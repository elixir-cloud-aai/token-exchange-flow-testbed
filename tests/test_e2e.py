"""Tests of `testbed.e2e`: what it checks, with scripted results.

The run itself needs the mock: CI's job `e2e` and `docker compose run e2e` do it.
"""

import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from testbed import e2e
from testbed.e2e import TRACE, Run
from testbed.rules import REFUSED_BY_RULE
from testbed.settings import DUMMY_SECRET, MOCK_ISSUER, Settings
from testbed.tokens import TokenResponse
from tests.conftest import FakeProvider, FakeResponse

USER = "test-user-inside"


def _hops(*auds: str) -> list[dict[str, Any]]:
    """Create rows of a successful call.

    Args:
        *auds: Audiences of the hops.

    Returns:
        One row per hop.
    """
    last = len(auds) - 1
    return [
        {
            "service": aud,
            "aud": aud,
            "sub": USER,
            "traceparent": TRACE,
            "trace_origin": "received" if position else "generated",
            "hop_limit": 8 - position,
            "policy": "allowed" if position == last else "off",
            "reason": None,
            "entitlements": ["group"],
        }
        for position, aud in enumerate(auds)
    ]


def _refused(error: str = "invalid_grant", description: str = "") -> dict[str, Any]:
    """Create the result of an exchange that the testbed's rules refused.

    Args:
        error: Error code.
        description: Description.

    Returns:
        Result.
    """
    return {
        "ok": False,
        "refused_by": REFUSED_BY_RULE,
        "error": error,
        "error_description": description,
    }


def _at_first_hop(status: int, reason: str) -> dict[str, Any]:
    """Create the result of a call that the first service refused.

    Args:
        status: HTTP status.
        reason: Reason of the refusal.

    Returns:
        Result.
    """
    return {"ok": False, "status": status, "hops": [{"reason": reason}]}


GOOD: dict[str, dict[str, Any]] = {
    "clients": {"provider": "mock", "ls_login_rules_emulated": True},
    "discovery": {"issuer": MOCK_ISSUER},
    "login user": {
        "ok": True,
        "claims": {"sub": USER, "aud": "tx-client", "client_id": "tx-client"},
        "header": {"typ": "at+jwt"},
    },
    "exchange to-gateway": {"ok": True, "claims": {"aud": "tx-gateway"}},
    "call gateway --token to-gateway --save": {
        "status": 200,
        "hops": _hops("tx-gateway", "tx-node"),
    },
    "call orchestrator": {
        "status": 200,
        "hops": _hops("tx-orchestrator", "tx-gateway", "tx-node"),
    },
    "compare": {"identical_at_last_hop": True, "act_present": [False, False]},
    "exchange bad --as gateway --from user": _refused(),
    "exchange bad --as client --from user --audience @unreg": _refused(
        "invalid_target"
    ),
    "exchange bad --as gateway --from to-gateway": _refused("invalid_target"),
    "exchange to-gw-url": {"ok": True, "claims": {"aud": "https://gw/"}},
    "call gateway --token to-gw-url": {"status": 502},
    "call node --token to-gateway": _at_first_hop(401, "audience"),
    "call node --token user": _at_first_hop(401, "audience"),
    "call gateway --token to-gateway --tamper": _at_first_hop(401, "signature"),
    "call node --token rogue": _at_first_hop(401, "issuer"),
    "call node --token plain": _at_first_hop(401, "type"),
    "call node --token short": _at_first_hop(401, "expired"),
    "exchange bad --as client --from short": _refused("invalid_grant", "expired"),
    "call gateway --token to-gateway": {
        "status": 200,
        "hops": _hops("tx-gateway", "tx-node"),
    },
    "login outside": {"ok": True},
    "exchange out-gw": {"ok": True},
    "call gateway --token out-gw": {
        "status": 403,
        "hops": [
            {"service": "gateway", "policy": "off"},
            {"service": "node", "refused": "entitlement"},
        ],
    },
    "show user": {"refresh_token": {"present": True}},
    "refresh user2": {"ok": True, "claims": {"sub": USER}},
    "introspect user": {"active": True},
    "userinfo user": {"sub": USER},
    "lifetimes": {"tokens": {"user": {}}},
    "revoke user": {"ok": True},
    "call gateway --token to-gateway --hop-limit 0": {"status": 508},
    "call gateway --token to-gateway --hop-limit 1": {"status": 200},
    "call gateway --token to-gateway --hop-limit nonsense": {"status": 400},
    "call loop": {
        "status": 508,
        "hops": [{"hop_limit": limit, "reason": None} for limit in (3, 2, 1, 0)],
    },
    "exchange gap-x --as public": {"ok": False, "error": "invalid_request"},
    "exchange gap-x --as client --from gap --audience @gateway --requested": {
        "ok": True,
        "refresh_token": "absent",
        "claims": {},
    },
}


