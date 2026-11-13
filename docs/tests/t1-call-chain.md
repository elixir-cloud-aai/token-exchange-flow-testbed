# T1 Delegated call chain

## Description

One login, then one exchange per hop, up to the node. This is the central question: can the chain carry a user's identity, with tokens that are only good for the next service? The first exchange against LS Login happens here.

**Runs against:** both. On the mock, it only shows that the commands work, as `aud` and `client_id` come from our `mock/oidc.json`.

## Expectations

1. Login gives `typ: at+jwt`, `aud` with the client's ID (our own observation, 2026-10-20), a `sub` that is the same for the same account (the LS Login team, 2026-11-03; compared in [T4](t4-lifetime.md#expired-token)), and a refresh token, as `offline_access` is requested.
2. After each exchange, `sub` hasn't changed, and `aud` holds only the next hop's ID.
3. A call through the gateway gives 200: the gateway sees `aud` = gateway, the node sees `aud` = node, with the same `sub` and `traceparent`, hop limit 8 then 7, and `act: null`. Without the group, the node answers 403, or 502 with `refused: userinfo` if user info gives no answer. The rows are still valid, and [T3](t3-groups.md) goes into why.
4. Through the orchestrator, too: 200 (or as above) over three services, with `aud` changing at each.
5. A token with only a URL in `aud` is accepted by the gateway, but LS Login refuses its next exchange, which the gateway reports as 502. This follows from the `aud` rule ([A3](../testbed/assumptions.md#assumptions)).
6. Exchanged tokens pass the same checks as in FOCA.

For the public client, no outcome is expected.

## Steps

### Provider and clients

```text
tb> clients
tb> discovery
```

Provider `lslogin`, `ls_login_rules_emulated: false`, all five clients, and token exchange among the grant types. No testbed rule applies from here on: refusals are LS Login's own, with `refused_by: provider`.

### Login: user to client

```text
tb> login user --as client
```

The session shows a URL. Copy it into a browser, as a container can't open one, and log in with **account A**. It returns to `http://localhost:18994/callback`, which Compose forwards to the session. At the consent page, note what it lists, including whether it mentions offline access or how long the service may act ([Delegated access](../testbed/delegated-access.md#consent-once-explicitly)), and don't deselect entitlements.

### Hop 1: client to gateway

```text
tb> exchange to-gw --as client --from user --audience @gateway
```

`@gateway` stands for the gateway's client ID. If that's refused, try the same with `--resource`:

```text
tb> exchange to-gw --as client --from user --resource @gateway
```

If only `--resource` works, set `TESTBED_TARGET_PARAM=resource` in `lslogin.env` and [restart the services](../setup/configuration.md#changing-settings-during-a-session).

**If the registration app or the exchange refuses a bare client ID, stop and raise it:** see the first question below.

The URL form of the same hop:

```text
tb> exchange to-gw-url --as client --from user --resource @gateway.url
tb> call gateway --token to-gw-url
```

### Hop 2: gateway to node

```text
tb> call gateway --token to-gw --save direct --traceparent 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
```

The gateway validates the token, exchanges it for the node, and forwards the request. The result has one row per service. This is also the first real check that exchanged tokens pass FOCA's checks.

### Variant: client to orchestrator, orchestrator to gateway

```text
tb> exchange to-orch --as client --from user --audience @orchestrator
tb> call orchestrator --token to-orch --save chained
```

### Variant: public client to gateway

The mock can't answer this, as it refuses it outright.

```text
tb> login pub --as public
tb> exchange pub-gw --as public --from pub --audience @gateway
```

## Questions it answers

### Are bare client IDs accepted as resource indicators?

Or how else does the next hop's ID get into `aud`?

- **Yes:** FOCA's outgoing exchange names targets by client ID, and the token flow of [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391) stands.
- **No:** the `aud` rule and URL indicators clash, and chains can't work ([C3](../testbed/assumptions.md#constraints)). This blocks #391's token flow until one of them changes. proTES 0.5.0's architecture stays the fallback.

### Can a token with only a URL in `aud` be exchanged again?

We expect not, since the exchanging client's ID must be in `aud`.

- **No:** tokens for a service that forwards must carry its client ID. URL forms only work for the last hop.
- **Yes:** the `aud` rule is looser than described, and either form works. Then we need to know how LS Login maps a URL to a client.

### Which parameter names the target: `audience`, `resource` or both?

The LS Login team says that both are validated (2026-11-03). The outcome decides the default of FOCA's outgoing exchange, and what ends up in `aud` for each.

### What's in `client_id` after an exchange?

- **The exchanging client:** nodes can allow-list their callers with FOCA's `security.auth.clients`. As `sub` is the user, FOCA treats them as user tokens, which is right.
- **The original client:** nodes can't see even the last hop. That goes into #391's "Identity and tracing".

### Do exchanged tokens have the same `typ`, `alg` and keys as login tokens?

- **Yes:** nothing changes.
- **No:** FOCA's settings `token_types` and `algorithms` have to allow them, on every node. That would go into the operator docs, or get fixed on LS Login's side.

### Can public clients exchange?

Discovery at `/oidc/` lists the auth method `none`, and at `/cas/oidc` doesn't ([What we've seen](../testbed/assumptions.md#what-weve-seen)). That says nothing about exchange.

- **Yes:** Krini's backend can wait.
- **No:** the backend comes with proTES 0.6.0, as #391 expects. No FOCA change either way.

## What to record

| Step | Record | Result |
|---|---|---|
| Provider and clients | Provider, grant types | |
| Login | `sub`, `typ`, `aud`, `client_id`, `exp` minus `iat`, whether there's a refresh token, what the consent page lists, and whether it mentions offline access | |
| Hop 1 | Which parameter works, `aud`, `client_id`, `azp`, `exp` minus `iat`, `scope`, `typ` | |
| URL form | `aud`, the status of the call | |
| Hop 2 | `client_id` at each hop, `exp` minus `iat` at the node | |
| Orchestrator | Status, `aud` at each hop | |
| Public client | Both results, and the error if any | |
| Registration app | What it accepted, and anything that needed approval | |
