# Run against LS Login

Nothing on this page has been run yet. Every "Expected" comes from the LS Login team's answers of 2026-11-03 or the standards. Where the result differs, record it: that's what this run is for.

Before you start: [accounts, clients and group release](prepare.md), `lslogin.env`, and a [passing run against the mock](mock.md).

## Start

Terminal 1, the services. Their logs show decoded claims only:

```sh
docker compose -f compose.lslogin.yaml up -d --wait services
docker compose -f compose.lslogin.yaml logs -f services
```

Terminal 2, the session. Tokens live only in this process, so keep it open. Results are appended to `results/session.jsonl`, as decoded claims:

```sh
docker compose -f compose.lslogin.yaml run --rm session --record /results/session.jsonl
```

To change a setting later without losing the session's tokens, edit `lslogin.env`, then:

```sh
docker compose -f compose.lslogin.yaml up -d --force-recreate --no-deps --wait services
```

## 1. Provider and clients

```text
tb> clients
tb> discovery
```

**Expected:** provider `lslogin`, `ls_login_rules_emulated: false`, all five clients, and token exchange among the grant types. No testbed rule applies from here on: refusals are LS Login's own, with `refused_by: provider`.

## 2. Log in as account A

```text
tb> login user --as client
```

The session shows a URL. Copy it into a browser: a container can't open one. The browser returns to `http://localhost:18994/callback`, which Compose forwards to the session. At the [consent page](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742536712/Understanding+consent+pages+when+logging+in), don't deselect entitlements.

**Expected:** `typ: at+jwt`, `aud` is the client's ID (as seen on 2026-10-20), a persistent `sub`, and a refresh token, as `offline_access` is requested.

**Record:** `typ`, `aud`, `client_id`, `exp` minus `iat`, whether there's a refresh token.

## 3. First hop

```text
tb> exchange to-gw --as client --from user --audience @gateway
```

If that's refused, try the same with `--resource`:

```text
tb> exchange to-gw --as client --from user --resource @gateway
```

**Expected:** `aud` holds only the gateway's ID, and `sub` hasn't changed. If only `--resource` works, set `TESTBED_TARGET_PARAM=resource` in `lslogin.env` and restart the services.

