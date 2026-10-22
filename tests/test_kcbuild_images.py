from pathlib import Path

import pytest

from kcbuild import images
from kcbuild.config import get_target
from kcbuild.metadata import BuildInfo
from kcbuild.metadata import compute_tags
from kcbuild.runner import CommandError
from tests.kcbuild_support import FakeRunner
from tests.kcbuild_support import answer

SHA = "0123456789abcdef0123456789abcdef01234567"
REG = "755997884632.dkr.ecr.us-east-1.amazonaws.com"
PROD_PUSHES = 16  # 4 repositories x (sha, build, version, latest)
DEV_PUSHES = 9  # 3 repositories x (sha, build, latest)


def test_base_image_ref_is_registry_scoped_latest():
    assert (
        images.base_image_ref(REG, "kcprofiles-base")
        == f"{REG}/kcprofiles-base:latest"
    )


def test_image_exists_reports_inspect_outcome():
    present = FakeRunner(answer(("docker", "image", "inspect"), 0, "[]"))
    missing = FakeRunner(answer(("docker", "image", "inspect"), 1, ""))

    assert images.image_exists(present, "x:latest") is True
    assert images.image_exists(missing, "x:latest") is False


def test_build_base_matches_the_build_base_workflow(tmp_path: Path):
    runner = FakeRunner()

    ref = images.build_base(
        runner, tmp_path, f"{REG}/kcprofiles-base:latest", "production",
    )

    assert ref == f"{REG}/kcprofiles-base:latest"
    (build,) = runner.commands_starting("docker", "build")
    assert "compose/base/Dockerfile" in build
    assert "BUILD_ENVIRONMENT=production" in build
    assert f"{REG}/kcprofiles-base:latest" in build
    assert build[-1] == "."
    assert "--no-cache" not in build


def test_build_base_can_disable_the_layer_cache(tmp_path: Path):
    runner = FakeRunner()

    images.build_base(runner, tmp_path, "r/b:latest", "local", no_cache=True)

    (build,) = runner.commands_starting("docker", "build")
    assert "--no-cache" in build
    assert "BUILD_ENVIRONMENT=local" in build


def test_pull_image_pulls_the_reference():
    runner = FakeRunner()

    images.pull_image(runner, "r/b:latest")

    assert runner.commands == [["docker", "pull", "r/b:latest"]]


def test_build_app_images_uses_compose_with_ci_environment(tmp_path: Path):
    target = get_target("production")
    info = BuildInfo(sha=SHA, branch="main", version="4.57.0")
    tags = compute_tags(target, info)
    runner = FakeRunner()

    images.build_app_images(
        runner, tmp_path, target, REG, info=info, tags=tags,
    )

    (call,) = runner.calls
    assert call.args[:5] == [
        "docker", "compose", "-f", "docker-compose.production.yml", "build",
    ]
    assert call.env["ECR_REGISTRY"] == REG
    assert call.env["IMAGE_TAG"] == SHA
    assert call.env["BUILD_TAG"] == "v4.57.0-0123456"
    assert call.env["GIT_SHA"] == SHA
    assert call.env["APP_BRANCH"] == "main"
    assert call.env["DOCKER_BUILDKIT"] == "1"
    assert call.env["COMPOSE_DOCKER_CLI_BUILD"] == "1"


def test_build_app_images_can_limit_services_and_skip_cache(tmp_path: Path):
    target = get_target("dev")
    info = BuildInfo(sha=SHA, branch="dev", version="4.57.0")
    tags = compute_tags(target, info)
    runner = FakeRunner()

    images.build_app_images(
        runner, tmp_path, target, REG, info=info, tags=tags,
        services=["django", "idms"], no_cache=True,
    )

    (call,) = runner.calls
    assert "--no-cache" in call.args
    assert call.args[-2:] == ["django", "idms"]


def test_production_retag_pairs_cover_build_and_version_tags():
    target = get_target("production")
    info = BuildInfo(sha=SHA, branch="main", version="4.57.0")
    tags = compute_tags(target, info)

    pairs = images.retag_pairs(target, REG, tags)

    expected = []
    for repo in (
        "kcprofiles", "kcprofiles-traefik", "kcprofiles-idms",
        "kcprofiles-monitor",
    ):
        source = f"{REG}/{repo}:{SHA}"
        expected.append((source, f"{REG}/{repo}:v4.57.0-0123456"))
        expected.append((source, f"{REG}/{repo}:v4.57.0"))
    assert pairs == expected


def test_dev_retag_pairs_have_no_version_tag_and_no_monitor():
    target = get_target("dev")
    info = BuildInfo(sha=SHA, branch="dev", version="4.57.0")
    tags = compute_tags(target, info)

    pairs = images.retag_pairs(target, REG, tags)

    assert pairs == [
        (
            f"{REG}/kcprofiles-dev:{SHA}",
            f"{REG}/kcprofiles-dev:dev-v4.57.0-0123456",
        ),
        (
            f"{REG}/kcprofiles-traefik-dev:{SHA}",
            f"{REG}/kcprofiles-traefik-dev:dev-v4.57.0-0123456",
        ),
        (
            f"{REG}/kcprofiles-idms-dev:{SHA}",
            f"{REG}/kcprofiles-idms-dev:dev-v4.57.0-0123456",
        ),
    ]


def test_retag_images_issues_a_docker_tag_per_pair():
    target = get_target("dev")
    info = BuildInfo(sha=SHA, branch="dev", version="4.57.0")
    tags = compute_tags(target, info)
    runner = FakeRunner()

    created = images.retag_images(runner, target, REG, tags)

    assert runner.commands == [
        ["docker", "tag", src, dst]
        for src, dst in images.retag_pairs(target, REG, tags)
    ]
    assert created == [dst for _, dst in images.retag_pairs(target, REG, tags)]


def test_push_refs_lists_every_tag_the_release_job_pushes():
    target = get_target("production")
    info = BuildInfo(sha=SHA, branch="main", version="4.57.0")
    tags = compute_tags(target, info)

    refs = images.push_refs(target, REG, tags)

    assert len(refs) == PROD_PUSHES
    for repo in target.repositories:
        for tag in (SHA, "v4.57.0-0123456", "v4.57.0", "latest"):
            assert f"{REG}/{repo}:{tag}" in refs


def test_push_refs_for_dev_omits_version_and_monitor():
    target = get_target("dev")
    info = BuildInfo(sha=SHA, branch="dev", version="4.57.0")
    tags = compute_tags(target, info)

    refs = images.push_refs(target, REG, tags)

    assert len(refs) == DEV_PUSHES
    assert not any("monitor" in ref for ref in refs)
    assert not any(ref.endswith(":v4.57.0") for ref in refs)


def test_push_images_pushes_each_ref_in_order():
    runner = FakeRunner()

    images.push_images(runner, ["a:1", "b:2"])

    assert runner.commands == [
        ["docker", "push", "a:1"],
        ["docker", "push", "b:2"],
    ]


def test_push_images_stops_at_the_first_failure():
    runner = FakeRunner(answer(("docker", "push", "a:1"), 1, ""))

    with pytest.raises(CommandError):
        images.push_images(runner, ["a:1", "b:2"])

    assert runner.commands == [["docker", "push", "a:1"]]


def test_image_exists_is_marked_safe_for_dry_runs():
    runner = FakeRunner(answer(("docker", "image", "inspect"), 0, "[]"))

    images.image_exists(runner, "x:latest")

    assert runner.calls[0].always_run is True
