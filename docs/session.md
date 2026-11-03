# Session with the LS Login team

The sequence for the planned hands-on session with the LS Login team, on one page, with blanks for the results. The [tutorial](tutorial/index.md) explains the same steps at more length. Afterwards, update the "To check" list of [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391) and the [open questions](open-questions.md) with the answers.

!!! warning "Status"
    Nothing here has run against LS Login. Every "Expected" is what the LS Login team's answers of 2026-11-03 or the standards suggest, not an observation. All commands have run against a local mock, which only shows that they work: see What the mock can't show.

Target flow, as in proTES #391: each caller exchanges its token for one meant for the next service.

```text
User -> client (Krini) -> gateway (proTES) -> node (TES)
User -> client -> orchestrator (Conquest) -> gateway -> node
```

## Before the session

1. **Accounts, clients and group release:** see Prepare accounts and clients. As early as possible, as we don't know whether registrations need approval.
2. **`lslogin.env`:** as on that page. Check the `ECP_CLN` entitlement in it: we derived that value from a known entitlement of the same form.
3. **Prove your machine:** the run against the mock must end with all checks passed.
4. **Try steps 1 to 5 once beforehand,** so that the session isn't spent on registration mistakes.

## In the session

Terminal 1, the services (logs show decoded claims only):

```sh
docker compose -f compose.lslogin.yaml up -d --wait services
docker compose -f compose.lslogin.yaml logs -f services
```

Terminal 2, the client. Tokens live only in this process, so keep it open:

```sh
docker compose -f compose.lslogin.yaml run --rm session --record /results/session.jsonl
```

Terminal 3, **at least an hour before you need the result** (step 13):

```sh
docker compose -f compose.lslogin.yaml run --rm session --record /results/expiry.jsonl
```

`--record` keeps the decoded results, so the blanks only need what you want to remember. Only one session can log in at a time, as they share the callback port. If a validation says "not yet valid", check the machine's clock: as in FOCA, there's no leeway.

### Changing settings

After editing `lslogin.env`, this restarts the services only. Running sessions keep their tokens:

```sh
docker compose -f compose.lslogin.yaml up -d --force-recreate --no-deps --wait services
```

### Happy path

**1. Provider and clients.**

```
tb> clients
tb> discovery
```

Expected: provider `lslogin`, `ls_login_rules_emulated: false`, all five clients, token exchange in the grant types.

Actual: ____________________

**2. Log in as account A.** Copy the URL it shows into a browser, as a container can't open one. Add `--flow device` if the app refuses the localhost redirect URI (never run: the mock has no device flow).

```
tb> login user --as client
```

Expected: `typ: at+jwt`, `aud` = client's ID (seen on 2026-10-20), a persistent `sub`, a refresh token, as `offline_access` is requested.

Actual: typ ______ aud ______ client_id ______ exp-iat ______ refresh token ______

**3. Hop 1: the client exchanges for the gateway.** If refused, try the next line.

```
tb> exchange to-gw --as client --from user --audience @gateway
tb> exchange to-gw --as client --from user --resource @gateway
```

