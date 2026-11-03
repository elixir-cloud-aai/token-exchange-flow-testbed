# Token exchange testbed

A small client, gateway and node for trying per-hop OAuth 2.0 token exchange with [LS Login](https://lifescience-ri.eu/ls-login/), on a local machine, without public hosting. It exists to answer one question: can the chain of ELIXIR On-Cloud services, Krini -> Conquest -> proTES -> TES nodes, carry a user's identity with tokens that are only good for the next service?

!!! warning "Status: nothing has run against LS Login yet"
    All commands have only run against a local mock. **The mock accepts almost everything**, so in local runs the testbed itself enforces LS Login's rules, as the LS Login team described them. A passing run shows that this code works and handles refusals. It says nothing about how LS Login behaves. See What the mock can't show.

## Why

[proTES issue #391](https://github.com/elixir-cloud-aai/proTES/issues/391) proposes making proTES a thin gateway that holds no stored credentials: each service exchanges the token it received for one meant for the next service. The proposal stands or falls with how LS Login behaves, and several details aren't known. The testbed makes them observable, one command at a time, and records the decoded results. It stands in for the real services:

| Testbed role | Stands for | Does |
|---|---|---|
| `client` | Krini with a backend | Logs in the user, exchanges for the first service |
| `public` | Krini without a backend | The same, as a public client |
| `orchestrator` | Conquest | Validates, exchanges, forwards |
| `gateway` | proTES | Validates, exchanges, forwards |
| `node` | A TES node | Validates, applies its own policy, reports |

The group policy at the node uses `ECP_CLN` as a configurable example.

## Where to go

- **Concepts:** the flow, what LS Login requires, and what can't work yet.
- **[Tutorial](tutorial/index.md):** accounts and clients, the mock first, then LS Login.
- **[Reference](reference/commands.md):** commands, settings, and the limits of the mock.
- **[Open questions](open-questions.md):** everything we don't know, for the LS Login team, with what each answer changes.
- **[Session with the LS Login team](session.md):** the sequence for the planned hands-on session.

## What's needed

Docker with Compose on Linux, macOS or WSL. It has been run on Linux only so far. The LS Login path also needs test accounts and registered clients. No public hosting is involved: LS Login only sees your browser and the testbed's outgoing requests.

This is a testbed and never for production: it reports why it refused a token, shows decoded claims and keeps no state.
