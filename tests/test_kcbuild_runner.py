import sys
from pathlib import Path

import pytest

from kcbuild.runner import CommandError
from kcbuild.runner import Runner

EXIT_CODE = 3


def test_run_captures_stdout():
    result = Runner().run(
        [sys.executable, "-c", "print('hello')"],
        capture=True,
    )

    assert result.returncode == 0
    assert result.stdout == "hello\n"


def test_run_feeds_stdin_to_the_process():
    result = Runner().run(
        [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
        stdin="secret",
        capture=True,
    )

    assert result.stdout == "SECRET\n"


def test_run_raises_on_failure_when_checked():
    with pytest.raises(CommandError) as excinfo:
        Runner().run([sys.executable, "-c", f"raise SystemExit({EXIT_CODE})"])

    assert excinfo.value.result.returncode == EXIT_CODE


def test_run_returns_failure_when_not_checked():
    result = Runner().run(
        [sys.executable, "-c", f"raise SystemExit({EXIT_CODE})"],
        check=False,
    )

    assert result.returncode == EXIT_CODE


def test_run_passes_environment_to_the_process():
    result = Runner().run(
        [sys.executable, "-c", "import os; print(os.environ['KCB_X'])"],
        env={"KCB_X": "yes"},
        capture=True,
    )

    assert result.stdout == "yes\n"


def test_run_honours_working_directory(tmp_path: Path):
    result = Runner(cwd=tmp_path).run(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        capture=True,
    )

    assert Path(result.stdout.strip()).resolve() == tmp_path.resolve()


def test_dry_run_echoes_instead_of_executing(tmp_path: Path):
    marker = tmp_path / "marker"
    echoed: list[str] = []

    result = Runner(dry_run=True, echo=echoed.append).run(
        [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
    )

    assert result.returncode == 0
    assert not marker.exists()
    assert any("-c" in line for line in echoed)


def test_dry_run_never_echoes_stdin_contents(tmp_path: Path):
    echoed: list[str] = []

    Runner(dry_run=True, echo=echoed.append).run(
        ["docker", "login", "--password-stdin"],
        stdin="hunter2",
    )

    assert not any("hunter2" in line for line in echoed)


def test_dry_run_still_executes_read_only_queries():
    result = Runner(dry_run=True).run(
        [sys.executable, "-c", "print('real')"],
        capture=True,
        always_run=True,
    )

    assert result.stdout == "real\n"
