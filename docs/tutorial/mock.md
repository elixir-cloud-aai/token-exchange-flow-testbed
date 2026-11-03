# Run against the mock

Needs Docker with Compose. No account, no Python on your machine, and no free ports: the mock is only reachable from the testbed's containers.

!!! warning "What this does and doesn't show"
    The mock accepts almost everything, so `refused_by: testbed rule (mock only; not LS Login)` means that the testbed refused, by its own emulation of LS Login's rules. `aud` and `client_id` after an exchange come from our `mock/oidc.json`. So this run teaches the commands and shows that the code works. It's no evidence about LS Login. See What the mock can't show.

## 1. Prove your machine

```sh
docker compose build
docker compose run --rm e2e
docker compose down -v
```

**Expected:** it ends with `51/51 checks passed`, in under a minute after the build. It starts the mock, runs all scenarios, and scans all output for tokens and secrets. The section `MOCK GAP` lists what the mock lets through.

## 2. Start a session

Start the services, then a session in the same terminal:

```sh
docker compose up -d --wait services
docker compose run --rm session
```

Tokens exist only in the session's memory. To see what the services log, run `docker compose logs -f services` in a second terminal. The logs show decoded claims only. All results below are JSON; these listings only keep what matters.

## 3. Check the provider

```text
tb> clients
tb> discovery
```

**Expected:** `provider: mock`, `ls_login_rules_emulated: true`, and six clients, including `loop`, which only exists on the mock. In `discovery`, `grant_types_supported` is `null`: the mock doesn't list them.

## 4. Log in

The mock's login form is filled in for you, with a made-up user.

```text
tb> login user --as client
```

**Expected:**

```json
"header": {"alg": "RS256", "kid": "testbed", "typ": "at+jwt"},
"claims": {"sub": "test-user-inside", "aud": "tx-client", "client_id": "tx-client"}
```

## 5. First hop: exchange for the gateway

```text
tb> exchange to-gw --as client --from user --audience @gateway
```

`@gateway` stands for the gateway's client ID. **Expected:** `aud` is now `tx-gateway`, and `sub` hasn't changed.

## 6. Two hops

```text
tb> call gateway --token to-gw --save direct
```

The gateway validates the token, exchanges it for the node and forwards the request. **Expected:** `status: 200`, with one row per service:

```text
service  aud         client_id  hop_limit  policy   trace_origin
gateway  tx-gateway  tx-client  8          off      generated
node     tx-node     tx-gateway 7          allowed  received
```

`act` is `null` in both, and both have the same `traceparent`.

## 7. Through the orchestrator

```text
tb> exchange to-orch --as client --from user --audience @orchestrator
tb> call orchestrator --token to-orch --save chained
```

**Expected:** `status: 200` with three rows: `aud` changes at each, from `tx-orchestrator` to `tx-gateway` to `tx-node`.

## 8. The case for `act`

```text
tb> compare direct chained
```

**Expected:** `identical_at_last_hop: true`, `act_present: [false, false]`. The node saw the same claims on both paths. See What can't work yet.

## 9. Lifetimes

```text
tb> lifetimes
```

**Expected:** 3600 seconds for all. That's from our `mock/oidc.json`, so it's no evidence.

## 10. What the rules refuse

The rules of the LS Login team as the testbed emulates them, then the same without them:

```text
tb> exchange bad --as gateway --from user --audience @node
tb> exchange bad --as client --from user --audience @unregistered
tb> exchange bad --as client --from user --audience @gateway --tamper-subject
tb> exchange bad --as client --from user --audience @gateway --tamper-subject --no-rules
```

**Expected:** `ok: false` in the first three, each with `refused_by: testbed rule (mock only; not LS Login)` and the errors `invalid_grant`, `invalid_target` and `invalid_grant`. With `--no-rules`, the mock accepts the tampered token: `ok: true`.

## 11. What the services refuse

```text
tb> exchange to-node --as gateway --from to-gw --audience @node
tb> call node --token to-node
tb> call node --token to-gw
tb> call node --token to-node --tamper
```

**Expected:** 200, then 401 with the reason `audience`, then 401 with the reason `signature`. These come from the services' own validation, and would be the same against any provider.

## 12. A user outside the group

```text
tb> login b --as client --mock-user outside
tb> exchange b-gw --as client --from b --audience @gateway
tb> call gateway --token b-gw
```

**Expected:** `status: 403`. The gateway passes the request on (`policy: off`), and the node refuses it (`policy: denied`, `refused: entitlement`). It's 403 and not 401, so that a portal can offer a way to get access.

## 13. Hop limit

```text
tb> call gateway --token to-gw --hop-limit 0
```

**Expected:** `status: 508`, with `refused: hop limit`.

## 14. Clean up

```text
tb> quit
```

```sh
docker compose down -v
```

To keep results, start the session with `--record /results/mock.jsonl` instead; see [Settings](../reference/settings.md#results).