def script(
    changes: dict[str, dict[str, Any]] | None = None,
) -> Callable[[str], dict[str, Any]]:
    """Create a stand-in for `Session.execute`.

    Args:
        changes: Results to use instead of the good ones.

    Returns:
        Function that gives the result with the longest matching prefix.
    """
    table = {**GOOD, **(changes or {})}

    def execute(line: str) -> dict[str, Any]:
        """Get the result of a command line.

        Args:
            line: Command line.

        Returns:
            Result; `ok` by default.
        """
        matches = [prefix for prefix in table if line.startswith(prefix)]
        return dict(table[max(matches, key=len)]) if matches else {"ok": True}

    return execute


class ScriptedSession:
    """Stands in for `testbed.session.Session`.

    Attributes:
        settings: Settings.
        tokens: Tokens, by name.
        execute: Gives the result of a command line.
    """

    def __init__(self, settings: Settings, *_args: Any, **_options: Any) -> None:
        """Create the session.

        Args:
            settings: Settings.
            *_args: Ignored.
            **_options: Ignored.
        """
        self.settings = settings
        self.tokens = {"gap": TokenResponse(access_token="a.b.c")}
        self.execute = script()


@pytest.fixture
def run() -> Run:
    """Provide an empty run.

    Returns:
        Run.
    """
    return Run([])


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    """Provide docs with one harmless command per page group.

    Args:
        tmp_path: Temporary folder.

    Returns:
        Folder of the docs.
    """
    folder = tmp_path / "docs"
    for pages in e2e.PAGE_GROUPS:
        for page in pages:
            path = folder / page
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Page\n\n```text\ntb> clients\n```\n")
    return folder


def test_run_counts_and_reports_checks(
    run: Run, capsys: pytest.CaptureFixture[str]
) -> None:
    """Checks are printed and kept; failures are remembered."""
    run.section("Title")
    run.check("good", True)
    run.check("bad", False, {"seen": 1})
    output = capsys.readouterr().out
    assert "== Title" in output
    assert "PASS  good\n" in output
    assert 'FAIL  bad  [{"seen": 1}]' in output
    assert run.count == 2
    assert run.failures == ["bad"]
    assert len(run.output) == 3


@pytest.mark.parametrize(
    "scenario",
    [e2e._happy_path, e2e._refusals, e2e._entitlements, e2e._refresh, e2e._loops],
)
def test_scenarios_pass_with_the_expected_results(
    run: Run, scenario: Callable[[Run, Callable[[str], dict[str, Any]]], None]
) -> None:
    """The expected results make all checks of a scenario pass."""
    scenario(run, script())
    assert run.count > 0
    assert run.failures == []


@pytest.mark.parametrize(
    ("scenario", "prefix", "result", "failure"),
    [
        (
            e2e._happy_path,
            "exchange to-gateway",
            {"ok": True, "claims": {"aud": ["tx-gateway", "tx-node"]}},
            "client exchanges for the gateway",
        ),
        (
            e2e._happy_path,
            "compare",
            {"identical_at_last_hop": False, "act_present": [False, False]},
            "node sees the same claims on both paths",
        ),
        (
            e2e._refusals,
            "exchange bad --as gateway --from user",
            {"ok": True},
            "subject token without our client in aud",
        ),
        (
            e2e._refusals,
            "call node --token to-gateway",
            _at_first_hop(401, "signature"),
            "wrong audience at the node",
        ),
        (
            e2e._entitlements,
            "call gateway --token out-gw",
            {
                "status": 401,
                "hops": [{"policy": "off"}, {"refused": "entitlement"}],
            },
            "outside: gateway passes it on, node answers 403, not 401",
        ),
        (
            e2e._refresh,
            "show user",
            {"refresh_token": "absent"},
            "login returned a refresh token",
        ),
        (
            e2e._loops,
            "call gateway --token to-gateway --hop-limit 0",
            {"status": 200},
            "limit 0 at the gateway: 508",
        ),
    ],
)
def test_scenarios_notice_wrong_results(
    run: Run,
    scenario: Callable[[Run, Callable[[str], dict[str, Any]]], None],
    prefix: str,
    result: dict[str, Any],
    failure: str,
) -> None:
    """A result that isn't the expected one fails exactly its check."""
    scenario(run, script({prefix: result}))
    assert run.failures == [failure]


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """Make `e2e` use a fake instead of the mock.

    Args:
        monkeypatch: Pytest's monkeypatch.

    Returns:
        Fake provider.
    """
    provider = FakeProvider(MOCK_ISSUER)
    monkeypatch.setattr(e2e, "create_http", lambda _settings: provider)
    return provider


