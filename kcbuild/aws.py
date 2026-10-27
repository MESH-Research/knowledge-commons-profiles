"""AWS operations: ECR login, credential check, ECS redeploy.

Everything here shells out to the locally installed AWS CLI, replacing the
``configure-aws-credentials`` and ``amazon-ecr-login`` GitHub actions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kcbuild.config import Target
    from kcbuild.runner import Runner


class AwsAuthError(RuntimeError):
    """The local AWS CLI has no usable credentials."""


def aws_environment(profile: str | None, region: str) -> dict[str, str]:
    env = {"AWS_REGION": region, "AWS_DEFAULT_REGION": region}
    if profile:
        env["AWS_PROFILE"] = profile
    return env


def caller_account(
    runner: Runner,
    *,
    profile: str | None,
    region: str,
) -> str:
    result = runner.run(
        [
            "aws", "sts", "get-caller-identity",
            "--query", "Account", "--output", "text",
        ],
        env=aws_environment(profile, region),
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        msg = (
            "No valid AWS credentials. Run `aws login` (or `aws sso login`) "
            "and retry, or pass --profile.\n"
            f"{result.stderr.strip()}"
        )
        raise AwsAuthError(msg)
    return result.stdout.strip()


def ecr_login(
    runner: Runner,
    registry: str,
    *,
    profile: str | None,
    region: str,
) -> None:
    env = aws_environment(profile, region)
    password = runner.run(
        ["aws", "ecr", "get-login-password", "--region", region],
        env=env,
        capture=True,
    ).stdout.strip()
    runner.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        stdin=password,
    )


def force_deployment(
    runner: Runner,
    target: Target,
    *,
    profile: str | None,
    region: str,
) -> None:
    env = aws_environment(profile, region)
    runner.run(
        [
            "aws", "ecs", "update-service",
            "--cluster", target.ecs_cluster,
            "--service", target.ecs_service,
            "--force-new-deployment",
        ],
        env=env,
    )
    runner.run(
        [
            "aws", "autoscaling", "start-instance-refresh",
            "--auto-scaling-group-name", target.autoscale_group,
            "--region", region,
            "--preferences", '{"SkipMatching": false}',
        ],
        env=env,
    )
