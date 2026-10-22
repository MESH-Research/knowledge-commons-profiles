"""Test doubles for the kcbuild tool."""

from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path

from kcbuild.runner import CommandError
from kcbuild.runner import CommandResult

Responder = Callable[[list[str]], tuple[int, str] | None]


class FakeRunner:
    """Records every command and answers from a list of responders.

    A responder receives the argument list and returns ``(returncode,
    stdout)`` for commands it recognises, or ``None`` to pass. The first
    responder that answers wins; unanswered commands succeed with empty
    output.
    """

    def __init__(self, *responders: Responder) -> None:
        self.responders = list(responders)
        self.calls: list[CommandResult] = []

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
        returncode, stdout = 0, ""
        for responder in self.responders:
            answer = responder(args)
            if answer is not None:
                returncode, stdout = answer
                break
        result = CommandResult(
            args=list(args),
            returncode=returncode,
            stdout=stdout,
            env=dict(env or {}),
            stdin=stdin,
            always_run=always_run,
        )
        self.calls.append(result)
        if check and returncode != 0:
            raise CommandError(result)
        return result

    @property
    def commands(self) -> list[list[str]]:
        return [call.args for call in self.calls]

    def commands_starting(self, *prefix: str) -> list[list[str]]:
        return [
            args
            for args in self.commands
            if args[: len(prefix)] == list(prefix)
        ]


def answer(prefix: tuple[str, ...], returncode: int, stdout: str) -> Responder:
    """Build a responder that matches commands beginning with ``prefix``."""

    def respond(args: list[str]) -> tuple[int, str] | None:
        if tuple(args[: len(prefix)]) == prefix:
            return returncode, stdout
        return None

    return respond