def _session_for_gaps(settings: Settings, provider: FakeProvider) -> ScriptedSession:
    """Create a session with a real token for the gap checks.

    Args:
        settings: Settings.
        provider: Fake provider.

    Returns:
        Session.
    """
    session = ScriptedSession(settings)
    session.tokens["gap"] = TokenResponse(access_token=provider.mint())
    return session


def test_mock_gaps_shows_what_the_mock_accepts(
    run: Run, mock_settings: Settings, fake_http: FakeProvider
) -> None:
    """A mock that accepts everything passes the gap checks."""
    session = _session_for_gaps(mock_settings, fake_http)
    e2e._mock_gaps(run, session)  # type: ignore[arg-type]
    assert run.failures == []
    assert fake_http.posts[-1][1]["audience"] == ["tx-node"]


def test_mock_gaps_notices_a_stricter_mock(
    run: Run, mock_settings: Settings, fake_http: FakeProvider
) -> None:
    """If the mock starts to refuse wrong secrets, the check fails: docs need it."""
    session = _session_for_gaps(mock_settings, fake_http)
    fake_http.token_error = FakeResponse(401, {"error": "invalid_client"})
    e2e._mock_gaps(run, session)  # type: ignore[arg-type]
    assert run.failures == ["mock accepts: wrong client secret"]


def test_docs_commands_reads_the_prompts(docs: Path) -> None:
    """Only lines with the prompt count, in the order of the pages."""
    (docs / "session.md").write_text("tb> one\nnot tb> two\n  tb> three\ntb> four\n")
    assert e2e.docs_commands(docs, ("session.md",)) == ["one", "four"]


def test_docs_commands_pass(
    run: Run,
    mock_settings: Settings,
    fake_http: FakeProvider,
    docs: Path,
    tmp_path: Path,
) -> None:
    """Commands that run pass, also if their result is a refusal."""
    (docs / "session.md").write_text(
        "tb> clients\ntb> wait-expiry never\ntb> show ro-a\n"
    )
    e2e._docs_commands(run, mock_settings, tmp_path / "record", docs)
    assert run.count == len(e2e.PAGE_GROUPS)
    assert run.failures == []
    assert fake_http is not None


@pytest.mark.parametrize(
    "page", ["tb> show nothing\n", "tb> nonsense\n", "No prompt\n"]
)
def test_docs_commands_fail(
    run: Run,
    mock_settings: Settings,
    fake_http: FakeProvider,
    docs: Path,
    tmp_path: Path,
    page: str,
) -> None:
    """Commands that can't run fail, and so does a page group without commands."""
    (docs / "session.md").write_text(page)
    e2e._docs_commands(run, mock_settings, tmp_path / "record", docs)
    assert len(run.failures) == 1
    assert "session.md" in run.failures[0]
    assert fake_http is not None


def test_leak_scan(run: Run, tmp_path: Path, provider: FakeProvider) -> None:
    """Tokens and secrets anywhere in the output fail the scan."""
    record = tmp_path / "record"
    record.write_text(USER)
    e2e._leak_scan(run, record)
    assert run.failures == []
    run.output.append(provider.mint())
    run.output.append(DUMMY_SECRET)
    e2e._leak_scan(run, record)
    assert run.failures == ["no JWT in any output", "no client secret in any output"]


