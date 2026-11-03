# Testbed commands

## Starting things

All from the repository's folder, in any shell. For LS Login, add `-f compose.lslogin.yaml` after `docker compose`. All but `e2e` work with both.

| Command | Does |
|---|---|
| `docker compose build` | Builds the image |
| `docker compose run --rm e2e` | Runs all scenarios against the mock (mock only) |
| `docker compose up -d --wait services` | Starts the services |
| `docker compose logs -f services` | Shows the services' logs: decoded claims only |
| `docker compose run --rm session` | Starts a session |
| `docker compose run --rm session --record /results/<file>` | The same, keeping results in `results/<file>` |
| `docker compose down -v` | Removes everything |

`e2e` refuses to start while `services` is running, as it starts its own.

## Services and ports

Inside the containers' shared network namespace:

| Role | Port |
|---|---|
| Mock (mock only) | 18990 |
| `gateway` | 18991 |
| `node` | 18992 |
| `orchestrator` | 18993 |
| Login callback | 18994 |
| `loop` (mock only: its own next hop) | 18995 |

Only the login callback is published on the host, on `127.0.0.1`, and only for LS Login.

Each service has `GET /report`, with the token as a bearer token, and `GET /healthz`.

## Session commands

Results are JSON. `ok` says whether the request succeeded; refusals are results, too. They're decoded claims, never tokens or secrets. Lines starting with `#` are ignored.

Tokens are kept under names you choose. Targets in `--audience` and `--resource` can be shorthands:

| Shorthand | Stands for |
|---|---|
| `@<role>` | The client ID of a role, e.g., `@gateway` |
| `@<role>.url` | Its resource indicator in URL form |
| `@unregistered` | A target that no client has registered |

| Command | Does | Options |
|---|---|---|
| `clients` | Shows the configured clients, never their secrets | |
| `discovery` | Shows what the provider's discovery document says | |
| `lifetimes` | Shows the lifetimes of all tokens of this session | |
| `login <name>` | Logs in a user via the dummy client | `--as <role>`, `--flow code\|device`, `--scope`, `--resource`, `--no-browser`, `--mock-user inside\|outside`, `--mock-issuer short\|rogue` |
| `exchange <name>` | Exchanges a token; `--as` is the exchanging client | `--as <role>`, `--from <token>`, `--audience`, `--resource`, `--scope`, `--requested-type access\|refresh`, `--auth auto\|basic\|post\|none`, `--tamper-subject`, `--no-rules` |
| `refresh <name>` | Redeems the refresh token held by a token of the session | `--as <role>`, `--from <token>`, `--audience`, `--resource`, `--scope` |
| `credentials <name>` | Gets a client's own token | `--as <role>`, `--scope` |
| `call <service>` | Calls a service with a token and shows what each hop saw | `--token <token>`, `--save <name>`, `--hop-limit`, `--traceparent`, `--tamper`, `--id-token`, `--full` |
| `show <name>` | Shows the decoded claims of a token | |
| `userinfo <name>` | Calls user info with a token; shows released entitlements | |
| `introspect <name>` | Introspects a token as a client | `--as <role>`, `--refresh` |
| `revoke <name>` | Revokes a token as a client | `--as <role>`, `--refresh` |
| `wait-expiry <name>` | Blocks until a token has expired; Ctrl-C ends the wait | `--margin <seconds>` |
| `compare <first> <second>` | Compares what the last hop saw in two saved calls | |
| `help` | Shows the commands | |
| `quit` | Ends the session; all tokens are gone with it | |

Options that only make sense on the mock: `--mock-user`, `--mock-issuer` and `--no-rules`.

## Reasons a service gives

With status 401, `reason` is one of `malformed`, `issuer`, `type`, `provider`, `key`, `signature`, `expired`, `audience` or `claims`. Other statuses:

| Status | Meaning |
|---|---|
| 400 | Invalid `Hop-Limit` |
| 403 | The node's policy: `refused: entitlement` |
| 502 | The next hop couldn't be reached, or the exchange for it was refused: the row shows why |
| 508 | The hop limit is used up |
