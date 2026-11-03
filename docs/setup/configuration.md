# Configuration

The mock needs no configuration. For LS Login, copy the template, then fill in `lslogin.env` with an editor:

```sh
cp lslogin.env.example lslogin.env
```

It's git-ignored and the image build doesn't see it: Compose passes it to the containers at runtime only. It holds client secrets, so keep it private, and delete it after the event. Put a secret in single quotes if it holds `$`, `#` or spaces, as Compose otherwise changes it without an error.

## Settings

All settings are environment variables.

| Variable | Meaning | Default |
|---|---|---|
| `TESTBED_PROVIDER` | `mock` or `lslogin` | `mock` |
| `TESTBED_NODE_CLIENT_ID` | Client ID of the node; required for LS Login | |
| `TESTBED_GATEWAY_CLIENT_ID` | Client ID of the gateway; required for LS Login | |
| `TESTBED_ORCHESTRATOR_CLIENT_ID` | Client ID of the orchestrator; required for LS Login | |
| `TESTBED_CLIENT_CLIENT_ID` | Client ID of the client; required for LS Login | |
| `TESTBED_PUBLIC_CLIENT_ID` | Client ID of the public client | |
| `TESTBED_NODE_CLIENT_SECRET` | Secret of the node, for introspection | |
| `TESTBED_GATEWAY_CLIENT_SECRET` | Secret of the gateway | |
| `TESTBED_ORCHESTRATOR_CLIENT_SECRET` | Secret of the orchestrator | |
| `TESTBED_CLIENT_CLIENT_SECRET` | Secret of the client | |
| `TESTBED_NODE_RESOURCE` | Resource indicator of the node in URL form, as registered | |
| `TESTBED_GATEWAY_RESOURCE` | The same for the gateway | |
| `TESTBED_ORCHESTRATOR_RESOURCE` | The same for the orchestrator | |
| `TESTBED_REQUIRED_ENTITLEMENT` | The value that the node's policy requires, from any entitlement or capability; empty for no policy. `ECP_CLN` in the template is an example | On the mock: a made-up one |
| `TESTBED_TARGET_PARAM` | How services name their next hop in exchanges: see below | `audience` |
| `TESTBED_EXCHANGE_SCOPE` | `scope` that services request in exchanges; empty for none | |
| `TESTBED_ISSUER` | Issuer, exactly as in tokens. For trying another stack, e.g., `https://login.aai.lifescience-ri.eu/cas/oidc` (never tried) | `https://login.aai.lifescience-ri.eu/oidc/` |
| `TESTBED_ALGORITHMS` | Accepted signature algorithms, comma-separated | `RS256` |
| `TESTBED_CALLBACK_BIND` | Address that the login callback listens on. `compose.lslogin.yaml` sets it, as published ports don't arrive on a container's loopback interface | `localhost` |
| `TESTBED_DOCS` | Folder of the docs, for the end-to-end run. The image sets it | `docs` |

Values of `TESTBED_TARGET_PARAM`:

| Value | `audience` | `resource` |
|---|---|---|
| `audience` | Client ID | |
| `resource` | | Client ID |
| `resource-url` | | URL form |
| `both` | Client ID | URL form |

## Changing settings during a session

After editing `lslogin.env`, this restarts the services only. Open sessions keep their tokens, but read their own settings only when they start.

```sh
docker compose -f compose.lslogin.yaml up -d --force-recreate --no-deps --wait services
```

## Results {#results}

`--record /results/<file>` appends decoded results to `results/<file>` in the repository's folder. There are no tokens in it, but it does hold the claims of the accounts used, so use test accounts only, and delete it when done.

The session's container runs as user 1000. On Linux, if your user has another ID, a session with `--record` says that it can't write the file. Pass your IDs:

```sh
TESTBED_UID=$(id -u) TESTBED_GID=$(id -g) docker compose run --rm session --record /results/session.jsonl
```

This is for Bash and Zsh. In other shells, set the two variables as your shell does it.
