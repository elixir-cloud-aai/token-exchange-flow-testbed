# Actors and components

## User

Two test accounts, as sessions record their claims:

- **Account A** inside the group, here `ECP_CLN`.
- **Account B** outside it.

On the mock, these are the made-up users `test-user-inside` and `test-user-outside`.

## Clients and services

Five registered clients stand in for the real chain. Three of them also run as services.

| Role | Stands for | Client | Service | Does |
|---|---|---|---|---|
| `client` | Krini with a backend | `tx-test-client` | | Logs in the user, exchanges for the first service |
| `public` | Krini without a backend | `tx-test-public` | | The same, as a public client |
| `orchestrator` | Conquest | `tx-test-orchestrator` | yes | Validates, exchanges, forwards |
| `gateway` | proTES | `tx-test-gateway` | yes | Validates, exchanges, forwards |
| `node` | A TES node | `tx-test-node` | yes | Validates, applies its own policy, reports |

On the mock, the client IDs are `tx-client` and so on, and there's a sixth, `loop`, which is its own next hop.

## Session

An interactive command line that acts as the clients: it logs in, exchanges and calls services, and holds all tokens in memory. See Commands.

## Mock

[`mock-oauth2-server`](https://github.com/navikt/mock-oauth2-server) 6.0.7, configured by `mock/oidc.json`. It's for learning the commands and for automated runs. See [what it can't show](limits.md#what-the-mock-cant-show).

## LS Login

The identity provider under test, the [Life Science Login](https://lifescience-ri.eu/ls-login/), by way of its [service registration app](https://services.aai.lifescience-ri.eu/). Its rules as we know them are in [Assumptions and constraints](assumptions.md).

## Perun

The identity management system behind LS Login. Facilities, resources, groups and VOs live here, and determine which entitlements a user gets ([A9, A10](assumptions.md)). See Client registration.
