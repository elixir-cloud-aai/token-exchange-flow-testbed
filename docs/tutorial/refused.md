# Refused cases

Continues the [LS Login run](ls-login.md), in the same session, as it uses its tokens. For each case, record the status and the error code: FOCA will have to handle them, and the testbed's own codes on the mock are guesses.

Who refused shows in the result. Against LS Login, a refused exchange says `refused_by: provider`. `refused_by: testbed rule (mock only; not LS Login)` must never show up here: if it does, you're on the mock.

## 9. Subject token without our client in `aud`

The login token is for the client, not the gateway.

```text
tb> exchange bad --as gateway --from user --audience @node
```

**Expected:** an error, as the LS Login team described it.

## 10. Target not registered

The second line asks for a hop that exists, but isn't registered for that client: a client can't skip the gateway.

```text
tb> exchange bad --as client --from user --audience @unregistered
tb> exchange bad --as client --from user --audience @node
tb> exchange bad --as client --from user --resource @unregistered
```

**Expected:** errors, probably `invalid_target`.

## 11. Tampered subject token

The mock accepts this. LS Login must not.

```text
tb> exchange bad --as client --from user --audience @gateway --tamper-subject
```

**Expected:** an error. Whether the subject's signature and expiry are checked is our assumption of what LS Login does.

## 12. Wrong audience and wrong token type at the node

The node checks these itself, with no help from LS Login.

```text
tb> exchange to-node --as gateway --from to-gw --audience @node
tb> call node --token to-node
tb> call node --token to-gw
tb> call node --token user
tb> call node --token user --id-token
tb> call node --token to-node --tamper
```

**Expected, in order:** 200 (or 403 if the entitlement isn't released); then 401 with the reasons `audience`, `audience`, `type` and `signature`. The ID token's `type` can't be shown locally, as the mock gives ID tokens the same `typ`.

## 13. Expired token

Start this at least an hour before you need the result, in a second session, as it takes as long as the tokens live:

```sh
docker compose -f compose.lslogin.yaml run --rm session --record /results/expiry.jsonl
```

Only one session can log in at a time, as they share the callback port.

```text
tb> login exp --as client
tb> exchange exp-gw --as client --from exp --audience @gateway
tb> lifetimes
tb> wait-expiry exp-gw
tb> call gateway --token exp-gw
tb> exchange exp-bad --as gateway --from exp-gw --audience @node
tb> refresh exp-new --as client --from exp
```

**Expected:** 401 with the reason `expired`; the exchange refused by LS Login; the refresh still works. Ctrl-C ends a wait without losing the tokens.
