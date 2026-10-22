"""Thin subprocess wrapper so every external call can be faked in tests."""

import os
import shlex
import subprocess
from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path


class CommandError(RuntimeError):
    """Raised when a command exits non-zero and ``check`` is on."""

    def __init__(self, result: "CommandResult") -> None:
        self.result = result
        super().__init__(
            f"Command {shlex.join(result.args)!r} exited with "
            f"{result.returncode}",
        )


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    env: dict[str, str] = field(default_factory=dict)
    stdin: str | None = None
    always_run: bool = False


class Runner:
    """Executes commands, or merely echoes them in dry-run mode.

    ``env`` entries are layered on top of the current process environment.
    Stdin contents are never echoed, so secrets piped into ``docker login``
    stay off the terminal.
    """

    def __init__(
        self,
        *,
        dry_run: bool = False,
        echo: Callable[[str], None] | None = None,
        cwd: Path | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.echo = echo or (lambda _line: None)
        self.cwd = cwd

    def run(  # noqa: PLR0913
        self,
        args: list[str],
        *,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
        capture: bool = False,
        check: bool = True,
        cwd: Path | None = None,
        always_run: bool = False,
    ) -> CommandResult:
        """Run ``args``.

        ``always_run`` marks read-only queries (git rev-parse, docker image
        inspect) that are executed even in dry-run mode so the preview
        shows real tags.
        """
        extra_env = dict(env or {})
        prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in extra_env.items())
        line = f"$ {prefix + ' ' if prefix else ''}{shlex.join(args)}"
        if stdin is not None:
            line += "  <<< (stdin)"
        self.echo(line)

        if self.dry_run and not always_run:
            return CommandResult(
                args=list(args), returncode=0, env=extra_env, stdin=stdin,
            )

        completed = subprocess.run(  # noqa: S603
            args,
            cwd=cwd or self.cwd,
            env={**os.environ, **extra_env},
            input=stdin,
            capture_output=capture,
            text=True,
            check=False,
        )
        result = CommandResult(
            args=list(args),
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            env=extra_env,
            stdin=stdin,
            always_run=always_run,
        )
        if check and result.returncode != 0:
            raise CommandError(result)
        return result
