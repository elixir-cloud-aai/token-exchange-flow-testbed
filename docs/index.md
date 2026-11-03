# Token exchange testbed

A small client, gateway and node for trying per-hop OAuth 2.0 token exchange with [LS Login](https://lifescience-ri.eu/ls-login/), on a local machine, without public hosting. It exists to answer one question: can the chain of ELIXIR On-Cloud services, Krini -> Conquest -> proTES -> TES nodes, carry a user's identity with tokens that are only good for the next service?

It's also the start of a blueprint: for how people and services prove who they are, and what they may do, in federated analysis across WES and TES nodes.

## Status

!!! warning "Nothing has run against LS Login yet"
    The `tb>` lines of these docs were executed on a local mock, except for `wait-expiry`, and some only up to a refusal or usage error. **The mock accepts almost everything**, so in local runs the testbed itself enforces LS Login's rules, as the LS Login team described them on 2026-11-03. A passing run shows that this code works and handles refusals. It says nothing about how LS Login behaves. See [Testbed limits](testbed/limits.md).

This is a testbed and never for production: it reports why it refused a token, shows decoded claims and keeps no state. The Outcomes are empty until the tests have run.

## Quick start

Takes about 5 minutes. It needs Docker with Compose on Linux, macOS or WSL, and has been run on Linux only so far. No Python on your machine, no free ports, no account.

```sh
git clone https://github.com/elixir-cloud-aai/token-exchange-flow-testbed.git
cd token-exchange-flow-testbed
docker compose build
docker compose run --rm e2e
docker compose down -v
```

It ends with `N/N checks passed`, with the same number twice: the mock, the services and the session, through all scenarios and all commands of the docs.

## Reading paths

- **To understand the idea:** [Use case](background/use-case.md), [Requirements](background/requirements.md), [Design](background/design.md). These don't depend on any product.
- **To see what's being tested, and why:** [Testbed](testbed/index.md), then [Assumptions and constraints](testbed/assumptions.md) for what we know about LS Login.
- **To try it on your machine:** [Checking the setup](setup/checking.md), by hand against the mock.
- **To run it against LS Login, or for the LS Login team:** [Tests](tests/index.md), for the tests, their order and all questions.
- **To look something up:** [Commands](about/commands.md), [Configuration](setup/configuration.md), [Glossary](about/glossary.md), [References](about/references.md).
