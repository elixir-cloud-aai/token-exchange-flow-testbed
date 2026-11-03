# Checking the setup

Two checks against the mock. The first is automated, and the second teaches the commands.

!!! warning "What this does and doesn't show"
    The mock accepts almost everything, so `refused_by: testbed rule (mock only; not LS Login)` means that the testbed refused, by its own emulation of LS Login's rules as its team described them on 2026-11-03. `aud` and `client_id` after an exchange come from our `mock/oidc.json`. So these checks show that the code works, and your machine can run it. They're no evidence about LS Login. See [Testbed limits](../testbed/limits.md).

## The automated run

```sh
docker compose run --rm e2e
docker compose down -v
```

**Expected:** after the build, in under a minute, it ends with `N/N checks passed`, with the same number twice. It starts the mock, runs all scenarios, executes the `tb>` lines of these docs except for `wait-expiry` (some end in a refusal or a usage error, which counts as passing here), and scans all output for tokens and secrets. The section `MOCK GAP` lists what the mock lets through.

## A session by hand

About 15 minutes.

### Start a session

Start the services, then a session in the same terminal:

```sh
docker compose up -d --wait services
docker compose run --rm session
```

Tokens exist only in the session's memory. To see what the services log, run `docker compose logs -f services` in a second terminal. The logs show decoded claims only. All results below are JSON; these listings only keep what matters.

### Check the provider

```text
tb> clients
tb> discovery
```

**Expected:** `provider: mock`, `ls_login_rules_emulated: true`, and six clients, including `loop`, which only exists on the mock. In `discovery`, `grant_types_supported` is `null`: the mock doesn't list them.

### Log in

The mock's login form is filled in for you, with a made-up user.

```text
tb> login user --as client
```

**Expected:**

```json
"header": {"alg": "RS256", "kid": "testbed", "typ": "at+jwt"},
"claims": {"sub": "test-user-inside", "aud": "tx-client", "client_id": "tx-client"}
```

### First hop: exchange for the gateway

```text
tb> exchange to-gw --as client --from user --audience @gateway
```

`@gateway` stands for the gateway's client ID. **Expected:** `aud` is now `tx-gateway`, and `sub` hasn't changed.

### Two hops

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

### Through the orchestrator

```text
tb> exchange to-orch --as client --from user --audience @orchestrator
tb> call orchestrator --token to-orch --save chained
```

**Expected:** `status: 200` with three rows: `aud` changes at each, from `tx-orchestrator` to `tx-gateway` to `tx-node`.

### What the node can tell

```text
tb> compare direct chained
```

**Expected:** `identical_at_last_hop: true`, `act_present: [false, false]`. The node saw the same claims on both paths. See [T5](../tests/t5-attribution.md).

### Lifetimes

```text
tb> lifetimes
```

**Expected:** 3600 seconds for all. That's from our `mock/oidc.json`, so it's no evidence.

### What the rules refuse

The rules of the LS Login team as the testbed emulates them, then the same without them:

```text
tb> exchange bad --as gateway --from user --audience @node
tb> exchange bad --as client --from user --audience @unregistered
tb> exchange bad --as client --from user --audience @gateway --tamper-subject
tb> exchange bad --as client --from user --audience @gateway --tamper-subject --no-rules
```

**Expected:** `ok: false` in the first three, each with `refused_by: testbed rule (mock only; not LS Login)` and the errors `invalid_grant`, `invalid_target` and `invalid_grant`. With `--no-rules`, the mock accepts the tampered token: `ok: true`.

### What the services refuse

```text
tb> exchange to-node --as gateway --from to-gw --audience @node
tb> call node --token to-node
tb> call node --token to-gw
tb> call node --token to-node --tamper
```

**Expected:** 200, then 401 with the reason `audience`, then 401 with the reason `signature`. These come from the services' own validation, and would be the same against any provider.

### A user outside the group

```text
tb> login b --as client --mock-user outside
tb> exchange b-gw --as client --from b --audience @gateway
tb> call gateway --token b-gw
```

**Expected:** `status: 403`. The gateway passes the request on (`policy: off`), and the node refuses it (`policy: denied`, `refused: entitlement`). It's 403 and not 401, so that a portal can offer a way to get access.

### Hop limit

```text
tb> call gateway --token to-gw --hop-limit 0
```

**Expected:** `status: 508`, with `refused: hop limit`.

### Clean up

```text
tb> quit
```

```sh
docker compose down -v
```

To keep results, start the session with `--record /results/mock.jsonl` instead; see [Configuration](configuration.md#results).
