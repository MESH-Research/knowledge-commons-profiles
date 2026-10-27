"""Deployment constants mirrored from ``.github/workflows/ci.yml``.

Keep these in step with the ``release-main`` and ``deploy-dev`` jobs: the
whole point of this tool is to produce images that are indistinguishable
from a CI build.
"""

from dataclasses import dataclass

AWS_ACCOUNT_ID = "755997884632"
AWS_REGION = "us-east-1"
COMMITIZEN_VERSION = "4.16.2"
BASE_DOCKERFILE = "compose/base/Dockerfile"
TEST_COMPOSE_FILE = "docker-compose.github.yml"
TEST_BASE_REPOSITORY = "kcprofiles-base-dev"
TEST_BASE_BUILD_ENVIRONMENT = "local"


@dataclass(frozen=True)
class Target:
    name: str
    compose_file: str
    ecr_repository: str
    ecr_repository_traefik: str
    ecr_repository_idms: str
    ecr_repository_monitor: str | None
    ecs_cluster: str
    ecs_service: str
    autoscale_group: str
    base_repository: str = "kcprofiles-base"
    base_build_environment: str = "production"
    tags_version: bool = True
    branch_prefixed_build_tag: bool = False

    @property
    def repositories(self) -> list[str]:
        repos = [
            self.ecr_repository,
            self.ecr_repository_traefik,
            self.ecr_repository_idms,
        ]
        if self.ecr_repository_monitor:
            repos.append(self.ecr_repository_monitor)
        return repos


def ecr_registry(
    account_id: str = AWS_ACCOUNT_ID,
    region: str = AWS_REGION,
) -> str:
    return f"{account_id}.dkr.ecr.{region}.amazonaws.com"


TARGETS: dict[str, Target] = {
    "production": Target(
        name="production",
        compose_file="docker-compose.production.yml",
        ecr_repository="kcprofiles",
        ecr_repository_traefik="kcprofiles-traefik",
        ecr_repository_idms="kcprofiles-idms",
        ecr_repository_monitor="kcprofiles-monitor",
        ecs_cluster="kcprofiles",
        ecs_service="kcprofiles-blue",
        autoscale_group=(
            "Infra-ECS-Cluster-kcprofiles-ee645084-ECSAutoScalingGroup-"
            "v3MrRnH7laIx"
        ),
        tags_version=True,
        branch_prefixed_build_tag=False,
    ),
    "dev": Target(
        name="dev",
        compose_file="docker-compose.dev.yml",
        ecr_repository="kcprofiles-dev",
        ecr_repository_traefik="kcprofiles-traefik-dev",
        ecr_repository_idms="kcprofiles-idms-dev",
        ecr_repository_monitor=None,
        ecs_cluster="kcprofiles-dev-2",
        ecs_service="kcprofiles-dev",
        autoscale_group=(
            "Infra-ECS-Cluster-kcprofiles-dev-2-f89c2350-ECSAutoScalingGroup-"
            "zUYaGlEf1GWi"
        ),
        tags_version=False,
        branch_prefixed_build_tag=True,
    ),
}


def get_target(name: str) -> Target:
    return TARGETS[name]
