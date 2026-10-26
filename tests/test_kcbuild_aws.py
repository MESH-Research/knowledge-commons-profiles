import pytest

from kcbuild import aws
from kcbuild.config import get_target
from tests.kcbuild_support import FakeRunner
from tests.kcbuild_support import answer

REG = "755997884632.dkr.ecr.us-east-1.amazonaws.com"


def test_aws_environment_sets_region_and_optional_profile():
    assert aws.aws_environment(None, "us-east-1") == {
        "AWS_REGION": "us-east-1",
        "AWS_DEFAULT_REGION": "us-east-1",
    }
    assert aws.aws_environment("kc", "us-east-1")["AWS_PROFILE"] == "kc"


def test_caller_account_returns_the_account_id():
    runner = FakeRunner(
        answer(("aws", "sts", "get-caller-identity"), 0, "755997884632\n"),
    )

    account = aws.caller_account(runner, profile="kc", region="us-east-1")

    assert account == "755997884632"
    (call,) = runner.calls
    assert call.env["AWS_PROFILE"] == "kc"


def test_caller_account_raises_a_helpful_error_when_logged_out():
    runner = FakeRunner(answer(("aws", "sts"), 255, ""))

    with pytest.raises(aws.AwsAuthError, match="aws login"):
        aws.caller_account(runner, profile=None, region="us-east-1")


def test_ecr_login_pipes_the_password_into_docker_login():
    runner = FakeRunner(
        answer(("aws", "ecr", "get-login-password"), 0, "tok3n\n"),
    )

    aws.ecr_login(runner, REG, profile=None, region="us-east-1")

    password, login = runner.calls
    assert password.args[:3] == ["aws", "ecr", "get-login-password"]
    assert "us-east-1" in password.args
    assert login.args == [
        "docker", "login", "--username", "AWS", "--password-stdin", REG,
    ]
    assert login.stdin == "tok3n"


def test_ecr_login_does_not_put_the_token_on_a_command_line():
    runner = FakeRunner(
        answer(("aws", "ecr", "get-login-password"), 0, "tok3n\n"),
    )

    aws.ecr_login(runner, REG, profile=None, region="us-east-1")

    assert not any("tok3n" in arg for call in runner.calls for arg in call.args)


def test_force_deployment_matches_the_release_job():
    runner = FakeRunner()
    target = get_target("production")

    aws.force_deployment(runner, target, profile="kc", region="us-east-1")

    ecs, asg = runner.calls
    assert ecs.args == [
        "aws", "ecs", "update-service",
        "--cluster", "kcprofiles",
        "--service", "kcprofiles-blue",
        "--force-new-deployment",
    ]
    assert asg.args[:3] == ["aws", "autoscaling", "start-instance-refresh"]
    assert target.autoscale_group in asg.args
    assert "--preferences" in asg.args
    assert '{"SkipMatching": false}' in asg.args
    assert ecs.env["AWS_PROFILE"] == "kc"
    assert asg.env["AWS_REGION"] == "us-east-1"
