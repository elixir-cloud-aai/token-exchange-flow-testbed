# Settings

All settings are environment variables. For LS Login, they go in `lslogin.env`, a copy of `lslogin.env.example`; Compose passes it to the containers at runtime. It's git-ignored and excluded from image builds. The mock needs none of them.

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
| `TESTBED_TARGET_PARAM` | How services name their next hop in exchanges: `audience`, `resource` or `both` | `audience` |
| `TESTBED_EXCHANGE_SCOPE` | `scope` that services request in exchanges; empty for none | |
| `TESTBED_ISSUER` | Issuer, exactly as in tokens. For trying another stack, e.g., `https://login.aai.lifescience-ri.eu/cas/oidc` (never tried) | `https://login.aai.lifescience-ri.eu/oidc/` |
| `TESTBED_ALGORITHMS` | Accepted signature algorithms, comma-separated | `RS256` |
| `TESTBED_CALLBACK_BIND` | Address that the login callback listens on. `compose.lslogin.yaml` sets it, as published ports don't arrive on a container's loopback interface | `localhost` |
| `TESTBED_DOCS` | Folder of the docs, for the end-to-end run. The image sets it | `docs` |

## Results {#results}

`--record /results/<file>` appends decoded results to `results/<file>` in the repository's folder. There are no tokens in it, but it does hold the claims of the accounts used, so use test accounts only, and delete it when done.

The session's container runs as user 1000. On Linux, if your user has another ID, a session with `--record` says that it can't write the file. Pass your IDs (in Bash and Zsh; in Fish 3.4 or later, too):

```sh
TESTBED_UID=$(id -u) TESTBED_GID=$(id -g) docker compose run --rm session --record /results/session.jsonl
```

## Secrets and personal data

- Tokens exist only in memory, and in the session only for its length. Output, logs and records hold decoded claims, without signatures and with nested tokens (e.g., visas) removed. Refresh tokens are shown as "present".
- Each end-to-end run scans all its output for JWTs and secrets.
- Client secrets only come from the environment. The image has none.
- The mock's fixtures are made-up users. Its signing keys are public defaults: it's for local use only.
