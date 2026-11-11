# Contributing and development

Contributions are welcome by pull request. Use test accounts only, and never add client IDs, secrets, tokens or real user data.

Only for working on the testbed itself: running it needs nothing but Docker. This path uses [uv](https://docs.astral.sh/uv/) and Python 3.13.

```sh
uv sync --extra dev --extra docs
uv run pre-commit install
```

## Checks

CI runs the same (`.github/workflows/ci.yml`), and needs no secrets.

Unit tests use a temporary login callback port, so an LS Login session on port 18994 can stay running.

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pre-commit run --all-files
uv run mkdocs build --strict
```

Tests must keep 100% line and branch coverage (`pyproject.toml`). The only exclusion is `if __name__ == "__main__":`. Semgrep runs with the public rule set `p/python`, which it downloads, and ast-grep has no rules yet (`sgconfig.yml`).

Tests of the docs (`tests/test_docs.py`) check that all `tb>` lines are valid commands, and that all commands and settings are documented. The end-to-end run also runs these lines. So commands in the docs are always written at the start of a line in a code block, with the prompt `tb> `. A new page with such lines goes into `PAGE_GROUPS` in `src/testbed/e2e.py`. They also check the layering of the docs: see "Rules for these docs" below.

## End to end, without the image

Publish the mock on the loopback interface, and run on the host. This needs the ports 18990 to 18995:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait mock
uv run testbed-e2e
docker compose -f compose.yaml -f compose.dev.yaml down -v
```

By hand, with the services and a session in two terminals:

```sh
uv run testbed-services --provider mock
uv run testbed-session --provider mock
```

Against LS Login, uv can read the same settings, in any shell. The callback then listens on `localhost`, without Docker:

```sh
uv run --env-file lslogin.env testbed-services
uv run --env-file lslogin.env testbed-session --record results/session.jsonl
```

## Mock configuration

`mock/oidc.json` sets what the mock puts in tokens. Remember that this is why `aud` and `client_id` look right on the mock: see [What the mock can't show](../testbed/limits.md#what-the-mock-cant-show).

If a `MOCK GAP` check starts to fail, the mock's behaviour changed: update that page and the tests.

## Rules for these docs

- The Use case names no technology, the Requirements no solution, and the Design no LS Login, so that the Background can move elsewhere later.
- LS Login specifics go in [Assumptions and constraints](../testbed/assumptions.md). Links to the operator's docs only go there, under Setup, and in the [References](references.md).
- Section 5, Outcomes, only holds what results support, as drafts.
