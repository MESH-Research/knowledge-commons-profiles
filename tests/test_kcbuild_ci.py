import json
import re
from pathlib import Path

import pytest

from kcbuild import ci
from kcbuild.ci import CI_TRIGGERS
from kcbuild.ci import WorkflowRun
from kcbuild.ci import find_dispatched_run
from kcbuild.ci import get_trigger
from kcbuild.ci import trigger_workflow
from kcbuild.ci import watch_run
from tests.kcbuild_support import FakeRunner
from tests.kcbuild_support import answer

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
RUN_ID = 42
RUN_URL = (
    "https://github.com/MESH-Research/knowledge-commons-profiles/actions/"
    f"runs/{RUN_ID}"
)
ONE_RUN = json.dumps(
    [{"databaseId": RUN_ID, "url": RUN_URL, "status": "queued"}],
)
ATTEMPTS = 3


def test_triggers_cover_main_dev_and_base():
    assert set(CI_TRIGGERS) == {"main", "dev", "base"}


@pytest.mark.parametrize("name", ["main", "dev"])
def test_main_and_dev_dispatch_ci_on_their_own_branch(name: str):
    trigger = get_trigger(name)

    assert trigger.workflow == "ci.yml"
    assert trigger.ref == name
    assert trigger.inputs == {}


def test_base_dispatches_the_base_image_workflow_for_both_images():
    trigger = get_trigger("base")

    assert trigger.workflow == "build-base.yml"
    assert trigger.inputs == {"target": "both"}


def test_base_target_can_be_narrowed():
    assert get_trigger("base", target="production").inputs == {
        "target": "production",
    }


def test_unknown_trigger_is_rejected():
    with pytest.raises(KeyError):
        get_trigger("staging")


def test_trigger_workflow_runs_gh_workflow_run_on_the_ref():
    runner = FakeRunner()

    trigger_workflow(runner, get_trigger("dev"))

    assert runner.commands == [
        ["gh", "workflow", "run", "ci.yml", "--ref", "dev"],
    ]


def test_trigger_workflow_passes_inputs_as_raw_fields():
    runner = FakeRunner()

    trigger_workflow(runner, get_trigger("base", target="dev"))

    (command,) = runner.commands
    assert command[:6] == [
        "gh", "workflow", "run", "build-base.yml", "--ref", "main",
    ]
    assert command[6:] == ["-f", "target=dev"]


def test_trigger_workflow_explains_when_gh_fails():
    runner = FakeRunner(answer(("gh", "workflow", "run"), 4, ""))

    with pytest.raises(ci.CiTriggerError, match="gh auth login"):
        trigger_workflow(runner, get_trigger("main"))


def test_find_dispatched_run_returns_the_newest_dispatch_run():
    runner = FakeRunner(answer(("gh", "run", "list"), 0, ONE_RUN))

    run = find_dispatched_run(
        runner, get_trigger("main"), sleep=lambda _s: None,
    )

    assert run == WorkflowRun(run_id=RUN_ID, url=RUN_URL, status="queued")
    (command,) = runner.commands
    assert "--workflow" in command
    assert command[command.index("--workflow") + 1] == "ci.yml"
    assert command[command.index("--branch") + 1] == "main"
    assert command[command.index("--event") + 1] == "workflow_dispatch"


def test_find_dispatched_run_polls_until_the_run_appears():
    answers = iter(["[]", "[]", ONE_RUN])
    runner = FakeRunner(
        lambda args: (0, next(answers)) if args[:3] == ["gh", "run", "list"]
        else None,
    )
    slept: list[float] = []

    run = find_dispatched_run(
        runner, get_trigger("main"), attempts=5, delay=0.5,
        sleep=slept.append,
    )

    assert run is not None
    assert run.run_id == RUN_ID
    assert len(runner.commands) == ATTEMPTS
    assert slept == [0.5, 0.5]


def test_find_dispatched_run_gives_up_after_the_attempts():
    runner = FakeRunner(answer(("gh", "run", "list"), 0, "[]"))

    run = find_dispatched_run(
        runner, get_trigger("dev"), attempts=ATTEMPTS, sleep=lambda _s: None,
    )

    assert run is None
    assert len(runner.commands) == ATTEMPTS


def test_find_dispatched_run_treats_empty_output_as_no_run():
    """Dry-run mode yields no stdout at all; that must not crash."""
    runner = FakeRunner(answer(("gh", "run", "list"), 0, ""))

    run = find_dispatched_run(
        runner, get_trigger("main"), attempts=1, sleep=lambda _s: None,
    )

    assert run is None


def test_watch_run_follows_the_run_and_propagates_failure():
    runner = FakeRunner()

    run = WorkflowRun(run_id=RUN_ID, url=RUN_URL, status="queued")

    watch_run(runner, run)

    assert runner.commands == [
        ["gh", "run", "watch", str(RUN_ID), "--exit-status"],
    ]


# -- The workflows must accept what the tool sends --------------------------


def test_every_trigger_points_at_an_existing_workflow_file():
    for trigger in CI_TRIGGERS.values():
        assert (WORKFLOWS / trigger.workflow).is_file(), trigger


def test_ci_workflow_accepts_manual_dispatch():
    text = (WORKFLOWS / "ci.yml").read_text()

    assert re.search(r"^  workflow_dispatch:", text, re.MULTILINE)


@pytest.mark.parametrize("job", ["release-main", "deploy-dev"])
def test_ci_release_and_deploy_jobs_run_on_dispatch(job: str):
    """A dispatched run on main/dev must release/deploy, not just test."""
    text = (WORKFLOWS / "ci.yml").read_text()
    job_block = text.split(f"\n  {job}:\n", 1)[1].split("\n  steps:", 1)[0]
    condition = re.search(r"^\s+if: (.+)$", job_block, re.MULTILINE)

    assert condition is not None
    assert "workflow_dispatch" in condition.group(1)


def test_base_workflow_accepts_the_targets_the_tool_offers():
    text = (WORKFLOWS / "build-base.yml").read_text()
    options = re.search(
        r"options:\n((?:\s+- \w+\n)+)", text,
    )

    assert options is not None
    offered = {
        line.strip("- ").strip() for line in options.group(1).splitlines()
    }
    assert offered == set(ci.BASE_TARGETS)
