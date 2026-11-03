# T2 Refused requests

## Description

What must fail, who refuses it, and how. Uses the tokens of [T1](t1-call-chain.md), in the same session.

Who refused shows in the result. Against LS Login, a refused exchange says `refused_by: provider`. `refused_by: testbed rule (mock only; not LS Login)` must never show up there: if it does, you're on the mock.

**Runs against:** both. On the mock, cases 1 to 3 are refused by the testbed's own rules, with error codes of our choosing. Case 4 is real on both, as the node checks that itself.

An expired token is part of [T4](t4-lifetime.md#expired-token), as it takes an hour.

## Expectations

1. A subject token without the exchanging client in `aud` is refused, as the LS Login team described it (2026-11-03, [A3](../testbed/assumptions.md#assumptions)).
2. A target that isn't registered for the client is refused, probably with `invalid_target` ([A2](../testbed/assumptions.md#assumptions)).
3. A tampered subject token is refused. Whether LS Login checks the subject's signature is our assumption ([A11](../testbed/assumptions.md#assumptions)).
4. The node answers, in order: 200 (or 403 if the entitlement isn't released); then 401 with the reasons `audience`, `audience`, `type` and `signature`.

## Steps

### Case 1: subject token without our client in `aud`

The login token is for the client, not the gateway.

```text
tb> exchange bad --as gateway --from user --audience @node
```

### Case 2: target not registered

The second line asks for a hop that exists, but isn't registered for that client: a client can't skip the gateway.

```text
tb> exchange bad --as client --from user --audience @unregistered
tb> exchange bad --as client --from user --audience @node
tb> exchange bad --as client --from user --resource @unregistered
```

### Case 3: tampered subject token

The mock itself accepts this, with `--no-rules`. LS Login must not.

```text
tb> exchange bad --as client --from user --audience @gateway --tamper-subject
```

### Case 4: wrong audience and wrong token type at the node

The node checks these itself, with no help from LS Login. The ID token's `type` can't be shown locally, as the mock gives ID tokens the same `typ`.

```text
tb> exchange to-node --as gateway --from to-gw --audience @node
tb> call node --token to-node
tb> call node --token to-gw
tb> call node --token user
tb> call node --token user --id-token
tb> call node --token to-node --tamper
```

## Questions it answers

### What are the error codes of refusals?

The testbed's codes on the mock are guesses. FOCA has to tell a refused exchange from an unreachable provider, and report it to callers.

### Does LS Login check the subject token's signature and expiry?

Assumed, not stated ([A11](../testbed/assumptions.md#assumptions)). If it doesn't, a service must validate a token before exchanging it, which the services here do anyway, and that goes into the operator docs.

## What to record

| Case | Record | Result |
|---|---|---|
| 1 | Status, error code, `refused_by` | |
| 2 | Status, error code, for each line | |
| 3 | Status, error code | |
| 4 | Status and reason, for each call | |
