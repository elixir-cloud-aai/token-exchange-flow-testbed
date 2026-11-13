# T4 Token lifetime and refresh

## Description

How long tokens live, whether an exchange can give a token for work that outlasts the request, and what happens at expiry. Uses the tokens of [T1](t1-call-chain.md), in the same session, except for the expired token, which has its own.

**Runs against:** LS Login. On the mock, lifetimes come from `mock/oidc.json`, and an exchange never returns a refresh token.

From the LS Login team, 2026-11-03: the lifetime is "currently 1 hour" ([A7](../testbed/assumptions.md#assumptions)), and refresh tokens come with `offline_access` and last 31 days for now ([A6](../testbed/assumptions.md#assumptions)).

## Expectations

1. Exchanged tokens live 1 hour. A login token of Krini's lived 4 hours on 2026-10-20 (our own observation), so login tokens may differ.
2. Refreshing gives a new access token for the same `sub`.
3. If `exp` of the refresh token moves by the time elapsed, the limit is idle. If it stays, absolute. If introspection shows no `exp` and the token is opaque, only the LS Login team can tell.
4. Whether an exchange returns a refresh token is unknown. If it does, its access token has `aud` = gateway, the call gives 200, and the last refresh is refused after revocation.
5. An expired token gets 401 with the reason `expired`, an exchange of it is refused by LS Login, and the refresh still works.
6. Another client can't redeem the client's refresh token ([RFC 6749, section 6](https://datatracker.ietf.org/doc/html/rfc6749#section-6)). Whether a rotated refresh token can be reused, and whether that ends the whole grant, is unknown.

## Steps

### Refresh at the client

Rotation shows in `refresh_token_rotated`.

```text
tb> show user
tb> introspect user --as client --refresh
tb> refresh r1 --as client --from user
tb> introspect r1 --as client --refresh
tb> show r1
```

### Lifetimes

Compare the login, exchanged and refreshed tokens. Then exchange from the login token, which is old by now: does the new token get a full lifetime, or only what the subject token has left? If the subject has expired, the exchange should be refused. If it's refused with `seconds_left` above zero, the refresh may have ended the old access token, which is a result of its own.

```text
tb> lifetimes
tb> exchange late --as client --from user --audience @gateway
tb> lifetimes
```

### 31 days: idle or absolute?

We can't wait 31 days, but we can compare. At least 10 minutes after the previous step:

```text
tb> refresh r2 --as client --from r1
tb> introspect r2 --as client --refresh
```

### Refresh token from an exchange

The Conquest case, which decides how long-running work gets tokens. It starts from a new token, as the one from T1 may have expired, which would look like a refusal of the refresh token.

```text
tb> exchange to-orch2 --as client --from r2 --audience @orchestrator
tb> exchange ro --as orchestrator --from to-orch2 --audience @gateway --scope "openid offline_access"
tb> exchange ro2 --as orchestrator --from to-orch2 --audience @gateway --scope "openid offline_access" --requested-type refresh
```

### Only if that returned one

Use the token that holds it in place of `ro`. A token issued as a refresh token can only be redeemed, not called with.

```text
tb> refresh ro-a --as orchestrator --from ro
tb> show ro-a
tb> call gateway --token ro-a
tb> refresh ro-b --as orchestrator --from ro-a --audience @gateway
tb> revoke ro-b --as orchestrator --refresh
tb> refresh ro-c --as orchestrator --from ro-b
```

### Expired token

Start this at least an hour before you need the result, in a second session, as it takes as long as the tokens live:

```sh
docker compose -f compose.lslogin.yaml run --rm session --record /results/expiry.jsonl
```

Only one session can log in at a time, as they share the callback port. Log in with account A again, so that `sub` can be compared with the first login.

```text
tb> login exp --as client
tb> exchange exp-gw --as client --from exp --audience @gateway
tb> lifetimes
tb> wait-expiry exp-gw
tb> call gateway --token exp-gw
tb> exchange exp-bad --as gateway --from exp-gw --audience @node
tb> refresh exp-new --as client --from exp
```

Ctrl-C ends a wait without losing the tokens.

### Binding and reuse

In the same second session, as reuse detection may end every refresh token of a login, and later tests need those of the first. Another client tries the refresh token first, then the client refreshes twice, then reuses the older one:

```text
tb> refresh exp-other --as gateway --from exp-new
tb> refresh exp-new2 --as client --from exp-new
tb> refresh exp-reuse --as client --from exp-new
tb> refresh exp-after --as client --from exp-new2
```

Only if `exp-new2` shows `refresh_token_rotated: true` does the reuse mean anything. Then a refused `exp-reuse` shows that rotation is enforced, and a refused `exp-after` that reuse ended the grant. If `exp-other` worked, the refresh token isn't bound to the client, which is a result of its own. If it was refused and `exp-new2` is refused, too, the attempt by another client ended the grant. See [Delegated access](../testbed/delegated-access.md#bounded-grant) for why this matters.

## Questions it answers

### What does "1 hour" cover, and is it capped by the subject token?

Does it cover only exchanged tokens?

- Sets the margin of FOCA's cache per user and audience, until shortly before expiry.
- **If it's capped:** an old login token shortens each hop, so clients have to refresh before exchanging. That goes into the docs for the clients of proTES #391.

Lifetimes stay configurable in FOCA either way, as the new stack will change them ([C10](../testbed/assumptions.md#constraints)).

### Can an exchange return a refresh token, limited to the next hop?

- **Yes:** the orchestrator holds it per run. FOCA adds encrypted storage and revocation helpers.
- **No:** Conquest can't mint tokens days later. Options to weigh: Krini's backend holds the user's refresh token and exchanges on demand, or service tokens for that hop only. #391's "Long-running work" changes.

### Is the 31 days idle or absolute, and do refresh tokens rotate?

- **Absolute:** it's the maximum length of a run, which goes into Conquest's docs.
- **Idle:** runs are unlimited, as long as they refresh in time.
- **Rotation:** FOCA's helper has to store the new token atomically, as a lost one ends the run.

### Are refresh tokens bound to the client, and is reuse detected?

- **Bound:** a refresh token that leaks from the workflow system is of no use to another client without that client's secret, too. If not, a refresh token has to be treated like a password of the user's.
- **Reuse detected:** a leaked refresh token that is used ends the run, too, so leaks show. FOCA's helper then reports that the grant has ended, rather than retrying.
- **Neither:** the 31 days are all that limits a leaked refresh token, unless it's revoked.

## What to record

| Step | Record | Result |
|---|---|---|
| Lifetimes | Login, exchanged, second hop, refreshed, exchanged from an old subject | |
| Refresh at the client | Format of the refresh token, `refresh_token_rotated`, `exp` before and after | |
| Idle or absolute | `exp` of `r1` and `r2`, and the verdict: idle, absolute or unknown | |
| Refresh token from an exchange | Whether either holds a refresh token, and `issued_token_type` | |
| Only if that returned one | `aud`, status of the call, the refresh after revoking | |
| Expired token | `sub` compared with the first login, status and reason, the exchange's error, the refresh | |
| Binding and reuse | Whether `exp-other` was refused, `refresh_token_rotated` of `exp-new2`, and whether `exp-reuse` and `exp-after` were refused, with errors | |
