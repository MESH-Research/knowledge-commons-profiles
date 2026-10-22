"""Git and version metadata that feed the image tags."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from kcbuild.config import Target
from kcbuild.runner import Runner

SHORT_SHA_LENGTH = 7


@dataclass(frozen=True)
class BuildInfo:
    sha: str
    branch: str
    version: str

    @property
    def short_sha(self) -> str:
        return self.sha[:SHORT_SHA_LENGTH]


@dataclass(frozen=True)
class ImageTags:
    """The tags CI applies to every image.

    ``image_tag`` is the full commit SHA, ``build_tag`` is the unique
    ``vX.Y.Z-<sha7>`` rollback name and ``version_tag`` (production only)
    tracks the latest build of a release.
    """

    image_tag: str
    build_tag: str
    version_tag: str | None

    @property
    def all(self) -> list[str]:
        tags = [self.image_tag, self.build_tag]
        if self.version_tag:
            tags.append(self.version_tag)
        tags.append("latest")
        return tags


def read_project_version(pyproject: Path) -> str:
    with pyproject.open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def git_sha(runner: Runner, repo: Path) -> str:
    result = runner.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture=True,
        always_run=True,
    )
    return result.stdout.strip()


def git_branch(runner: Runner, repo: Path) -> str:
    result = runner.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture=True,
        always_run=True,
    )
    return result.stdout.strip()


def collect_build_info(runner: Runner, repo: Path) -> BuildInfo:
    return BuildInfo(
        sha=git_sha(runner, repo),
        branch=git_branch(runner, repo),
        version=read_project_version(repo / "pyproject.toml"),
    )


def compute_tags(target: Target, info: BuildInfo) -> ImageTags:
    build_tag = f"v{info.version}-{info.short_sha}"
    if target.branch_prefixed_build_tag:
        build_tag = f"{info.branch}-{build_tag}"
    return ImageTags(
        image_tag=info.sha,
        build_tag=build_tag,
        version_tag=f"v{info.version}" if target.tags_version else None,
    )


def compose_environment(
    target: Target,
    registry: str,
    info: BuildInfo,
    tags: ImageTags,
) -> dict[str, str]:
    env = {
        "DOCKER_BUILDKIT": "1",
        "COMPOSE_DOCKER_CLI_BUILD": "1",
        "ECR_REGISTRY": registry,
        "ECR_REPOSITORY": target.ecr_repository,
        "ECR_REPOSITORY_TRAEFIK": target.ecr_repository_traefik,
        "ECR_REPOSITORY_IDMS": target.ecr_repository_idms,
        "IMAGE_TAG": tags.image_tag,
        "BUILD_TAG": tags.build_tag,
        "APP_BRANCH": info.branch,
        "GIT_SHA": info.sha,
    }
    if target.ecr_repository_monitor:
        env["ECR_REPOSITORY_MONITOR"] = target.ecr_repository_monitor
    if tags.version_tag:
        env["VERSION_TAG"] = tags.version_tag
    return env