def test_run_scenarios_runs_all_of_them(
    mock_settings: Settings,
    fake_http: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
    docs: Path,
    tmp_path: Path,
) -> None:
    """A whole run with the expected results passes."""
    monkeypatch.setattr(
        e2e,
        "Session",
        lambda settings, *_args, **_options: _session_for_gaps(settings, fake_http),
    )
    run = e2e.run_scenarios(mock_settings, [], tmp_path / "record", docs)
    assert run.failures == []
    assert run.count > 40
    assert fake_http is not None


def test_ports_in_use() -> None:
    """A port with a listener is reported; a free one isn't."""
    with socket.socket() as listener:
        listener.bind(("localhost", 0))
        listener.listen()
        taken = listener.getsockname()[1]
        with socket.socket() as other:
            other.bind(("localhost", 0))
            free = other.getsockname()[1]
        assert e2e.ports_in_use([taken, free]) == [taken]


class FakeServices:
    """Stands in for `testbed.launcher.Services`.

    Attributes:
        stopped: Whether the services were stopped.
    """

    stopped = False

    def __init__(self, _settings: Settings, _output: Callable[[str], None]) -> None:
        """Create the services.

        Args:
            _settings: Settings.
            _output: Receives output.
        """
        type(self).stopped = False

    def wait_until_healthy(self) -> None:
        """Return at once."""

    def stop(self) -> None:
        """Record that the services were stopped."""
        type(self).stopped = True


def _finished_run(failures: list[str]) -> Callable[..., Run]:
    """Create a stand-in for `run_scenarios`.

    Args:
        failures: Failures of the run.

    Returns:
        Function that writes a harmless record and returns the run.
    """

    def run_scenarios(
        _settings: Settings, output: list[str], record: Path, _docs: Path
    ) -> Run:
        """Finish a run.

        Args:
            _settings: Settings.
            output: Output of the run.
            record: File of the record.
            _docs: Folder of the docs.

        Returns:
            The run.
        """
        record.write_text(USER)
        finished = Run(output)
        for name in failures:
            finished.check(name, False)
        return finished

    return run_scenarios


@pytest.fixture
def main_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Replace what `main()` starts.

    Args:
        monkeypatch: Pytest's monkeypatch.

    Returns:
        The monkeypatch, for more.
    """
    monkeypatch.setattr(e2e, "Services", FakeServices)
    monkeypatch.setattr(e2e, "ports_in_use", lambda _ports: [])
    return monkeypatch


def test_main_reports_a_passed_run(
    main_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A passed run ends normally, says so, and stops the services."""
    main_env.setattr(e2e, "run_scenarios", _finished_run([]))
    e2e.main()
    assert "checks passed in" in capsys.readouterr().out
    assert FakeServices.stopped


def test_main_fails_with_failed_checks(
    main_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Failed checks are listed and fail the run."""
    main_env.setattr(e2e, "run_scenarios", _finished_run(["broken check"]))
    with pytest.raises(SystemExit) as stop:
        e2e.main()
    assert stop.value.code == 1
    assert "FAILED:\n  broken check" in capsys.readouterr().out


def test_main_aborts_on_errors_and_shows_service_logs(
    main_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Errors abort the run, with the logs of the services."""

    def fail(_settings: Settings, output: list[str], *_args: Any) -> Run:
        """Fail like a run without its docs.

        Args:
            _settings: Settings.
            output: Output of the run.
            *_args: Ignored.

        Raises:
            OSError: Always.
        """
        output.extend(["[node] log line", "other line"])
        raise OSError("No such file")

    main_env.setattr(e2e, "run_scenarios", fail)
    with pytest.raises(SystemExit) as stop:
        e2e.main()
    assert stop.value.code == 2
    output = capsys.readouterr().out
    assert "Run aborted: OSError: No such file" in output
    assert "[node] log line" in output
    assert "other line" not in output
    assert FakeServices.stopped


def test_main_refuses_taken_ports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Results would come from other services, so the run doesn't start."""
    monkeypatch.setattr(e2e, "ports_in_use", lambda _ports: [18991])
    with pytest.raises(SystemExit) as stop:
        e2e.main()
    assert stop.value.code == 2
    assert "Ports in use: [18991]" in capsys.readouterr().out
