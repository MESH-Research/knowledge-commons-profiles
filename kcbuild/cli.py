"""Click command line for the local CI stand-in.

Each stage of ``.github/workflows/ci.yml`` is its own subcommand so a build
can be produced without linting or testing first; ``release`` chains them
in the same order CI uses.
"""

import functools
import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import click

from kcbuild import aws
from kcbuild import images
from kcbuild import local
from kcbuild import metadata
from kcbuild import quality
from kcbuild.config import AWS_REGION
from kcbuild.config import TARGETS
from kcbuild.config import TEST_BASE_BUILD_ENVIRONMENT
from kcbuild.config import TEST_BASE_REPOSITORY
from kcbuild.config import TEST_COMPOSE_FILE
from kcbuild.config import Target
from kcbuild.config import ecr_registry
from kcbuild.config import get_target
from kcbuild.runner import CommandError
from kcbuild.runner import Runner

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_DATABASE_URL = "postgres://kcp:kcp@localhost:5459/kcp"
DEFAULT_TEST_WP_DATABASE_URL = "postgres://kcp:kcp@localhost:5459/kcp_wp"
DEFAULT_TEST_ENV_FILE = ".envs/.github/.django"
DEFAULT_LOCAL_DATABASE_URL = "postgres://kcp:kcp@host.docker.internal:5459/kcp"
DEFAULT_DB_CONTAINER = "kcp-test-pg"


@dataclass
class AppContext:
    runner: Runner
    target: Target
    registry: str
    region: str
    profile: str | None
    repo: Path

    def build_info(self) -> metadata.BuildInfo:
        return metadata.collect_build_info(self.runner, self.repo)

    def tags(self, info: metadata.BuildInfo) -> metadata.ImageTags:
        return metadata.compute_tags(self.target, info)

    def base_ref(self) -> str:
        return images.base_image_ref(self.registry, self.target.base_repository)


def banner(text: str) -> None:
    click.secho(f"\n==> {text}", fg="cyan", bold=True)


