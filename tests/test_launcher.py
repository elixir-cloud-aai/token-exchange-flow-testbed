"""Tests of `testbed.launcher`: processes and HTTP are replaced by fakes."""

import subprocess
from typing import Any

import pytest
import requests

from testbed import launcher
from testbed.settings import Settings


class FakeProcess:
    """Stands in for `subprocess.Popen`.

    Attributes:
        started: All processes created, with their arguments.
        hangs: Whether waiting for the process times out.
    """

    started: list["FakeProcess"]
    hangs = False

    def __init__(self, args: list[str], **options: Any) -> None:
        """Create the process.

        Args:
            args: Command line.
            **options: Options of the process.
        """
        self.args = args
        self.env = options["env"]
        self.stdout = ["line one\n"]
        self.terminated = False
        self.killed = False
        type(self).started.append(self)

    def terminate(self) -> None:
        """Record that the process was asked to end."""
        self.terminated = True

    def wait(self, timeout: float) -> None:
        """Wait for the end of the process.

        Args:
            timeout: How long to wait, in seconds.

        Raises:
            subprocess.TimeoutExpired: The process hangs.
        """
        if self.hangs:
            raise subprocess.TimeoutExpired(self.args, timeout)

    def kill(self) -> None:
        """Record that the process was killed."""
        self.killed = True


@pytest.fixture
def processes(monkeypatch: pytest.MonkeyPatch) -> type[FakeProcess]:
    """Replace `subprocess.Popen` with a fake.

    Args:
        monkeypatch: Pytest's monkeypatch.

    Returns:
        The class of the fake, with the processes that were started.
    """
    FakeProcess.started = []
    FakeProcess.hangs = False
    monkeypatch.setattr("subprocess.Popen", FakeProcess)
    return FakeProcess


class FakeSession:
    """Stands in for `requests.Session`.

    Attributes:
        answers: What the next requests get: a status or an exception.
    """

    answers: list[int | Exception]

    def get(self, _url: str, **_options: Any) -> Any:
        """Answer a request.

        Args:
            _url: URL.
            **_options: Options of the request.

        Returns:
            Response with a status.

        Raises:
            Exception: The next answer is an exception.
        """
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return type("Response", (), {"status_code": answer})()


def test_services_start_per_role_and_pass_on_output(
    mock_settings: Settings, processes: type[FakeProcess]
) -> None:
    """Each service role with a client gets a process, and its output is labelled."""
    lines: list[str] = []
    services = launcher.Services(mock_settings, lines.append)
    assert services.roles == ["gateway", "node", "orchestrator", "loop"]
    assert processes.started[0].args[-1] == "gateway"
    assert processes.started[0].env["TESTBED_PROVIDER"] == "mock"
    services._pump("gateway", processes.started[0])  # type: ignore[arg-type]
    assert "[gateway] line one" in lines


def test_services_stop_kills_what_hangs(
    mock_settings: Settings, processes: type[FakeProcess]
) -> None:
    """Processes that don't end when asked are killed."""
    services = launcher.Services(mock_settings, lambda _line: None)
    services.stop()
    assert all(item.terminated and not item.killed for item in processes.started)
    processes.hangs = True
    services.stop()
    assert all(item.killed for item in processes.started)


def test_wait_until_healthy_retries(
    mock_settings: Settings,
    processes: type[FakeProcess],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Services that aren't up yet are asked again."""
    FakeSession.answers = [requests.ConnectionError(), 503, 200]
    monkeypatch.setattr("requests.Session", FakeSession)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    launcher.Services(mock_settings, lambda _line: None).wait_until_healthy()
    assert processes.started


def test_wait_until_healthy_gives_up(
    mock_settings: Settings,
    processes: type[FakeProcess],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A service that never answers is named."""
    FakeSession.answers = [requests.ConnectionError()]
    monkeypatch.setattr("requests.Session", FakeSession)
    services = launcher.Services(mock_settings, lambda _line: None)
    with pytest.raises(TimeoutError, match="gateway"):
        services.wait_until_healthy(timeout=-1)
    assert processes.started


def test_main_runs_until_interrupted(
    processes: type[FakeProcess],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The services run until Ctrl-C, and are stopped then."""

    def interrupt(_seconds: float) -> None:
        """Interrupt the wait.

        Args:
            _seconds: Seconds to wait.

        Raises:
            KeyboardInterrupt: Always.
        """
        raise KeyboardInterrupt

    FakeSession.answers = [200]
    monkeypatch.setattr("requests.Session", FakeSession)
    monkeypatch.setattr("time.sleep", interrupt)
    monkeypatch.setattr("sys.argv", ["testbed-services", "--provider", "mock"])
    launcher.main()
    assert "Up: gateway" in capsys.readouterr().out
    assert all(item.terminated for item in processes.started)
