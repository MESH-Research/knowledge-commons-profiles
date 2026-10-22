import pytest

from kcbuild import config


def test_registry_is_the_account_scoped_ecr_host():
    assert (
        config.ecr_registry("755997884632", "us-east-1")
        == "755997884632.dkr.ecr.us-east-1.amazonaws.com"
    )


def test_production_target_matches_the_release_job():
    target = config.get_target("production")

    assert target.compose_file == "docker-compose.production.yml"
    assert target.ecr_repository == "kcprofiles"
    assert target.ecr_repository_traefik == "kcprofiles-traefik"
    assert target.ecr_repository_idms == "kcprofiles-idms"
    assert target.ecr_repository_monitor == "kcprofiles-monitor"
    assert target.ecs_cluster == "kcprofiles"
    assert target.ecs_service == "kcprofiles-blue"
    assert target.autoscale_group.startswith("Infra-ECS-Cluster-kcprofiles-ee")
    assert target.tags_version is True
    assert target.branch_prefixed_build_tag is False


def test_dev_target_matches_the_deploy_dev_job():
    target = config.get_target("dev")

    assert target.compose_file == "docker-compose.dev.yml"
    assert target.ecr_repository == "kcprofiles-dev"
    assert target.ecr_repository_traefik == "kcprofiles-traefik-dev"
    assert target.ecr_repository_idms == "kcprofiles-idms-dev"
    assert target.ecr_repository_monitor is None
    assert target.ecs_cluster == "kcprofiles-dev-2"
    assert target.ecs_service == "kcprofiles-dev"
    assert target.autoscale_group.startswith(
        "Infra-ECS-Cluster-kcprofiles-dev-2",
    )
    assert target.tags_version is False
    assert target.branch_prefixed_build_tag is True


def test_both_targets_build_from_the_production_base_image():
    for name in ("production", "dev"):
        target = config.get_target(name)
        assert target.base_repository == "kcprofiles-base"
        assert target.base_build_environment == "production"


def test_repositories_skips_monitor_when_absent():
    assert config.get_target("production").repositories == [
        "kcprofiles",
        "kcprofiles-traefik",
        "kcprofiles-idms",
        "kcprofiles-monitor",
    ]
    assert config.get_target("dev").repositories == [
        "kcprofiles-dev",
        "kcprofiles-traefik-dev",
        "kcprofiles-idms-dev",
    ]


def test_unknown_target_is_rejected():
    with pytest.raises(KeyError):
        config.get_target("staging")
