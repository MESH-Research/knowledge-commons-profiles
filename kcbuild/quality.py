"""Lint, test and version-bump stages."""

from pathlib import Path

from kcbuild.config import COMMITIZEN_VERSION
from kcbuild.config import TEST_COMPOSE_FILE
from kcbuild.metadata import git_sha
from kcbuild.runner import CommandError
from kcbuild.runner import Runner

CZ_NO_COMMITS_EXIT_CODE = 21
UV_LOCAL = ["uv", "run", "--group", "local"]


def run_lint(runner: Runner, repo: Path) -> None:
    runner.run([*UV_LOCAL, "pre-commit", "run", "--all-files"], cwd=repo)


def run_tests_in_docker(  # noqa: PLR0913
    runner: Runner,
    repo: Path,
    registry: str,
    *,
    check_migrations: bool = True,
    cron_tests: bool = True,
    keep_up: bool = False,
) -> None:
    env = {
        "DOCKER_BUILDKIT": "1",
        "COMPOSE_DOCKER_CLI_BUILD": "1",
        "ECR_REGISTRY": registry,
    }
    compose = ["docker", "compose", "-f", TEST_COMPOSE_FILE]
    django = [*compose, "run", "--rm", "django", "uv", "run"]

    def step(args: list[str]) -> None:
        runner.run(args, cwd=repo, env=env)

    try:
        step([*compose, "build"])
        if check_migrations:
            step([*django, "python", "manage.py", "makemigrations", "--check"])
        step([*django, "python", "manage.py", "migrate"])
        step([*django, "coverage", "run", "manage.py", "test"])
        if cron_tests:
            step([
                *django, "python", "-m", "pytest",
                "knowledge_commons_profiles/cron/tests/", "-v",
            ])
    finally:
        if not keep_up:
            step([*compose, "down"])


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def run_tests_on_host(  # noqa: PLR0913
    runner: Runner,
    repo: Path,
    *,
    database_url: str,
    wordpress_database_url: str,
    env_file: Path,
    labels: list[str] | None = None,
) -> None:
    env = read_env_file(env_file)
    env.update({
        "DATABASE_URL": database_url,
        "WORDPRESS_DATABASE_URL": wordpress_database_url,
        "DJANGO_SETTINGS_MODULE": "config.settings.test",
    })
    runner.run(
        [
            *UV_LOCAL, "python", "manage.py", "test",
            *(labels or ["knowledge_commons_profiles"]),
        ],
        cwd=repo,
        env=env,
    )


def bump_version(runner: Runner, repo: Path) -> bool:
    """Run commitizen exactly as the release job does.

    Returns True when a bump commit was created. Exit code 21 means
    commitizen found nothing semantic to bump, which is not an error.
    """
    before = git_sha(runner, repo)
    result = runner.run(
        [
            "uvx", "--from", f"commitizen=={COMMITIZEN_VERSION}",
            "cz", "bump", "--yes",
        ],
        cwd=repo,
        check=False,
    )
    if result.returncode == CZ_NO_COMMITS_EXIT_CODE:
        return False
    if result.returncode != 0:
        raise CommandError(result)
    return git_sha(runner, repo) != before


def push_git(runner: Runner, repo: Path, branch: str) -> None:
    runner.run(["git", "push", "origin", branch, "--tags"], cwd=repo)
