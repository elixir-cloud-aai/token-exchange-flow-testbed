# Testbed limits

What this testbed can and can't show, compared to the [Design](../background/design.md). These are limits of the testbed and of what can be observed with it. They aren't findings: findings go in the Gap analysis, after the tests have run.

## Each design point

| Design point | What the testbed can show | What it can't, and why |
|---|---|---|
| [An identity provider, verified by each service](../background/design.md#trust-model) | Each service validates for itself, as in FOCA | Federations of identity providers: out of scope |
| [Authorization code with PKCE](../background/design.md#authentication) | A real login, against LS Login | On the mock, the login form is filled in for you, so no browser is involved |
| [Device flow](../background/design.md#authentication) | Against LS Login, if the client has it registered | On the mock: it has none. Never run so far, there are only unit tests with a fake |
| [Public portal](../background/design.md#authentication) | Whether LS Login lets a public client exchange | On the mock: it refuses exchange without a client secret |
| [Token per hop](../background/design.md#delegation-across-hops) | The whole chain, with stand-ins for the services | Real services: these only validate, exchange, forward and report |
| [Resource indicators](../background/design.md#delegation-across-hops) | Whether LS Login accepts bare client IDs or URLs | On the mock: it ignores `audience` and `resource`, unless a mapping says otherwise |
| [`act` and `may_act`](../background/design.md#delegation-across-hops) | That they're absent, as expected from [C1](assumptions.md#constraints) | That they work: neither LS Login nor the mock issues them |
| [Refresh token from an exchange](../background/design.md#delegation-across-hops) | Whether LS Login issues one | On the mock: it never does. The 31-day limit itself can't be waited for, only compared at two points in time |
| [Lifetimes per service](../background/design.md#delegation-across-hops) | What the lifetimes are today | Setting them: [C5](assumptions.md#constraints). On the mock, they follow `mock/oidc.json` |
| [Entitlements per service](../background/design.md#authorization) | What each client gets at user info and introspection | On the mock: user info just returns the token's claims |
| [Each node's own policy](../background/design.md#authorization) | One node with one required value | Several nodes with different policies: one node is enough for what's being asked |
| [Provenance](../background/design.md#attribution) | Whether a node can tell the paths apart today | Provenance from a token: no `act` |
| [Accounting](../background/design.md#attribution) | What `sub` and `client_id` hold at each hop | Attribution to a portal or workflow system, without `act` |
| [Tracing](../background/design.md#attribution) | `traceparent` across all hops, and the hop limit | Signed tracing: both are headers that any hop can reset. They stop accidental loops and help with tracing, and prove nothing |

## What the mock can't show

The mock is [`mock-oauth2-server`](https://github.com/navikt/mock-oauth2-server) 6.0.7. It supports the token exchange grant, but it's not LS Login. All of this was seen in probes, and most of it is checked again in each end-to-end run, in the section `MOCK GAP`.

It **accepts:** a subject token without the exchanging client in `aud`, for an unregistered target, expired, or with a broken signature, and any client secret. A refresh token can be redeemed by any client.

It **ignores** `audience` and `resource`, unless a mapping says otherwise. `aud` and `client_id` after an exchange come from **our** `mock/oidc.json`, so they're no evidence. Only one target ends up in `aud`.

It **refuses** exchange without a client secret (`invalid_request`), so public clients can't be shown.

It **doesn't have:**

- `act` (`actor_token` is ignored);
- refresh tokens from exchanges (`requested_token_type` is ignored), rotation, or idle and absolute limits;
- entitlements per client: user info just returns the token's claims, whereas LS Login has them in user info or introspection ([A5](assumptions.md#assumptions));
- a device flow;
- a separate `typ` for ID tokens.

## What hasn't run

**Everything against LS Login: no test has ever run there.** Its discovery document was read, which is public and needs no credentials. A local run shows that our code works and handles refusals, not that LS Login behaves as expected.

Beyond that:

- **Executed on the mock, not as a success:** the `tb>` lines of these docs are executed in each end-to-end run, except for `wait-expiry`, which takes as long as tokens live. Many of them end in a refusal, which counts as passing there. Those that need a refresh token from an exchange end in a usage error, which also counts.
- **Never run at all, on the mock or elsewhere:** the real browser login (the mock run fills in its login form), `--flow device` (unit tests with a fake only), the public client's exchange, a refresh token from an exchange, a real rotation, entitlements that differ by client.
- **Ran on the mock, but the results are no evidence:** `client_id`, `aud`, lifetimes and refresh tokens. In the mock, these follow our own `mock/oidc.json`.
- **Refusals** of a subject without our client in `aud`, unregistered targets, tampered and expired subjects come from the testbed's own rules on the mock, with made-up error codes.
- **`compose.lslogin.yaml`:** no automated test or CI job uses it. It's been started by hand with made-up client IDs, for `clients` and `discovery` only, and restarting the services with a session open has been tried, as has a request from the host reaching the callback. No login or exchange has gone through it.
- **The registration instructions:** we haven't gone through the whole app, so its fields may differ.
- **Platforms:** the Docker path has only run on Linux. macOS and WSL are expected to work, as nothing in it is specific to Linux, but haven't been tried. That includes a browser on the host returning to the published callback port.
