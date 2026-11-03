# What can't work yet

## No `act`

RFC 8693 lets an exchanged token say who is acting for the user, with a nested [`act` claim](https://datatracker.ietf.org/doc/html/rfc8693#section-4.1). LS Login doesn't support it for now, and is considering it for its new stack. What's left in the token is `sub`, the user, and `aud`, the next service. At best, `client_id` names the last caller, and what it holds after an exchange is itself [an open question](../open-questions.md).

### Why it matters

A node can't tell which services a request came through. The testbed shows this directly: `compare` on a direct call and a call through the orchestrator gives the same claims at the node, on the mock at least.

- **Provenance:** a record of how a task reached a node can't be read from the token. Whether Conquest was involved is invisible.
- **Accounting:** usage can't be attributed to a portal or workflow system from the token alone.
- **Loop detection by identity:** a gateway can't find itself in the chain, so it can't refuse by identity.

### What we use instead

From [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391):

- A **hop limit** in a request header stops loops.
- **W3C `traceparent`** across hops allows tracing afterwards, from each service's logs.

Neither is signed, so any hop can reset them. They stop accidental loops and help with tracing. They prove nothing.

### What we'd ask for

Nested `act` in the new stack, set by LS Login from the exchanging client, as only it can vouch for that. Later `may_act` or `can_act`, for restricting who may act. Our chain is a concrete use case for it.

## Also not possible for now

- **Lifetimes can't be set per service.** The LS Login team says that comes with the new stack, as do refresh token lifetimes per service.
- **Targets can't be added without registration.** They're listed per client, so proTES's client lists every TES node, by hand for now. Automating this, e.g., through the Cloud Registry, depends on [whether there's an API](../open-questions.md).
- **FOCA doesn't exchange yet.** Outgoing exchange per target audience is planned in FOCA. The testbed has its own small implementation.

The new proxy stack may change the `aud` rule, `act` and lifetimes, so nothing here should be hard-coded in FOCA or proTES.
