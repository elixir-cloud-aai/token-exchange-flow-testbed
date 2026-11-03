# Token exchange testbed

A small client, gateway and node for trying per-hop OAuth 2.0 token exchange with LS Login, on a local machine, without public hosting. It tests the design proposed in [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391), for the chain of ELIXIR On-Cloud services: Krini -> Conquest -> proTES -> TES nodes.

> [!WARNING]
> **Nothing has run against LS Login yet.** The `tb>` lines of the docs were executed on a local mock, except for `wait-expiry`, and some only up to a refusal or usage error. The mock accepts almost everything, so in local runs the testbed enforces LS Login's rules itself, as the LS Login team described them on 2026-11-03. A passing run shows that this code works, and says nothing about how LS Login behaves.

## Quick start

Needs Docker with Compose, on Linux, macOS or WSL. So far it has only been run on Linux. No Python on your machine, and no free ports.

```sh
git clone https://github.com/elixir-cloud-aai/token-exchange-flow-testbed.git
cd token-exchange-flow-testbed
docker compose build
docker compose run --rm e2e
docker compose down -v
```

It ends with `N/N checks passed`, with the same number twice.

## Links

Docs are written for Read the Docs (MkDocs Material), and readable here as Markdown.

- [Home](docs/index.md)
- [Background](docs/background/use-case.md): use case, requirements and design, independent of any product
- [Testbed](docs/testbed/index.md): scope, assumptions and limits
- Setup
- Tests, with the questions for the LS Login team
- Outcomes: empty until the tests have run
- About

Licence: [Apache-2.0](LICENSE). Never for production.
