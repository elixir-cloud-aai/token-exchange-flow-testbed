# Testbed

## Intro

The [Background](../background/use-case.md) describes an end state. This testbed checks how much of it works today, with a real identity provider: [LS Login](https://lifescience-ri.eu/ls-login/), for the chain of [ELIXIR On-Cloud](https://elixir-on.cloud/) services, Krini -> Conquest -> proTES -> TES nodes.

[proTES issue #391](https://github.com/elixir-cloud-aai/proTES/issues/391) proposes making proTES a thin gateway that holds no stored credentials: each service exchanges the token it received for one meant for the next service. That is a proposal, not a decision. It stands or falls with how LS Login behaves, and several details aren't known. The testbed makes them observable, one command at a time, and records the decoded results.

!!! warning "Status: nothing has run against LS Login yet"
    The `tb>` lines of these docs were executed on a local mock, except for `wait-expiry`, and some only up to a refusal or usage error. **The mock accepts almost everything**, so in local runs the testbed itself enforces LS Login's rules, as the LS Login team described them on 2026-11-03. A passing run shows that this code works and handles refusals. It says nothing about how LS Login behaves. See [Testbed limits](limits.md).

## Scope

**In scope:**

- Per-hop token exchange against LS Login, through the real protocol, with stand-ins for the services.
- Standard validation of the resulting tokens, as in [FOCA](https://github.com/elixir-cloud-aai/foca), and a group policy at the node.
- Refusals, token lifetimes and refresh, and what a node can tell about the path of a request.
- Everything needed to repeat this on a local machine, without public hosting.

**Out of scope:**

- Real TES or WES behaviour: the services only validate, exchange, forward and report.
- Krini, Conquest, proTES or a TES implementation themselves.
- Production use. The testbed reports why it refused a token, shows decoded claims and keeps no state, all of which is fine here and nowhere else.
- Real data of any kind, and real accounts: test accounts only.
- Performance and load.
