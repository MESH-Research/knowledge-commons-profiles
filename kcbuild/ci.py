"""Trigger GitHub Actions runs from the workstation.

The opposite direction from the rest of this tool: instead of replacing
CI, ask it to run. Everything shells out to the GitHub CLI (``gh``), which
must already be logged in. ``ci.yml`` only releases or deploys on a
``push`` or ``workflow_dispatch`` event for ``main`` / ``dev``, so the
trigger for each is a dispatch of that workflow on that branch; the base
images have their own dispatch-only workflow.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from kcbuild.runner import Runner

CI_WORKFLOW = "ci.yml"
BASE_WORKFLOW = "build-base.yml"
BASE_TARGETS = ("both", "production", "dev")


class CiTriggerError(RuntimeError):
    """``gh`` could not dispatch the workflow."""


@dataclass(frozen=True)
class CiTrigger:
    """What ``kcb.py ci-trigger <name>`` dispatches."""

    name: str
    workflow: str
    ref: str
    inputs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowRun:
    run_id: int
    url: str
    status: str


CI_TRIGGERS: dict[str, CiTrigger] = {
    "main": CiTrigger("main", CI_WORKFLOW, "main"),
    "dev": CiTrigger("dev", CI_WORKFLOW, "dev"),
    "base": CiTrigger("base", BASE_WORKFLOW, "main", {"target": "both"}),
}


def get_trigger(name: str, **inputs: str) -> CiTrigger:
    """The named trigger, with ``inputs`` overriding its defaults."""
    base = CI_TRIGGERS[name]
    return CiTrigger(
        base.name, base.workflow, base.ref, {**base.inputs, **inputs},
    )


def trigger_workflow(runner: Runner, trigger: CiTrigger) -> None:
    """``gh workflow run`` the trigger's workflow on its ref."""
    args = ["gh", "workflow", "run", trigger.workflow, "--ref", trigger.ref]
    for key, value in trigger.inputs.items():
        args += ["-f", f"{key}={value}"]
    result = runner.run(args, check=False)
    if result.returncode != 0:
        msg = (
            f"Could not dispatch {trigger.workflow} on {trigger.ref} "
            f"(gh exited {result.returncode}). Is the GitHub CLI logged in "
            "(`gh auth login`) with access to this repository?"
        )
        raise CiTriggerError(msg)


def find_dispatched_run(
    runner: Runner,
    trigger: CiTrigger,
    *,
    attempts: int = 5,
    delay: float = 2.0,
    sleep: Callable[[float], None] | None = None,
) -> WorkflowRun | None:
    """
    The newest ``workflow_dispatch`` run of the trigger's workflow on its
    ref, polling a few times because GitHub registers the run a moment
    after the dispatch call returns. ``None`` when nothing appeared.
    """
    pause = sleep or time.sleep
    for attempt in range(attempts):
        if attempt:
            pause(delay)
        result = runner.run(
            [
                "gh", "run", "list",
                "--workflow", trigger.workflow,
                "--branch", trigger.ref,
                "--event", "workflow_dispatch",
                "--limit", "1",
                "--json", "databaseId,url,status",
            ],
            capture=True,
            check=False,
        )
        runs = json.loads(result.stdout) if result.stdout.strip() else []
        if result.returncode == 0 and runs:
            newest = runs[0]
            return WorkflowRun(
                run_id=int(newest["databaseId"]),
                url=newest["url"],
                status=newest.get("status", ""),
            )
    return None


def watch_run(runner: Runner, run: WorkflowRun) -> None:
    """Follow the run until it finishes; non-zero exit if it fails."""
    runner.run(["gh", "run", "watch", str(run.run_id), "--exit-status"])
