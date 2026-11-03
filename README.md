# Token exchange testbed

A small client, gateway and node for trying per-hop OAuth 2.0 token exchange with LS Login, on a local machine, without public hosting. It tests the design proposed in [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391), for the chain of ELIXIR On-Cloud services: Krini -> Conquest -> proTES -> TES nodes. Each service exchanges the token it received for one meant only for the next service.

> [!WARNING]
> **Nothing has run against LS Login yet.** All commands have only run against a local mock. The mock accepts almost everything, so in local runs the testbed enforces LS Login's rules itself, as the LS Login team described them. A passing run shows that this code works, and says nothing about how LS Login behaves.

## Quick start

Needs Docker with Compose, on Linux, macOS or WSL. So far it has only been run on Linux. No Python on your machine, and no free ports.

```sh
git clone <URL of this repository> token_exchange_flow_testbed
cd token_exchange_flow_testbed
docker compose build
docker compose run --rm e2e
docker compose down -v
```

It ends with `51/51 checks passed`: the mock, the services and the session, through all scenarios and all commands of the docs.

## Docs

Written for Read the Docs (MkDocs Material), and readable here as Markdown.

- [Home](docs/index.md)
- Concepts: [the flow](docs/concepts/flow.md), [what LS Login requires](docs/concepts/ls-login.md), [what can't work yet](docs/concepts/limits.md)
- Tutorial: [overview](docs/tutorial/index.md), [prepare accounts and clients](docs/tutorial/prepare.md), [run against the mock](docs/tutorial/mock.md), [run against LS Login](docs/tutorial/ls-login.md), [refused cases](docs/tutorial/refused.md)
- Reference: [commands](docs/reference/commands.md), [settings](docs/reference/settings.md), [what the mock can't show](docs/reference/mock.md)
- [Open questions](docs/open-questions.md), for the LS Login team
- [Session with the LS Login team](docs/session.md)
- [Optional: remote machines](docs/remote.md), untested
- [Development](docs/development.md)

## Status

A testbed, never for production. Next: register test clients and run the [tutorial](docs/tutorial/index.md) against LS Login, which will answer many of the [open questions](docs/open-questions.md). The goal after that is auth documentation and a tutorial for the "Architects & Operators" section of the ELIXIR On-Cloud docs, in more generic form.

## Licence

[Apache-2.0](LICENSE)
