
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from kcbuild.cli import main
from tests.kcbuild_support import FakeRunner
from tests.kcbuild_support import answer

if TYPE_CHECKING:
    from pathlib import Path

SHA = "0123456789abcdef0123456789abcdef01234567"
REG = "755997884632.dkr.ecr.us-east-1.amazonaws.com"
BASE = f"{REG}/kcprofiles-base:latest"
BASE_DEV = f"{REG}/kcprofiles-base-dev:latest"
PROD_RETAGS = 8  # 4 repositories x (build tag + version tag)
DEV_RETAGS = 3  # 3 repositories x build tag
PROD_PUSHES = 16  # 4 repositories x (sha, build, version, latest)

GIT = (
    answer(("git", "rev-parse", "HEAD"), 0, f"{SHA}\n"),
    answer(("git", "rev-parse", "--abbrev-ref", "HEAD"), 0, "main\n"),
)
AWS_OK = answer(("aws", "sts", "get-caller-identity"), 0, "755997884632\n")
AWS_LOGGED_OUT = answer(("aws", "sts", "get-caller-identity"), 255, "")
ECR_TOKEN = answer(("aws", "ecr", "get-login-password"), 0, "tok\n")
BASE_PRESENT = answer(("docker", "image", "inspect"), 0, "[]")
BASE_MISSING = answer(("docker", "image", "inspect"), 1, "")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "4.57.0"\n',
    )
    return tmp_path


def invoke(fake: FakeRunner, repo: Path, *args: str):
    return CliRunner().invoke(
        main, ["--repo", str(repo), *args], obj=fake, catch_exceptions=False,
    )


def flat(fake: FakeRunner) -> list[str]:
    return [" ".join(args) for args in fake.commands]


def first_index(lines: list[str], needle: str) -> int:
    return next(i for i, line in enumerate(lines) if needle in line)


def test_info_reports_the_tags_that_would_be_used(repo: Path):
    fake = FakeRunner(*GIT)

    result = invoke(fake, repo, "info")

    assert result.exit_code == 0
    assert SHA in result.output
    assert "v4.57.0-0123456" in result.output
    assert REG in result.output
    assert not fake.commands_starting("docker")


def test_lint_runs_pre_commit(repo: Path):
    fake = FakeRunner()

    result = invoke(fake, repo, "lint")

    assert result.exit_code == 0
    assert flat(fake) == ["uv run --group local pre-commit run --all-files"]