**Record:** which parameter works, `aud`, `client_id`, `azp`, `exp` minus `iat`, `scope`, `typ`. **This is the first real exchange:** if the registration app or the exchange refuses a bare client ID, stop and raise it. It [blocks the design](../open-questions.md#bare-ids).

## 4. The URL form

```text
tb> exchange to-gw-url --as client --from user --resource @gateway.url
tb> call gateway --token to-gw-url
```

**Expected:** if `aud` holds only the URL, the gateway accepts the token, but LS Login refuses its next exchange, which the gateway reports as 502, because the gateway's ID isn't in `aud`. Then bare client IDs are the only form that works for a chain.

**Record:** `aud`, the status of the call.

## 5. Two hops

```text
tb> call gateway --token to-gw --save direct --traceparent 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
```

**Expected:** 200. The gateway sees `aud` = gateway, the node sees `aud` = node, with the same `sub` and `traceparent`, hop limit 8 then 7, and `act: null`. This is also the first real check that exchanged tokens pass FOCA's checks.

**Record:** `client_id` at each hop, `exp` minus `iat` at the node.

## 6. Through the orchestrator

```text
tb> exchange to-orch --as client --from user --audience @orchestrator
tb> call orchestrator --token to-orch --save chained
```

**Expected:** 200 over three services, with `aud` changing at each.

## 7. Lifetimes

```text
tb> lifetimes
```

Compare the login, exchanged and refreshed tokens. Repeat steps 3 and 7 later in the session, with an older subject token: does the exchanged token get a full lifetime, or only what the subject token has left?

**Record:** the lifetime of each, and of a token exchanged from an old subject.

## 8. Public client

An open question, and either outcome is acceptable: Krini may get a backend anyway. The mock can't answer it, as it refuses this outright.

```text
tb> login pub --as public
tb> exchange pub-gw --as public --from pub --audience @gateway
```

**Record:** both results, and the error if any.

## Groups {#groups}

### 14. Release per client

Step numbers follow the [session page](../session.md). Which entitlements does each token get?

```text
tb> userinfo user
tb> userinfo to-gw
tb> exchange to-node --as gateway --from to-gw --audience @node
tb> userinfo to-node
tb> userinfo to-orch
tb> introspect to-node --as node
tb> introspect to-node --as gateway
tb> exchange to-node-s --as gateway --from to-gw --audience @node --scope "openid eduperson_entitlement"
tb> userinfo to-node-s
```

**Expected:** the group for the tokens of clients with the release, and not for `to-orch`. The node's token was issued to the gateway, so it probably shows the *gateway's* release, not the node's.

**Record:** the entitlements for each line, and the exact value, to compare with `TESTBED_REQUIRED_ENTITLEMENT`. Does `introspect --as node` differ? Does the exchange need the `scope`?

### 15. Account A through the chain

```text
tb> call gateway --token to-gw
```

**Expected:** 200, and `policy: allowed` at the node. A 403 here, for a member of the group, means that the release is missing on the gateway. If step 14 needed the `scope`, set `TESTBED_EXCHANGE_SCOPE` and restart the services.

### 16. Account B must not be locked out

Paste the URL into a private window, so that the browser's session for A isn't used.

```text
tb> login b --as client --no-browser
tb> exchange b-gw --as client --from b --audience @gateway
tb> userinfo b
tb> call gateway --token b-gw
```

**Expected:** login and exchange work, the gateway passes the request on, and the node answers **403** with `refused: entitlement`, not 401. Krini can then offer "request compute access". **If LS Login refuses the login or the exchange, B is locked out: raise it before going on.** The [access denied page](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1749647367/Access+denied+after+login) lists general causes.

## Refresh tokens

### 17. Refresh at the client

```text
tb> show user
tb> introspect user --as client --refresh
tb> refresh r1 --as client --from user
tb> introspect r1 --as client --refresh
tb> show r1
```

**Expected:** a new access token for the same `sub`. **Record:** the format of the refresh token, `refresh_token_rotated`, and `exp` before and after.

### 18. 31 days: idle or absolute?

We can't wait 31 days, but we can compare. At least 10 minutes after step 17:

```text
tb> refresh r2 --as client --from r1
tb> introspect r2 --as client --refresh
```

**Expected:** if `exp` moved by the time elapsed, the limit is idle; if it stayed, absolute. If introspection shows no `exp` and the token is opaque, only the LS Login team can tell.

### 19. Refresh token from an exchange

The Conquest case, which decides how long-running work gets tokens.

```text
tb> exchange ro --as orchestrator --from to-orch --audience @gateway --scope "openid offline_access"
tb> exchange ro2 --as orchestrator --from to-orch --audience @gateway --scope "openid offline_access" --requested-type refresh
```

**Expected:** unknown. **Record:** whether either holds a refresh token, and `issued_token_type`.

### 20. Only if 19 returned one

Use the token that holds it in place of `ro`.

```text
tb> refresh ro-a --as orchestrator --from ro
tb> show ro-a
tb> call gateway --token ro-a
tb> refresh ro-b --as orchestrator --from ro --audience @gateway
tb> revoke ro --as orchestrator --refresh
tb> refresh ro-c --as orchestrator --from ro
```

**Expected:** `aud` is the gateway, the call gives 200, and the last refresh is refused after revocation. With a rotating token, `ro` may already be refused earlier.

## The case for `act`

### 21. The node's view

```text
tb> compare direct chained
```

**Expected:** `identical_at_last_hop: true`, unless `client_id` differs, and `act_present: [false, false]`. Direct and through the orchestrator, the node sees the same claims. See [What can't work yet](../concepts/limits.md).

Go on with the [refused cases](refused.md), in the same session.

## Clean up

```text
tb> quit
```

```sh
docker compose -f compose.lslogin.yaml down -v
```

Then delete `lslogin.env`, and `results/` once you've taken what you need: it holds decoded claims of the accounts used.