def handle_errors(func: Callable[..., None]) -> Callable[..., None]:
    """Turn stage failures into a short message and a non-zero exit."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CommandError as exc:
            click.secho(f"\nFAILED: {exc}", fg="red", err=True)
            sys.exit(exc.result.returncode or 1)
        except aws.AwsAuthError as exc:
            click.secho(f"\nFAILED: {exc}", fg="red", err=True)
            sys.exit(2)

    return wrapper


def warn_if_not_arm64() -> None:
    if platform.machine() not in {"aarch64", "arm64"}:
        click.secho(
            "Warning: images are built for linux/arm64 but this host is "
            f"{platform.machine()}; docker will need binfmt/QEMU emulation.",
            fg="yellow",
            err=True,
        )


@click.group()
@click.option(
    "--target", "target_name",
    type=click.Choice(sorted(TARGETS)), default="production",
    show_default=True, help="Which deployment to build for.",
)
@click.option(
    "--profile", default=None, envvar="AWS_PROFILE",
    help="AWS CLI profile to use for ECR and ECS calls.",
)
@click.option("--region", default=AWS_REGION, show_default=True)
@click.option(
    "--registry", default=None,
    help="Override the ECR registry host (defaults to the KC account).",
)
@click.option(
    "--repo", type=click.Path(path_type=Path, file_okay=False),
    default=REPO_ROOT, help="Repository root (defaults to this checkout).",
)
@click.option(
    "--dry-run", is_flag=True,
    help="Print every command instead of running it.",
)
@click.pass_context
def main(  # noqa: PLR0913
    ctx: click.Context,
    *,
    target_name: str,
    profile: str | None,
    region: str,
    registry: str | None,
    repo: Path,
    dry_run: bool,
) -> None:
    """Build, test, push and deploy KC Profiles without GitHub Actions."""
    # Tests inject a fake runner through ``obj``; anything with a ``run``
    # method is accepted so the CLI never touches a real subprocess there.
    injected = ctx.obj if hasattr(ctx.obj, "run") else None
    ctx.obj = AppContext(
        runner=injected or Runner(dry_run=dry_run, echo=click.echo, cwd=repo),
        target=get_target(target_name),
        registry=registry or ecr_registry(region=region),
        region=region,
        profile=profile,
        repo=repo,
    )


pass_app = click.make_pass_decorator(AppContext)


# -- Individual stages -------------------------------------------------------


@main.command()
@pass_app
@handle_errors
def info(app: AppContext) -> None:
    """Show the tags and names this checkout would be built with."""
    build = app.build_info()
    tags = app.tags(build)
    click.echo(f"target:      {app.target.name}")
    click.echo(f"registry:    {app.registry}")
    click.echo(f"branch:      {build.branch}")
    click.echo(f"version:     {build.version}")
    click.echo(f"sha:         {build.sha}")
    click.echo(f"base image:  {app.base_ref()}")
    click.echo(f"image tag:   {tags.image_tag}")
    click.echo(f"build tag:   {tags.build_tag}")
    click.echo(f"version tag: {tags.version_tag or '(none for this target)'}")
    click.echo("would push:")
    for ref in images.push_refs(app.target, app.registry, tags):
        click.echo(f"  {ref}")


@main.command()
@pass_app
@handle_errors
def lint(app: AppContext) -> None:
    """Run pre-commit on all files, as the CI linter job does."""
    banner("Lint (pre-commit --all-files)")
    quality.run_lint(app.runner, app.repo)
    click.secho("Lint passed.", fg="green")


@main.command()
@click.option(
    "--host", is_flag=True,
    help="Run manage.py test on this machine against an existing Postgres "
         "instead of the CI docker compose stack.",
)
@click.option(
    "--database-url", default=DEFAULT_TEST_DATABASE_URL, show_default=True,
    help="Postgres URL for --host mode.",
)
@click.option(
    "--wordpress-database-url", default=DEFAULT_TEST_WP_DATABASE_URL,
    show_default=True, help="WordPress DB URL for --host mode.",
)
@click.option(
    "--env-file", default=DEFAULT_TEST_ENV_FILE, show_default=True,
    help="Dummy env file for --host mode (relative to the repo).",
)
@click.argument("labels", nargs=-1)
@click.option(
    "--skip-migration-check", is_flag=True,
    help="Docker mode: skip `makemigrations --check`.",
)
@click.option(
    "--skip-cron-tests", is_flag=True,
    help="Docker mode: skip the cron/monitor pytest run.",
)
@click.option(
    "--keep-up", is_flag=True,
    help="Docker mode: leave the compose stack running afterwards.",
)
@click.option(
    "--rebuild-base", is_flag=True,
    help="Docker mode: rebuild the dev base image even if present.",
)
@pass_app
@handle_errors
def test(  # noqa: PLR0913
    app: AppContext,
    *,
    host: bool,
    database_url: str,
    wordpress_database_url: str,
    env_file: str,
    labels: tuple[str, ...],
    skip_migration_check: bool,
    skip_cron_tests: bool,
    keep_up: bool,
    rebuild_base: bool,
) -> None:
    """Run the test suite, by default exactly as the CI test job does."""
    if host:
        host_test_stage(
            app,
            database_url=database_url,
            wordpress_database_url=wordpress_database_url,
            env_file=env_file,
            labels=list(labels) or None,
        )
    else:
        docker_test_stage(
            app,
            check_migrations=not skip_migration_check,
            cron_tests=not skip_cron_tests,
            keep_up=keep_up,
            rebuild_base=rebuild_base,
        )
    click.secho("Tests passed.", fg="green")


def host_test_stage(
    app: AppContext,
    *,
    database_url: str = DEFAULT_TEST_DATABASE_URL,
    wordpress_database_url: str = DEFAULT_TEST_WP_DATABASE_URL,
    env_file: str = DEFAULT_TEST_ENV_FILE,
    labels: list[str] | None = None,
) -> None:
    banner("Tests on host (manage.py test)")
    quality.run_tests_on_host(
        app.runner,
        app.repo,
        database_url=database_url,
        wordpress_database_url=wordpress_database_url,
        env_file=app.repo / env_file,
        labels=labels,
    )


def docker_test_stage(
    app: AppContext,
    *,
    check_migrations: bool = True,
    cron_tests: bool = True,
    keep_up: bool = False,
    rebuild_base: bool = False,
) -> None:
    dev_base = images.base_image_ref(app.registry, TEST_BASE_REPOSITORY)
    ensure_base(
        app, dev_base, TEST_BASE_BUILD_ENVIRONMENT, rebuild=rebuild_base,
    )
    banner(f"Tests in docker ({TEST_COMPOSE_FILE})")
    quality.run_tests_in_docker(
        app.runner,
        app.repo,
        app.registry,
        check_migrations=check_migrations,
        cron_tests=cron_tests,
        keep_up=keep_up,
    )


def ensure_base(  # noqa: PLR0913
    app: AppContext,
    ref: str,
    build_environment: str,
    *,
    rebuild: bool = False,
    pull: bool = False,
    no_cache: bool = False,
) -> None:
    if pull:
        banner(f"Pull base image {ref}")
        aws.caller_account(app.runner, profile=app.profile, region=app.region)
        aws.ecr_login(
            app.runner, app.registry, profile=app.profile, region=app.region,
        )
        images.pull_image(app.runner, ref)
        return
    if not rebuild and images.image_exists(app.runner, ref):
        click.echo(f"Base image {ref} already present; reusing it.")
        return
    banner(f"Build base image {ref} (BUILD_ENVIRONMENT={build_environment})")
    images.build_base(
        app.runner, app.repo, ref, build_environment, no_cache=no_cache,
    )


@main.command()
@click.option(
    "--pull", is_flag=True,
    help="Pull the base image from ECR instead of building it.",
)
@click.option("--no-cache", is_flag=True, help="Build without layer cache.")
@click.option(
    "--dev", is_flag=True,
    help="Build the kcprofiles-base-dev image used by the test stage.",
)
@pass_app
@handle_errors
def base(app: AppContext, *, pull: bool, no_cache: bool, dev: bool) -> None:
    """Build (or pull) the base image the app images are built FROM."""
    warn_if_not_arm64()
    if dev:
        ref = images.base_image_ref(app.registry, TEST_BASE_REPOSITORY)
        build_environment = TEST_BASE_BUILD_ENVIRONMENT
    else:
        ref = app.base_ref()
        build_environment = app.target.base_build_environment
    ensure_base(
        app, ref, build_environment, rebuild=True, pull=pull,
        no_cache=no_cache,
    )
    click.secho(f"Base image ready: {ref}", fg="green")


def build_stage(
    app: AppContext,
    *,
    rebuild_base: bool = False,
    pull_base: bool = False,
    no_cache: bool = False,
    services: list[str] | None = None,
) -> metadata.ImageTags:
    warn_if_not_arm64()
    ensure_base(
        app, app.base_ref(), app.target.base_build_environment,
        rebuild=rebuild_base, pull=pull_base,
    )
    build = app.build_info()
    tags = app.tags(build)
    banner(
        f"Build {app.target.name} images ({app.target.compose_file}) "
        f"tag={tags.build_tag}",
    )
    images.build_app_images(
        app.runner, app.repo, app.target, app.registry,
        info=build, tags=tags, services=services, no_cache=no_cache,
    )
    banner("Apply version-anchored tags")
    for ref in images.retag_images(app.runner, app.target, app.registry, tags):
        click.echo(f"  {ref}")
    return tags


@main.command()
@click.option(
    "--rebuild-base", is_flag=True,
    help="Rebuild the base image even if it already exists locally.",
)
@click.option(
    "--pull-base", is_flag=True,
    help="Pull the base image from ECR (needs AWS credentials).",
)
@click.option("--no-cache", is_flag=True, help="Build without layer cache.")
@click.option(
    "--service", "services", multiple=True,
    help="Only build these compose services (e.g. django).",
)
@pass_app
@handle_errors
def build(
    app: AppContext,
    *,
    rebuild_base: bool,
    pull_base: bool,
    no_cache: bool,
    services: tuple[str, ...],
) -> None:
    """Build the app images with the same tags CI would apply."""
    tags = build_stage(
        app, rebuild_base=rebuild_base, pull_base=pull_base,
        no_cache=no_cache, services=list(services) or None,
    )
    click.secho(
        f"Built {app.target.name} images: {tags.image_tag} "
        f"({tags.build_tag})",
        fg="green",
    )


def login_stage(app: AppContext) -> None:
    banner(f"ECR login ({app.registry})")
    account = aws.caller_account(
        app.runner, profile=app.profile, region=app.region,
    )
    click.echo(f"AWS account: {account}")
    aws.ecr_login(
        app.runner, app.registry, profile=app.profile, region=app.region,
    )


@main.command()
@pass_app
@handle_errors
def login(app: AppContext) -> None:
    """Log docker in to ECR using the local AWS CLI."""
    login_stage(app)
    click.secho("Logged in.", fg="green")


def push_stage(
    app: AppContext,
    tags: metadata.ImageTags,
    *,
    skip_login: bool = False,
    with_base: bool = False,
) -> list[str]:
    if not skip_login:
        login_stage(app)
    refs = images.push_refs(app.target, app.registry, tags)
    if with_base:
        refs = [app.base_ref(), *refs]
    banner(f"Push {len(refs)} image references to ECR")
    images.push_images(app.runner, refs)
    return refs


@main.command()
@click.option("--skip-login", is_flag=True, help="Assume docker is logged in.")
@click.option(
    "--with-base", is_flag=True,
    help="Also push the base image (as the build-base workflow does).",
)
@pass_app
@handle_errors
def push(app: AppContext, *, skip_login: bool, with_base: bool) -> None:
    """Push the images built by `build` to ECR."""
    tags = app.tags(app.build_info())
    refs = push_stage(app, tags, skip_login=skip_login, with_base=with_base)
    click.secho(f"Pushed {len(refs)} references.", fg="green")


def deploy_stage(app: AppContext) -> None:
    banner(
        f"Deploy: {app.target.ecs_cluster}/{app.target.ecs_service} "
        f"+ refresh {app.target.autoscale_group}",
    )
    aws.caller_account(app.runner, profile=app.profile, region=app.region)
    aws.force_deployment(
        app.runner, app.target, profile=app.profile, region=app.region,
    )


@main.command()
@pass_app
@handle_errors
def deploy(app: AppContext) -> None:
    """Force a new ECS deployment and an instance refresh."""
    deploy_stage(app)
    click.secho("Deployment requested.", fg="green")


@main.command()
@pass_app
@handle_errors
def bump(app: AppContext) -> None:
    """Bump the version with commitizen, as the release job does."""
    banner("Version bump (commitizen)")
    if quality.bump_version(app.runner, app.repo):
        click.secho("Version bumped; remember to push with --tags.", fg="green")
    else:
        click.echo("Nothing to bump.")


# -- Local development stack --------------------------------------------------


@main.command()
@click.option(
    "--database-url", default=DEFAULT_LOCAL_DATABASE_URL, show_default=True,
    help="Postgres URL as seen from inside the django container.",
)
@click.option(
    "--db-container", default=DEFAULT_DB_CONTAINER, show_default=True,
    help="Docker container to `docker start` before the stack comes up.",
)
@click.option(
    "--no-db-container", is_flag=True, help="Do not start any DB container.",
)
@click.option("--no-build", is_flag=True, help="Skip the image build.")
@click.option(
    "--foreground", is_flag=True,
    help="Stay attached to the containers instead of detaching.",
)
@click.option(
    "--rebuild-base", is_flag=True,
    help="Rebuild the dev base image even if present.",
)
@pass_app
@handle_errors
def up(  # noqa: PLR0913
    app: AppContext,
    *,
    database_url: str,
    db_container: str,
    no_db_container: bool,
    no_build: bool,
    foreground: bool,
    rebuild_base: bool,
) -> None:
    """Run the local dev stack on https://localhost with the local base."""
    dev_base = images.base_image_ref(app.registry, TEST_BASE_REPOSITORY)
    ensure_base(
        app, dev_base, TEST_BASE_BUILD_ENVIRONMENT, rebuild=rebuild_base,
    )
    for cert in ("cert.pem", "key.pem"):
        if not (Path.home() / cert).exists():
            click.secho(
                f"Warning: ~/{cert} not found; the compose file mounts it "
                "for TLS on port 443.",
                fg="yellow",
                err=True,
            )
    if not no_db_container:
        banner(f"Start database container {db_container}")
        local.start_container(app.runner, db_container)
    banner(f"Local stack ({local.LOCAL_COMPOSE_FILE}) on https://localhost")
    local.local_stack_up(
        app.runner, app.repo, app.registry,
        database_url=database_url, build=not no_build, detach=not foreground,
    )
    click.secho(
        "Stack is up: https://localhost  (kcb.py logs / kcb.py down)",
        fg="green",
    )