def test_failing_stage_exits_non_zero_without_a_traceback(repo: Path):
    fake = FakeRunner(answer(("uv",), 1, ""))

    result = CliRunner().invoke(
        main, ["--repo", str(repo), "lint"], obj=fake,
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "pre-commit" in result.output


def test_build_reuses_an_existing_base_image(repo: Path):
    fake = FakeRunner(*GIT, BASE_PRESENT)

    result = invoke(fake, repo, "build")

    assert result.exit_code == 0
    assert not fake.commands_starting("docker", "build")
    (compose,) = fake.commands_starting("docker", "compose")
    assert "docker-compose.production.yml" in compose
    assert len(fake.commands_starting("docker", "tag")) == PROD_RETAGS


def test_build_creates_the_base_image_when_missing(repo: Path):
    fake = FakeRunner(*GIT, BASE_MISSING)

    result = invoke(fake, repo, "build")

    assert result.exit_code == 0
    (base_build,) = fake.commands_starting("docker", "build")
    assert BASE in base_build
    assert "BUILD_ENVIRONMENT=production" in base_build
    lines = flat(fake)
    assert lines.index(" ".join(base_build)) < lines.index(
        next(line for line in lines if line.startswith("docker compose")),
    )


def test_build_can_force_a_base_rebuild(repo: Path):
    fake = FakeRunner(*GIT, BASE_PRESENT)

    result = invoke(fake, repo, "build", "--rebuild-base")

    assert result.exit_code == 0
    assert len(fake.commands_starting("docker", "build")) == 1


def test_build_for_dev_target_uses_the_dev_compose_file(repo: Path):
    fake = FakeRunner(*GIT, BASE_PRESENT)

    result = invoke(fake, repo, "--target", "dev", "build")

    assert result.exit_code == 0
    (compose,) = fake.commands_starting("docker", "compose")
    assert "docker-compose.dev.yml" in compose
    assert len(fake.commands_starting("docker", "tag")) == DEV_RETAGS


def test_base_pull_fetches_from_ecr_after_login(repo: Path):
    fake = FakeRunner(AWS_OK, ECR_TOKEN)

    result = invoke(fake, repo, "base", "--pull")

    assert result.exit_code == 0
    assert flat(fake)[-1] == f"docker pull {BASE}"
    assert fake.commands_starting("docker", "login")
    assert not fake.commands_starting("docker", "build")


def test_base_builds_locally_by_default(repo: Path):
    fake = FakeRunner()

    result = invoke(fake, repo, "base")

    assert result.exit_code == 0
    (build,) = fake.commands_starting("docker", "build")
    assert BASE in build
    assert not fake.commands_starting("aws")


def test_push_logs_in_and_pushes_every_release_tag(repo: Path):
    fake = FakeRunner(*GIT, AWS_OK, ECR_TOKEN)

    result = invoke(fake, repo, "push")

    assert result.exit_code == 0
    assert fake.commands_starting("docker", "login")
    pushes = fake.commands_starting("docker", "push")
    assert len(pushes) == PROD_PUSHES
    assert ["docker", "push", f"{REG}/kcprofiles:v4.57.0"] in pushes
    assert ["docker", "push", f"{REG}/kcprofiles-monitor:latest"] in pushes


def test_push_can_skip_the_login(repo: Path):
    fake = FakeRunner(*GIT)

    result = invoke(fake, repo, "push", "--skip-login")

    assert result.exit_code == 0
    assert not fake.commands_starting("aws")
    assert len(fake.commands_starting("docker", "push")) == PROD_PUSHES


def test_push_explains_when_aws_session_has_expired(repo: Path):
    fake = FakeRunner(*GIT, AWS_LOGGED_OUT)

    result = CliRunner().invoke(main, ["--repo", str(repo), "push"], obj=fake)

    assert result.exit_code != 0
    assert "aws login" in result.output
    assert not fake.commands_starting("docker", "push")


def test_push_can_include_the_base_image(repo: Path):
    fake = FakeRunner(*GIT, AWS_OK, ECR_TOKEN)

    result = invoke(fake, repo, "push", "--with-base")

    assert result.exit_code == 0
    assert ["docker", "push", BASE] in fake.commands_starting("docker", "push")


def test_deploy_forces_a_new_ecs_deployment(repo: Path):
    fake = FakeRunner(AWS_OK)

    result = invoke(fake, repo, "deploy")

    assert result.exit_code == 0
    lines = flat(fake)
    assert any(
        line.startswith("aws ecs update-service")
        and "--force-new-deployment" in line
        for line in lines
    )
    assert any(line.startswith("aws autoscaling start-instance-refresh")
               for line in lines)


def test_deploy_dev_uses_the_dev_cluster(repo: Path):
    fake = FakeRunner(AWS_OK)

    invoke(fake, repo, "--target", "dev", "deploy")

    (ecs,) = fake.commands_starting("aws", "ecs")
    assert "kcprofiles-dev-2" in ecs
    assert "kcprofiles-dev" in ecs


def test_login_only_logs_in(repo: Path):
    fake = FakeRunner(AWS_OK, ECR_TOKEN)

    result = invoke(fake, repo, "login")

    assert result.exit_code == 0
    assert flat(fake)[-1].startswith("docker login")


def test_test_in_docker_builds_dev_base_then_runs_the_ci_steps(repo: Path):
    fake = FakeRunner(BASE_MISSING)

    result = invoke(fake, repo, "test")

    assert result.exit_code == 0
    (base_build,) = fake.commands_starting("docker", "build")
    assert BASE_DEV in base_build
    assert "BUILD_ENVIRONMENT=local" in base_build
    lines = flat(fake)
    assert "docker compose -f docker-compose.github.yml build" in lines
    assert any("coverage run manage.py test" in line for line in lines)
    assert lines[-1] == "docker compose -f docker-compose.github.yml down"


def test_test_on_host_runs_manage_py_test(repo: Path):
    env_dir = repo / ".envs" / ".github"
    env_dir.mkdir(parents=True)
    (env_dir / ".django").write_text("WEBHOOK_TOKEN=x\n")
    fake = FakeRunner()

    result = invoke(
        fake, repo, "test", "--host",
        "--database-url", "postgres://kcp:kcp@localhost:5459/kcp",
    )

    assert result.exit_code == 0
    (call,) = fake.calls
    assert call.args[:7] == [
        "uv", "run", "--group", "local", "python", "manage.py", "test",
    ]
    assert call.env["DATABASE_URL"] == "postgres://kcp:kcp@localhost:5459/kcp"
    assert call.env["WEBHOOK_TOKEN"] == "x"


def test_bump_runs_commitizen(repo: Path):
    fake = FakeRunner(*GIT)

    result = invoke(fake, repo, "bump")

    assert result.exit_code == 0
    (bump,) = fake.commands_starting("uvx")
    assert bump[-3:] == ["cz", "bump", "--yes"]


def test_release_runs_the_full_chain_in_ci_order(repo: Path):
    fake = FakeRunner(*GIT, AWS_OK, ECR_TOKEN, BASE_PRESENT)

    result = invoke(fake, repo, "release")

    assert result.exit_code == 0
    lines = flat(fake)
    order = [
        first_index(lines, "pre-commit"),
        first_index(lines, "coverage run"),
        first_index(lines, "docker compose -f docker-compose.production"),
        first_index(lines, "docker push"),
        first_index(lines, "update-service"),
    ]
    assert order == sorted(order)
    assert not fake.commands_starting("uvx")
    assert not fake.commands_starting("git", "push")


def test_release_stages_can_be_skipped(repo: Path):
    fake = FakeRunner(*GIT, BASE_PRESENT)

    result = invoke(
        fake, repo, "release",
        "--skip-lint", "--skip-tests", "--skip-push", "--skip-deploy",
    )

    assert result.exit_code == 0
    lines = flat(fake)
    assert not any("pre-commit" in line for line in lines)
    assert not any("coverage" in line for line in lines)
    assert not fake.commands_starting("docker", "push")
    assert not fake.commands_starting("aws")
    assert fake.commands_starting("docker", "compose")


def test_release_with_bump_bumps_before_building_and_pushes_git(repo: Path):
    heads = iter([f"{SHA}\n", "fedcba9876543210fedcba9876543210fedcba98\n",
                  "fedcba9876543210fedcba9876543210fedcba98\n"])
    fake = FakeRunner(
        lambda args: (0, next(heads))
        if args[:3] == ["git", "rev-parse", "HEAD"] else None,
        GIT[1], AWS_OK, ECR_TOKEN, BASE_PRESENT,
    )

    result = invoke(
        fake, repo, "release", "--skip-lint", "--skip-tests", "--bump",
        "--push-git",
    )

    assert result.exit_code == 0
    lines = flat(fake)
    bump_at = first_index(lines, "cz bump")
    build_at = first_index(lines, "docker compose")
    push_at = first_index(lines, "docker push")
    git_push_at = first_index(lines, "git push origin main --tags")
    assert bump_at < build_at < push_at < git_push_at
    (compose,) = fake.commands_starting("docker", "compose")
    env = fake.calls[fake.commands.index(compose)].env
    assert env["IMAGE_TAG"].startswith("fedcba98")


def test_release_stops_when_lint_fails(repo: Path):
    fake = FakeRunner(*GIT, answer(("uv", "run", "--group", "local",
                                    "pre-commit"), 1, ""))

    result = CliRunner().invoke(
        main, ["--repo", str(repo), "release"], obj=fake,
    )

    assert result.exit_code != 0
    assert not fake.commands_starting("docker", "compose")


def test_dry_run_without_injected_runner_executes_nothing(repo: Path):
    result = CliRunner().invoke(
        main, ["--repo", str(repo), "--dry-run", "deploy"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "aws ecs update-service" in result.output


def test_dry_run_info_still_reads_real_git_metadata(repo: Path):
    fake = FakeRunner(*GIT)

    result = invoke(fake, repo, "--dry-run", "info")

    assert result.exit_code == 0
    assert SHA in result.output


def test_up_builds_base_dev_if_missing_starts_db_and_brings_stack_up(
    repo: Path,
):
    fake = FakeRunner(BASE_MISSING)

    result = invoke(fake, repo, "up")

    assert result.exit_code == 0
    lines = flat(fake)
    (base_build,) = fake.commands_starting("docker", "build")
    assert BASE_DEV in base_build
    assert "docker start kcp-test-pg" in lines
    assert first_index(lines, "docker start") < first_index(
        lines, "docker compose -f docker-compose.local.yml up",
    )
    assert "docker compose -f docker-compose.local.yml build" in lines
    assert lines[-1] == (
        "docker compose -f docker-compose.local.yml up -d --remove-orphans"
    )
    assert not fake.commands_starting("aws")


def test_up_reuses_an_existing_base_dev_image(repo: Path):
    fake = FakeRunner(BASE_PRESENT)

    result = invoke(fake, repo, "up", "--no-db-container")

    assert result.exit_code == 0
    assert not fake.commands_starting("docker", "build")
    assert not fake.commands_starting("docker", "start")


def test_up_passes_database_url_to_compose(repo: Path):
    fake = FakeRunner(BASE_PRESENT)

    invoke(fake, repo, "up", "--database-url", "postgres://x@y/z")

    (up,) = [
        call for call in fake.calls
        if call.args[-3:] == ["up", "-d", "--remove-orphans"]
    ]
    assert up.env["LOCAL_DATABASE_URL"] == "postgres://x@y/z"


def test_down_stops_the_local_stack(repo: Path):
    fake = FakeRunner()

    result = invoke(fake, repo, "down")

    assert result.exit_code == 0
    assert flat(fake) == ["docker compose -f docker-compose.local.yml down"]


def test_logs_follow_the_local_stack(repo: Path):
    fake = FakeRunner()

    result = invoke(fake, repo, "logs")

    assert result.exit_code == 0
    assert flat(fake) == ["docker compose -f docker-compose.local.yml logs -f"]
