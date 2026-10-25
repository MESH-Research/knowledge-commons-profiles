"""Docker build, tag and push operations."""


from typing import TYPE_CHECKING

from kcbuild.config import BASE_DOCKERFILE
from kcbuild.config import Target
from kcbuild.metadata import BuildInfo
from kcbuild.metadata import ImageTags
from kcbuild.metadata import compose_environment

if TYPE_CHECKING:
    from pathlib import Path

    from kcbuild.runner import Runner


def base_image_ref(registry: str, repository: str) -> str:
    return f"{registry}/{repository}:latest"


def image_exists(runner: Runner, ref: str) -> bool:
    result = runner.run(
        ["docker", "image", "inspect", ref], capture=True, check=False,
        always_run=True,
    )
    return result.returncode == 0


def build_base(
    runner: Runner,
    repo: Path,
    ref: str,
    build_environment: str,
    *,
    no_cache: bool = False,
) -> str:
    args = [
        "docker", "build",
        "--build-arg", f"BUILD_ENVIRONMENT={build_environment}",
        "-f", BASE_DOCKERFILE,
        "-t", ref,
    ]
    if no_cache:
        args.append("--no-cache")
    args.append(".")
    runner.run(args, cwd=repo, env={"DOCKER_BUILDKIT": "1"})
    return ref


def pull_image(runner: Runner, ref: str) -> None:
    runner.run(["docker", "pull", ref])


def build_app_images(  # noqa: PLR0913
    runner: Runner,
    repo: Path,
    target: Target,
    registry: str,
    *,
    info: BuildInfo,
    tags: ImageTags,
    services: list[str] | None = None,
    no_cache: bool = False,
) -> None:
    args = ["docker", "compose", "-f", target.compose_file, "build"]
    if no_cache:
        args.append("--no-cache")
    args.extend(services or [])
    runner.run(
        args, cwd=repo, env=compose_environment(target, registry, info, tags),
    )


def retag_pairs(
    target: Target,
    registry: str,
    tags: ImageTags,
) -> list[tuple[str, str]]:
    extra_tags = [tags.build_tag]
    if tags.version_tag:
        extra_tags.append(tags.version_tag)
    return [
        (f"{registry}/{repo}:{tags.image_tag}", f"{registry}/{repo}:{tag}")
        for repo in target.repositories
        for tag in extra_tags
    ]


def retag_images(
    runner: Runner,
    target: Target,
    registry: str,
    tags: ImageTags,
) -> list[str]:
    created = []
    for source, destination in retag_pairs(target, registry, tags):
        runner.run(["docker", "tag", source, destination])
        created.append(destination)
    return created


def push_refs(target: Target, registry: str, tags: ImageTags) -> list[str]:
    return [
        f"{registry}/{repo}:{tag}"
        for repo in target.repositories
        for tag in tags.all
    ]


def push_images(runner: Runner, refs: list[str]) -> None:
    for ref in refs:
        runner.run(["docker", "push", ref])
