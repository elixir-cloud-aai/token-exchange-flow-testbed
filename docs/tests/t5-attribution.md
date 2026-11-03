# T5 Attribution across hops

## Description

What a node can tell about the path of a request, and how a request can be followed afterwards. Uses the saved calls of [T1](t1-call-chain.md) and a refreshed token of [T4](t4-lifetime.md), in the same session.

From the LS Login team, 2026-11-03: `act` and `can_act` aren't supported, and are under consideration for the new stack ([C1](../testbed/assumptions.md#constraints)). What's left in the token is `sub`, the user, and `aud`, the next service. At best, `client_id` names the last caller.

**Runs against:** both. On the mock, the comparison follows from our `mock/oidc.json`. The hop limit and `traceparent` are the testbed's own, and work the same on both.

## Expectations

1. **Provenance:** direct and through the orchestrator, the node sees the same claims: `identical_at_last_hop: true`, unless `client_id` differs, and `act_present: [false, false]`. So whether the orchestrator was involved can't be read from the token.
2. **Accounting:** usage can't be attributed to a portal or workflow system from the token alone.
3. **Loops:** a gateway can't find itself in the chain, so it can't refuse by identity. A hop limit of 0 gives 508 with `refused: hop limit`. With 1, the gateway forwards, and the next service sees a limit of 0.
4. **Tracing:** all rows of a call have the same `traceparent`, and the services' logs show it.

Hop limit and `traceparent` come from [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391). Neither is signed, so any hop can reset them. They stop accidental loops and help with tracing. They prove nothing.

## Steps

### Provenance and accounting

```text
tb> compare direct chained
```

### Hop limit

A new token, as the one from T1 may have expired, in which case the services answer 401 before they get to the hop limit.

```text
tb> refresh r3 --as client --from r2
tb> exchange to-gw5 --as client --from r3 --audience @gateway
tb> call gateway --token to-gw5 --hop-limit 0
tb> call gateway --token to-gw5 --hop-limit 1
```

### Tracing

```text
tb> call gateway --token to-gw5 --traceparent 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
```

Then look for it in the services' logs:

```sh
docker compose -f compose.lslogin.yaml logs services
```

## Questions it answers

### Is `act` coming?

The chain could then come from nested `act` ([RFC 8693, section 4.1](https://datatracker.ietf.org/doc/html/rfc8693#section-4.1)), set by LS Login from the exchanging client.

- **Yes:** the chain comes from nested `act` claims, and a gateway finding itself in the chain refuses the request. FOCA can read `act` as optional from the start, as that changes nothing today.
- **No:** provenance and accounting stay in logs, with `traceparent`.

## What to record

| Step | Record | Result |
|---|---|---|
| Provenance | `identical_at_last_hop`, `act_present`, and what differs | |
| Accounting | `client_id` at the node on both paths | |
| Hop limit | Status for 0 and 1 | |
| Tracing | Whether the logs of all services show the same `traceparent` | |
| `act` | The LS Login team's answer | |
