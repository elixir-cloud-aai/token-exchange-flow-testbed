# Tests

!!! warning "Expected results are not observations"
    Nothing here has run against LS Login. Against LS Login, every expectation is what the LS Login team's answers of 2026-11-03 or the standards suggest. If you see something else, that's a result: record it. On the mock, the `tb>` lines were executed, except for `wait-expiry`, and some only up to a refusal or usage error: see [Testbed limits](../testbed/limits.md).

## The tests

| Test | What it shows | Mock | LS Login |
|---|---|---|---|
| [T1 Delegated call chain](t1-call-chain.md) | One sign-in, then one token per hop, all the way to the node | Commands only: `aud` and `client_id` come from our config | The result |
| [T2 Refused requests](t2-refused.md) | What must fail, who refuses it, and how | Exchanges: refused by our own rules. Services: real checks | The result |
| [T3 Groups and entitlements](t3-groups.md) | Who gets which entitlement, and whether people outside a group are locked out | Commands only: no entitlements per client | The result |
| [T4 Token lifetime and refresh](t4-lifetime.md) | What lifetimes mean, and how long-running work gets tokens | Commands only: lifetimes come from our config, and no refresh token from an exchange | The result |
| [T5 Attribution across hops](t5-attribution.md) | What a node can tell about a request's path, and how a request can be followed | Same claims on both paths; hop limit and tracing are real | The result |

## Order for a live session

Prepare, as early as possible:

1. Accounts, clients and group release: see [Client registration](../setup/client-registration.md). We don't know whether registrations need approval.
2. `lslogin.env`: see [Configuration](../setup/configuration.md).
3. The [automated run against the mock](../setup/checking.md#the-automated-run) must pass.
4. Try T1 up to the second hop once beforehand, so that the session isn't spent on registration mistakes.
5. **At least an hour before you need the result,** start [the expiry part of T4](t4-lifetime.md#expired-token), as it takes as long as tokens live. It runs in its own terminal.

Terminal 1, the services. Their logs show decoded claims only:

```sh
docker compose -f compose.lslogin.yaml up -d --wait services
docker compose -f compose.lslogin.yaml logs -f services
```

Terminal 2, the session. Tokens live only in this process, so keep it open. Results are appended to `results/session.jsonl`, as decoded claims:

```sh
docker compose -f compose.lslogin.yaml run --rm session --record /results/session.jsonl
```

Then, all in that one session, as later tests use the tokens of earlier ones: T1, T2, T3, T4, T5. Log in with account A, unless a step says otherwise.

Tokens may expire during the session, as exchanged tokens are expected to live 1 hour ([A7](../testbed/assumptions.md#assumptions)). T4 and T5 start with new ones. If an exchange is refused or a call gives 401 with the reason `expired`, check `seconds_left` in `lifetimes` before you record it as a result.

Afterwards:

```text
quit
```

```sh
docker compose -f compose.lslogin.yaml down -v
```

Then delete `lslogin.env`, and `results/` once you've taken what you need: it holds decoded claims of the accounts used. Copy what you need into Results, and update the "To check" list of [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391).

To run the same against the mock, leave out `-f compose.lslogin.yaml`. Everything works, but see the table above for what it means.

## Questions the tests answer

Each one is explained on its test's page, with what its outcome changes.

| Question | Test |
|---|---|
| Are bare client IDs accepted as resource indicators? | [T1](t1-call-chain.md#questions-it-answers) |
| Can a token with only a URL in `aud` be exchanged again? | [T1](t1-call-chain.md#questions-it-answers) |
| Which parameter names the target: `audience`, `resource` or both? | [T1](t1-call-chain.md#questions-it-answers) |
| What's in `client_id` after an exchange? | [T1](t1-call-chain.md#questions-it-answers) |
| Do exchanged tokens have the same `typ`, `alg` and keys as login tokens? | [T1](t1-call-chain.md#questions-it-answers) |
| Can public clients exchange? | [T1](t1-call-chain.md#questions-it-answers) |
| What are the error codes of refusals? | [T2](t2-refused.md#questions-it-answers) |
| Does LS Login check the subject token's signature and expiry? | [T2](t2-refused.md#questions-it-answers) |
| Which group release does a node see, and per which client? | [T3](t3-groups.md#questions-it-answers) |
| How can a group be released without locking out users outside it? | [T3](t3-groups.md#questions-it-answers) |
| Which role is needed to assign groups to a resource? | [T3](t3-groups.md#questions-it-answers) |
| Group entitlements or resource capabilities? | [T3](t3-groups.md#questions-it-answers) |
| What is the exact entitlement value? | [T3](t3-groups.md#questions-it-answers) |
| What does "1 hour" cover, and is it capped by the subject token? | [T4](t4-lifetime.md#questions-it-answers) |
| Can an exchange return a refresh token, limited to the next hop? | [T4](t4-lifetime.md#questions-it-answers) |
| Is the 31 days idle or absolute, and do refresh tokens rotate? | [T4](t4-lifetime.md#questions-it-answers) |
| Is `act` coming? | [T5](t5-attribution.md#questions-it-answers) |

## Questions outside the tests

No command answers these. They're for the LS Login team.

### What does the new proxy stack change, and when?

The LS Login team named the `aud` rule, `act`, lifetimes and refresh token lifetimes as possibly changing (2026-11-03).

- The timeline decides whether FOCA reads `act` as optional from the start.
- [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391) and FOCA keep these configurable either way.
- Is there a test instance, so that we can check our chain before the switch?

### Is `/cas/oidc` the new proxy stack?

A page of the operator names that issuer for another node, and the discovery documents differ: see [What we've seen](../testbed/assumptions.md#what-weve-seen).

- **If it is:** do the rules we were told apply to it already? The testbed can be pointed to it with `TESTBED_ISSUER`.
- **Which issuer should new test clients use?** Tokens of one aren't accepted by services that trust the other, so all services of a chain have to move together.

### Can registration be automated?

Is there an API for clients' resource indicators? proTES #391 says that targets are listed by hand for now, later through the Cloud Registry.

- **No API:** this stays manual, and the registry's plans leave it out.
- **API:** the Cloud Registry's plans can include it, with whoever holds the credentials for it.
