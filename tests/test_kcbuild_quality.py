
from typing import TYPE_CHECKING

import pytest

from kcbuild import quality
from kcbuild.runner import CommandError
from tests.kcbuild_support import FakeRunner
from tests.kcbuild_support import answer

if TYPE_CHECKING:
    from pathlib import Path

REG = "755997884632.dkr.ecr.us-east-1.amazonaws.com"


def test_lint_runs_pre_commit_on_all_files_inside_the_local_group(
    tmp_path: Path,
):
    runner = FakeRunner()

    quality.run_lint(runner, tmp_path)

    assert runner.commands == [
        ["uv", "run", "--group", "local", "pre-commit", "run", "--all-files"],
    ]


def test_docker_tests_follow_the_ci_test_job(tmp_path: Path):
    runner = FakeRunner()

    quality.run_tests_in_docker(runner, tmp_path, REG)

    compose = ["docker", "compose", "-f", "docker-compose.github.yml"]
    run = [*compose, "run", "--rm", "django", "uv", "run"]
    assert runner.commands == [
        [*compose, "build"],
        [*run, "python", "manage.py", "makemigrations", "--check"],
        [*run, "python", "manage.py", "migrate"],
        [*run, "coverage", "run", "manage.py", "test"],
        [*run, "python", "-m", "pytest",
         "knowledge_commons_profiles/cron/tests/", "-v"],
        [*compose, "down"],
    ]
    assert all(call.env["ECR_REGISTRY"] == REG for call in runner.calls)


def test_docker_tests_can_skip_migration_check_and_cron_tests(tmp_path: Path):
    runner = FakeRunner()

    quality.run_tests_in_docker(
        runner, tmp_path, REG, check_migrations=False, cron_tests=False,
    )

    flattened = [" ".join(args) for args in runner.commands]
    assert not any("makemigrations" in line for line in flattened)
    assert not any("pytest" in line for line in flattened)
    assert any("coverage run manage.py test" in line for line in flattened)


def test_docker_tests_tear_down_the_stack_even_when_tests_fail(
    tmp_path: Path,
):
    runner = FakeRunner(answer(("docker", "compose", "-f",
                                "docker-compose.github.yml", "run", "--rm",
                                "django", "uv", "run", "coverage"), 1, ""))

    with pytest.raises(CommandError):
        quality.run_tests_in_docker(runner, tmp_path, REG)

    assert runner.commands[-1] == [
        "docker", "compose", "-f", "docker-compose.github.yml", "down",
    ]


def test_docker_tests_can_leave_the_stack_running(tmp_path: Path):
    runner = FakeRunner()

    quality.run_tests_in_docker(runner, tmp_path, REG, keep_up=True)

    assert runner.commands[-1][-1] != "down"


def test_read_env_file_ignores_comments_blank_lines_and_quotes(
    tmp_path: Path,
):
    env_file = tmp_path / ".django"
    env_file.write_text(
        "# comment\n\nA=1\nB=\"two words\"\nC='three'\nD=x=y\n",
    )

    assert quality.read_env_file(env_file) == {
        "A": "1",
        "B": "two words",
        "C": "three",
        "D": "x=y",
    }


def test_host_tests_use_the_test_settings_and_supplied_database(
    tmp_path: Path,
):
    env_file = tmp_path / ".django"
    env_file.write_text("WEBHOOK_TOKEN=abc\nDATABASE_URL=postgres://wrong\n")
    runner = FakeRunner()

    quality.run_tests_on_host(
        runner,
        tmp_path,
        database_url="postgres://kcp:kcp@localhost:5459/kcp",
        wordpress_database_url="postgres://kcp:kcp@localhost:5459/kcp_wp",
        env_file=env_file,
        labels=["knowledge_commons_profiles.cilogon"],
    )

    (call,) = runner.calls
    assert call.args == [
        "uv", "run", "--group", "local", "python", "manage.py", "test",
        "knowledge_commons_profiles.cilogon",
    ]
    assert call.env["WEBHOOK_TOKEN"] == "abc"
    assert call.env["DATABASE_URL"] == "postgres://kcp:kcp@localhost:5459/kcp"
    assert (
        call.env["WORDPRESS_DATABASE_URL"]
        == "postgres://kcp:kcp@localhost:5459/kcp_wp"
    )
    assert call.env["DJANGO_SETTINGS_MODULE"] == "config.settings.test"


def test_host_tests_default_to_the_whole_project(tmp_path: Path):
    env_file = tmp_path / ".django"
    env_file.write_text("")
    runner = FakeRunner()

    quality.run_tests_on_host(
        runner, tmp_path, database_url="a", wordpress_database_url="b",
        env_file=env_file,
    )

    assert runner.commands[0][-1] == "knowledge_commons_profiles"


def test_bump_reports_true_when_head_moves(tmp_path: Path):
    heads = iter(["aaa\n", "bbb\n"])
    runner = FakeRunner(
        lambda args: (0, next(heads))
        if args[:3] == ["git", "rev-parse", "HEAD"] else None,
    )

    bumped = quality.bump_version(runner, tmp_path)

    assert bumped is True
    (bump,) = runner.commands_starting("uvx")
    assert "commitizen==4.16.2" in " ".join(bump)
    assert bump[-3:] == ["cz", "bump", "--yes"]


def test_bump_reports_false_when_nothing_to_bump(tmp_path: Path):
    runner = FakeRunner(
        answer(("git", "rev-parse", "HEAD"), 0, "aaa\n"),
        answer(("uvx",), 21, ""),
    )

    assert quality.bump_version(runner, tmp_path) is False


def test_bump_reports_false_when_head_is_unchanged(tmp_path: Path):
    runner = FakeRunner(answer(("git", "rev-parse", "HEAD"), 0, "aaa\n"))

    assert quality.bump_version(runner, tmp_path) is False


def test_bump_raises_on_unexpected_commitizen_failure(tmp_path: Path):
    runner = FakeRunner(
        answer(("git", "rev-parse", "HEAD"), 0, "aaa\n"),
        answer(("uvx",), 3, ""),
    )

    with pytest.raises(CommandError):
        quality.bump_version(runner, tmp_path)


def test_push_git_pushes_branch_with_tags(tmp_path: Path):
    runner = FakeRunner()

    quality.push_git(runner, tmp_path, "main")

    assert runner.commands == [["git", "push", "origin", "main", "--tags"]]
