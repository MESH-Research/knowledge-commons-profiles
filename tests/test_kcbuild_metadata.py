
from typing import TYPE_CHECKING

import pytest

from kcbuild import metadata
from kcbuild.config import get_target
from tests.kcbuild_support import FakeRunner
from tests.kcbuild_support import answer

if TYPE_CHECKING:
    from pathlib import Path

SHA = "0123456789abcdef0123456789abcdef01234567"


def test_read_project_version_from_pyproject(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.ruff]\nline-length = 80\n\n[project]\nname = "x"\n'
        'version = "4.57.0"\n',
    )

    assert metadata.read_project_version(pyproject) == "4.57.0"


def test_git_sha_and_branch_come_from_the_repository(tmp_path: Path):
    runner = FakeRunner(
        answer(("git", "rev-parse", "HEAD"), 0, f"{SHA}\n"),
        answer(("git", "rev-parse", "--abbrev-ref", "HEAD"), 0, "main\n"),
    )

    assert metadata.git_sha(runner, tmp_path) == SHA
    assert metadata.git_branch(runner, tmp_path) == "main"


def test_collect_build_info_combines_git_and_version(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1.2.3"\n',
    )
    runner = FakeRunner(
        answer(("git", "rev-parse", "HEAD"), 0, f"{SHA}\n"),
        answer(("git", "rev-parse", "--abbrev-ref", "HEAD"), 0, "dev\n"),
    )

    info = metadata.collect_build_info(runner, tmp_path)

    assert info == metadata.BuildInfo(sha=SHA, branch="dev", version="1.2.3")
    assert info.short_sha == "0123456"


def test_production_tags_match_the_release_job():
    info = metadata.BuildInfo(sha=SHA, branch="main", version="4.57.0")

    tags = metadata.compute_tags(get_target("production"), info)

    assert tags.image_tag == SHA
    assert tags.version_tag == "v4.57.0"
    assert tags.build_tag == "v4.57.0-0123456"
    assert tags.all == [SHA, "v4.57.0-0123456", "v4.57.0", "latest"]


def test_dev_tags_are_branch_prefixed_and_unversioned():
    info = metadata.BuildInfo(sha=SHA, branch="dev", version="4.57.0")

    tags = metadata.compute_tags(get_target("dev"), info)

    assert tags.image_tag == SHA
    assert tags.version_tag is None
    assert tags.build_tag == "dev-v4.57.0-0123456"
    assert tags.all == [SHA, "dev-v4.57.0-0123456", "latest"]


@pytest.mark.parametrize("target_name", ["production", "dev"])
def test_compose_environment_supplies_every_variable_compose_reads(
    target_name: str,
):
    target = get_target(target_name)
    info = metadata.BuildInfo(sha=SHA, branch="main", version="4.57.0")
    tags = metadata.compute_tags(target, info)

    env = metadata.compose_environment(target, "reg.example", info, tags)

    assert env["ECR_REGISTRY"] == "reg.example"
    assert env["ECR_REPOSITORY"] == target.ecr_repository
    assert env["ECR_REPOSITORY_TRAEFIK"] == target.ecr_repository_traefik
    assert env["ECR_REPOSITORY_IDMS"] == target.ecr_repository_idms
    assert env["IMAGE_TAG"] == SHA
    assert env["BUILD_TAG"] == tags.build_tag
    assert env["APP_BRANCH"] == "main"
    assert env["GIT_SHA"] == SHA


def test_compose_environment_includes_monitor_only_for_production():
    info = metadata.BuildInfo(sha=SHA, branch="main", version="4.57.0")

    production = get_target("production")
    prod_env = metadata.compose_environment(
        production, "reg", info, metadata.compute_tags(production, info),
    )
    dev = get_target("dev")
    dev_env = metadata.compose_environment(
        dev, "reg", info, metadata.compute_tags(dev, info),
    )

    assert prod_env["ECR_REPOSITORY_MONITOR"] == "kcprofiles-monitor"
    assert "ECR_REPOSITORY_MONITOR" not in dev_env


def test_git_queries_are_marked_safe_for_dry_runs(tmp_path: Path):
    runner = FakeRunner(*[
        answer(("git", "rev-parse", "HEAD"), 0, f"{SHA}\n"),
        answer(("git", "rev-parse", "--abbrev-ref", "HEAD"), 0, "main\n"),
    ])

    metadata.git_sha(runner, tmp_path)
    metadata.git_branch(runner, tmp_path)

    assert all(call.always_run for call in runner.calls)