@main.command()
@pass_app
@handle_errors
def down(app: AppContext) -> None:
    """Stop the local dev stack."""
    local.local_stack_down(app.runner, app.repo, app.registry)
    click.secho("Stack stopped.", fg="green")


@main.command()
@pass_app
@handle_errors
def logs(app: AppContext) -> None:
    """Follow the local dev stack's logs."""
    local.local_stack_logs(app.runner, app.repo, app.registry)


# -- Chained run -------------------------------------------------------------


@main.command()
@click.option("--skip-lint", is_flag=True)
@click.option("--skip-tests", is_flag=True)
@click.option("--skip-push", is_flag=True)
@click.option("--skip-deploy", is_flag=True)
@click.option(
    "--bump", "do_bump", is_flag=True,
    help="Run `cz bump` before building (CI does this on main).",
)
@click.option(
    "--push-git", is_flag=True,
    help="After a successful push, `git push origin <branch> --tags` if the "
         "version was bumped.",
)
@click.option("--rebuild-base", is_flag=True)
@click.option("--pull-base", is_flag=True)
@click.option("--no-cache", is_flag=True)
@click.option("--host-tests", is_flag=True, help="Run tests with --host.")
@pass_app
@handle_errors
def release(  # noqa: PLR0913
    app: AppContext,
    *,
    skip_lint: bool,
    skip_tests: bool,
    skip_push: bool,
    skip_deploy: bool,
    do_bump: bool,
    push_git: bool,
    rebuild_base: bool,
    pull_base: bool,
    no_cache: bool,
    host_tests: bool,
) -> None:
    """Run the whole CI pipeline: lint, test, bump, build, push, deploy."""
    if not skip_lint:
        banner("Lint (pre-commit --all-files)")
        quality.run_lint(app.runner, app.repo)
    if not skip_tests:
        if host_tests:
            host_test_stage(app)
        else:
            docker_test_stage(app, rebuild_base=rebuild_base)
    bumped = False
    if do_bump:
        banner("Version bump (commitizen)")
        bumped = quality.bump_version(app.runner, app.repo)
        click.echo("Version bumped." if bumped else "Nothing to bump.")
    tags = build_stage(
        app, rebuild_base=rebuild_base, pull_base=pull_base,
        no_cache=no_cache,
    )
    if not skip_push:
        push_stage(app, tags)
        if bumped and push_git:
            branch = metadata.git_branch(app.runner, app.repo)
            banner(f"Push bump commit and tags to {branch}")
            quality.push_git(app.runner, app.repo, branch)
    if not skip_deploy:
        deploy_stage(app)
    click.secho(
        f"Release complete: {app.target.name} {tags.build_tag}", fg="green",
    )