Expected: `aud` holds only the gateway's ID; `sub` unchanged. Open: what's in `client_id`, which parameter works, is `typ` still `at+jwt`. If only `--resource` works, set `TESTBED_TARGET_PARAM` to `resource` and [restart the services](#changing-settings).

Actual: parameter ______ aud ______ client_id ______ azp ______ exp-iat ______ scope ______

**4. URL form of the indicator.**

```
tb> exchange to-gw-url --as client --from user --resource @gateway.url
tb> call gateway --token to-gw-url
```

Expected: if `aud` holds only the URL, the gateway accepts the token but LS Login refuses its next exchange (502), because the gateway's ID isn't in `aud`. Then bare client IDs are the only form that works for a chain.

Actual: aud ______ call ______

**5. Two hops.**

```
tb> call gateway --token to-gw --save direct --traceparent 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
```

Expected: 200. Gateway sees `aud` = gateway, node sees `aud` = node, same `sub`, same `traceparent`, hop limit 8 then 7, `act: null`. This is also the first real check that exchanged tokens pass FOCA's checks.

Actual: gateway's client_id ______ node's client_id ______ exp-iat at node ______

**6. Variant through the orchestrator.**

```
tb> exchange to-orch --as client --from user --audience @orchestrator
tb> call orchestrator --token to-orch --save chained
```

Expected: 200 over three services, with `aud` changing at each.

Actual: ____________________

**7. What the lifetime covers.**

```
tb> lifetimes
```

Compare login, exchanged and refreshed tokens. A login token of Krini's lived 4 hours on 2026-10-20; the LS Login team said "currently 1 hour". Repeat steps 3 and 7 later in the session, with an older subject token: does the exchanged token get a full lifetime, or only what the subject token has left?

Actual: login ______ exchanged ______ second hop ______ exchanged from old subject ______

**8. Public client.** This is an open question, and either outcome is acceptable: Krini may get a backend anyway. The mock can't answer it, as it refuses this outright.

```
tb> login pub --as public
tb> exchange pub-gw --as public --from pub --audience @gateway
```

Actual: login ______ exchange ______ (error: ______)

### Refused cases

For each one, record the status and error code. FOCA will have to handle them, and the testbed's own codes on the mock are guesses.

**9. Subject token without our client in `aud`.** The login token is for the client, not the gateway.

```
tb> exchange bad --as gateway --from user --audience @node
```

Expected: an error, with `refused_by: provider`.

Actual: ____________________

**10. Target not registered.** The second line asks for a hop that exists but isn't registered for that client: a client can't skip the gateway.

```
tb> exchange bad --as client --from user --audience @unregistered
tb> exchange bad --as client --from user --audience @node
tb> exchange bad --as client --from user --resource @unregistered
```

Expected: errors, probably `invalid_target`.

Actual: ____________________

**11. Tampered subject token.** The mock accepts this. LS Login must not.

```
tb> exchange bad --as client --from user --audience @gateway --tamper-subject
```

Expected: an error.

Actual: ____________________

**12. Wrong audience and wrong token type at the node.** The node checks these itself, with no help from LS Login.

```
tb> exchange to-node --as gateway --from to-gw --audience @node
tb> call node --token to-node
tb> call node --token to-gw
tb> call node --token user
tb> call node --token user --id-token
tb> call node --token to-node --tamper
```

Expected, in order: 200 (or 403 if the entitlement isn't released); then 401 with the reasons `audience`, `audience`, `type`, `signature`. The ID token's `type` can't be shown locally, as the mock gives ID tokens the same `typ`.

Actual: ____________________

**13. Expired token (terminal 3).** Start this first, as it takes as long as the tokens live.

```
tb> login exp --as client
tb> exchange exp-gw --as client --from exp --audience @gateway
tb> lifetimes
tb> wait-expiry exp-gw
tb> call gateway --token exp-gw
tb> exchange exp-bad --as gateway --from exp-gw --audience @node
tb> refresh exp-new --as client --from exp
```

Expected: 401 with the reason `expired`; the exchange refused by LS Login; the refresh still works. Ctrl-C ends a wait without losing the tokens.

Actual: ____________________

### Groups

**14. Release per client (account A).** The LS Login team says that entitlements are computed for the client calling the exchange. Which entitlements does each token get?

```
tb> userinfo user
tb> userinfo to-gw
tb> userinfo to-node
tb> userinfo to-orch
tb> introspect to-node --as node
tb> introspect to-node --as gateway
tb> exchange to-node-s --as gateway --from to-gw --audience @node --scope "openid eduperson_entitlement"
tb> userinfo to-node-s
```

Expected: `ECP_CLN` for the tokens of clients with the release. Note that the node's token was issued to the gateway, so it probably shows the *gateway's* release, not the node's. Does `introspect --as node` differ? Does the exchange need the `scope`? Also compare the exact entitlement with `TESTBED_REQUIRED_ENTITLEMENT`.

Actual: user ______ to-gw ______ to-node ______ to-orch ______ as node ______ as gateway ______ with scope ______

**15. Account A through the chain.**

```
tb> call gateway --token to-gw
```

Expected: 200, node's `policy: allowed`. A 403 here, for a member of the group, means that the release is missing on the gateway; set `TESTBED_EXCHANGE_SCOPE` and [restart the services](#changing-settings) if step 14 needed the `scope`.

Actual: ____________________

**16. Account B, outside the group: must not be locked out.** Paste the URL into a private window, so that the browser's session for A isn't used.

```
tb> login b --as client --no-browser
tb> exchange b-gw --as client --from b --audience @gateway
tb> userinfo b
tb> call gateway --token b-gw
```

Expected: login and exchange work; the gateway passes the request on; the node answers **403** with `refused: entitlement`, not 401. Krini can then offer "request compute access". **If LS Login refuses the login or the exchange, B is locked out: raise it before going on.**

Actual: login ______ exchange ______ node ______

### Refresh tokens

**17. Refresh at the client.** Rotation shows in `refresh_token_rotated`.

```
tb> show user
tb> introspect user --as client --refresh
tb> refresh r1 --as client --from user
tb> introspect r1 --as client --refresh
tb> show r1
```

Expected: a new access token for the same `sub`. Open: rotation, what introspection shows.

Actual: format ______ rotated ______ exp before ______ exp after ______

**18. 31 days: idle or absolute?** We can't wait 31 days, but we can compare. At least 10 minutes after step 17:

```
tb> refresh r2 --as client --from r1
tb> introspect r2 --as client --refresh
```

Expected: if `exp` moved by the time elapsed, the limit is idle; if it stayed, absolute. If introspection shows no `exp` and the token is opaque, only the LS Login team can tell.

Actual: exp r1 ______ exp r2 ______ → idle / absolute / unknown

**19. Refresh token from an exchange (the Conquest case).** This decides how long-running work gets tokens.

```
tb> exchange ro --as orchestrator --from to-orch --audience @gateway --scope "openid offline_access"
tb> exchange ro2 --as orchestrator --from to-orch --audience @gateway --scope "openid offline_access" --requested-type refresh
```

Expected: unknown, and what the mock does is no evidence. If either returns a refresh token, go on with the next step, and use the token that holds it in place of `ro`.

Actual: `ro` refresh token ______ `ro2` issued type ______

**20. Only if 19 returned one.** Does it stay limited to the gateway, and does the access token still work?

```
tb> refresh ro-a --as orchestrator --from ro
tb> show ro-a
tb> call gateway --token ro-a
tb> refresh ro-b --as orchestrator --from ro --audience @gateway
tb> revoke ro --as orchestrator --refresh
tb> refresh ro-c --as orchestrator --from ro
```

Expected: `aud` = gateway, 200; the last refresh refused after revocation (with a rotating token, `ro` may already be refused earlier).

Actual: aud ______ call ______ after revoking ______

### The case for `act`

**21. Show the LS Login team the node's view.**

```
tb> compare direct chained
tb> call gateway --token to-gw --hop-limit 0
tb> call gateway --token to-gw --hop-limit 1
```

What to show them:

- Direct and through the orchestrator, the node sees **the same claims** (`identical_at_last_hop: true`, `act_present: [false, false]`), unless `client_id` differs. At best, `client_id` names the last caller.
- So the node can't tell whether the orchestrator was involved. Neither provenance nor accounting can be read from the token.
- A gateway can't detect itself in the chain, so it refuses nothing by identity ([proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391)). What's left is `Hop-Limit` (508 at 0) and `traceparent`. They stop accidental loops and allow tracing from logs, but neither is signed, so any hop can reset them.
- The ask: nested `act` (RFC 8693, section 4.1) in the new stack, set by LS Login from the exchanging client, as only it can vouch for that. Later `may_act`/`can_act`, for restricting who may act.

Their reaction: ____________________

## Afterwards

```sh
docker compose -f compose.lslogin.yaml down -v
```

Then delete `lslogin.env`, and `results/` once you've taken what you need. It holds decoded claims of the accounts used.
