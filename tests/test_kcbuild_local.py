from pathlib import Path

from kcbuild import local
from tests.kcbuild_support import FakeRunner

REG = "755997884632.dkr.ecr.us-east-1.amazonaws.com"
DB = "postgres://kcp:kcp@host.docker.internal:5459/kcp"
COMPOSE = ["docker", "compose", "-f", "docker-compose.local.yml"]


def test_start_container_starts_the_named_container():
    runner = FakeRunner()

    local.start_container(runner, "kcp-test-pg")

    assert runner.commands == [["docker", "start", "kcp-test-pg"]]


def test_local_environment_names_the_base_image_and_database():
    env = local.local_compose_environment(REG, DB)

    assert env["ECR_REGISTRY"] == REG
    assert env["LOCAL_DATABASE_URL"] == DB
    assert env["DOCKER_BUILDKIT"] == "1"


def test_up_builds_then_starts_detached(tmp_path: Path):
    runner = FakeRunner()

    local.local_stack_up(runner, tmp_path, REG, database_url=DB)

    assert runner.commands == [
        [*COMPOSE, "build"],
        [*COMPOSE, "up", "-d", "--remove-orphans"],
    ]
    assert all(call.env["ECR_REGISTRY"] == REG for call in runner.calls)
    assert all(call.env["LOCAL_DATABASE_URL"] == DB for call in runner.calls)


def test_up_can_skip_the_build_and_run_in_the_foreground(tmp_path: Path):
    runner = FakeRunner()

    local.local_stack_up(
        runner, tmp_path, REG, database_url=DB, build=False, detach=False,
    )

    assert runner.commands == [[*COMPOSE, "up", "--remove-orphans"]]


def test_down_stops_the_stack(tmp_path: Path):
    runner = FakeRunner()

    local.local_stack_down(runner, tmp_path, REG)

    assert runner.commands == [[*COMPOSE, "down"]]
    assert runner.calls[0].env["ECR_REGISTRY"] == REG


def test_logs_follow_the_stack(tmp_path: Path):
    runner = FakeRunner()

    local.local_stack_logs(runner, tmp_path, REG)

    assert runner.commands == [[*COMPOSE, "logs", "-f"]]
