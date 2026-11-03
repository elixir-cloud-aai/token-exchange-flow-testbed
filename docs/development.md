# Development

Only for working on the testbed itself: running it needs nothing but Docker. This path uses [uv](https://docs.astral.sh/uv/) and Python 3.13.

```sh
uv sync --extra dev --extra docs
uv run pre-commit install
```

## Checks

CI runs the same (`.github/workflows/ci.yml`), and needs no secrets.

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pre-commit run --all-files
uv run mkdocs build --strict
```

Tests must keep 100% line and branch coverage (`pyproject.toml`). The only exclusion is `if __name__ == "__main__":`. Semgrep runs with the public rule set `p/python`, which it downloads, and ast-grep has no rules yet (`sgconfig.yml`).

Tests of the docs (`tests/test_docs.py`) check that all `tb>` lines are valid commands, and that all commands and settings are documented. The end-to-end run also runs these lines. So commands in the docs are always written at the start of a line in a code block, with the prompt `tb> `. A new page with such lines goes into `PAGE_GROUPS` in `src/testbed/e2e.py`.

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

## Why the containers share a network namespace

Everything talks over `localhost`, in containers as on a host, so tokens have the same issuer in both, and a browser's redirect URI stays the same. In `compose.yaml`, `mock` holds the namespace. In `compose.lslogin.yaml`, the service `network` does, so that `services` can be recreated with new settings while a session keeps its tokens in memory.

## Mock configuration

`mock/oidc.json` sets what the mock puts in tokens. Remember that this is why `aud` and `client_id` look right on the mock: see What the mock can't show.

If a `MOCK GAP` check starts to fail, the mock's behaviour changed: update that page and the tutorial.
