"""Run the local development stack (docker-compose.local.yml) on
https://localhost using the locally built base image.

``ECR_REGISTRY`` is only the name prefix the local Dockerfile uses in its
``FROM`` line. Docker never pulls an image that already exists under that
name, so as long as ``kcb.py base --dev`` has run, nothing touches AWS.
"""

from pathlib import Path

from kcbuild.runner import Runner

LOCAL_COMPOSE_FILE = "docker-compose.local.yml"


def start_container(runner: Runner, name: str) -> None:
    runner.run(["docker", "start", name])


def local_compose_environment(
    registry: str,
    database_url: str,
) -> dict[str, str]:
    return {
        "DOCKER_BUILDKIT": "1",
        "COMPOSE_DOCKER_CLI_BUILD": "1",
        "ECR_REGISTRY": registry,
        "LOCAL_DATABASE_URL": database_url,
    }


def _compose(
    runner: Runner,
    repo: Path,
    registry: str,
    args: list[str],
    database_url: str = "",
) -> None:
    runner.run(
        ["docker", "compose", "-f", LOCAL_COMPOSE_FILE, *args],
        cwd=repo,
        env=local_compose_environment(registry, database_url),
    )


def local_stack_up(  # noqa: PLR0913
    runner: Runner,
    repo: Path,
    registry: str,
    *,
    database_url: str,
    build: bool = True,
    detach: bool = True,
) -> None:
    if build:
        _compose(runner, repo, registry, ["build"], database_url)
    up = ["up", "-d"] if detach else ["up"]
    _compose(
        runner, repo, registry, [*up, "--remove-orphans"], database_url,
    )


def local_stack_down(runner: Runner, repo: Path, registry: str) -> None:
    _compose(runner, repo, registry, ["down"])


def local_stack_logs(runner: Runner, repo: Path, registry: str) -> None:
    _compose(runner, repo, registry, ["logs", "-f"])
