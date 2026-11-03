"""Tests of the docs: commands and settings must exist and be documented."""

import re
import shlex
from pathlib import Path

import pytest

from testbed.e2e import PAGE_GROUPS, docs_commands
from testbed.session import _build_parser

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
PROMPT = re.compile(r"^tb> ", flags=re.MULTILINE)


def test_every_page_with_commands_runs_in_the_end_to_end_run() -> None:
    """Pages with session commands are in a page group, and only those."""
    with_commands = {
        str(page.relative_to(DOCS))
        for page in DOCS.rglob("*.md")
        if PROMPT.search(page.read_text(encoding="utf-8"))
    }
    assert with_commands == {page for pages in PAGE_GROUPS for page in pages}


@pytest.mark.parametrize("pages", PAGE_GROUPS, ids=" ".join)
def test_all_commands_in_the_docs_parse(pages: tuple[str, ...]) -> None:
    """Every `tb>` line of the docs is a valid session command."""
    lines = docs_commands(DOCS, pages)
    assert len(lines) > 10
    parser = _build_parser()
    for line in lines:
        parser.parse_args(shlex.split(line))


def test_all_session_commands_are_documented() -> None:
    """The reference lists each command of the session."""
    reference = (DOCS / "about" / "commands.md").read_text(encoding="utf-8")
    help_text = _build_parser().format_help()
    match = re.search(r"\{(.+?)\}", help_text)
    assert match is not None
    for command in match[1].split(","):
        assert re.search(rf"^\| `{command}\b", reference, flags=re.MULTILINE), command


def test_all_settings_are_read_and_documented() -> None:
    """Each variable of the template and the code is in the reference."""
    template = (ROOT / "lslogin.env.example").read_text(encoding="utf-8")
    in_template = set(re.findall(r"^(TESTBED_\w+)=", template, flags=re.MULTILINE))
    assert "TESTBED_NODE_CLIENT_SECRET" in in_template
    code = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py")
    )
    in_code = set(re.findall(r"\"(TESTBED_\w+)\"", code))
    reference = (DOCS / "setup" / "configuration.md").read_text(encoding="utf-8")
    for name in in_template | in_code:
        assert f"`{name}`" in reference, name
    for name in in_template:
        role_setting = re.fullmatch(
            r"TESTBED_(NODE|GATEWAY|ORCHESTRATOR|CLIENT|PUBLIC)_\w+", name
        )
        assert role_setting or name in code, name


def test_template_holds_no_values_of_secrets_or_clients() -> None:
    """Client IDs and secrets stay empty in the template."""
    template = (ROOT / "lslogin.env.example").read_text(encoding="utf-8")
    for name, value in re.findall(
        r"^(TESTBED_\w+_CLIENT_(?:ID|SECRET))=(.*)$", template, flags=re.MULTILINE
    ):
        assert value == "", name


@pytest.mark.parametrize(
    "pattern", ["**/.env", "**/.env.*", "**/*.env", "**/*.env.*", "**/results"]
)
def test_image_builds_never_see_secrets_or_results(pattern: str) -> None:
    """The build context excludes env files, after the lines that allow files."""
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert pattern in lines
    assert lines.index(pattern) > lines.index("!src")


def test_git_ignores_secrets_and_results() -> None:
    """Env files and results are never committed."""
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert {"*.env", ".env", ".env.*", "results/*"} <= set(lines)
