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

Then delete `lslogin.env`, and `results/` once you've taken what you need: it holds decoded claims of the accounts used. Fill in the Result column of each test's "What to record", take what you need into [Results](../outcomes/results.md), and update the "To check" list of [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391).

To run the same against the mock, leave out `-f compose.lslogin.yaml`. Everything works, but see the table above for what it means.

## A second client, if a result is in doubt

Optional, and only if an exchange or a refusal looks odd and you want to rule out the testbed's own code. The LS Login team suggested [OAuth Tools](https://oauth.tools/) by Curity for trying exchanges: a web client whose Token Exchange Flow sends one exchange request and shows the answer. It's a comparison, not proof, as it has to use a client of its own. The same answer points away from the testbed's code, but rules can differ per client. A different answer may come from the client's registration.

It doesn't replace any test. It has no documented API or command line, so it can't be scripted or be part of the automated run. It sends one `audience` and one `resource` per request, and it knows nothing of our services, the hops behind them or the record. It shouldn't reach the mock either, as `localhost` would mean Curity's server, not your machine (we didn't try).

!!! danger "Everything you send passes through Curity's server"
    The web version doesn't call the identity provider from your browser. It sends each request to its own server, `oauth.tools/api/client/proxy`, which passes it on. That includes **the client secret, the authorization code, the subject token and the tokens that come back**. Curity says that [no data is stored on the server](https://curity.io/oauth-tools). We can't check that, so treat anything you enter as disclosed.

    - **Never enter the secret of one of the five testbed clients**, or of any client that you can't delete afterwards.
    - **Never use a real person's account**, or enter or paste their tokens. Use test accounts only.
    - **Don't use "Share link".** It stores an encrypted copy of the configuration on Curity's server.

    We saw this on 2026-11-04, in the page's code and by capturing its requests with made-up values before they left the browser. The site can change, so check again before you enter anything.

What to do, **never tried against LS Login**. We've only seen that its server fetches LS Login's public discovery document:

1. Ask the LS Login team whether they're fine with a test client's secret and a test account's tokens passing through a third party.
2. Register a sixth client just for this, in the [same way as `tx-test-client`](../setup/client-registration.md#five-clients), as confidential, with the redirect URI `https://oauth.tools/callback/code`. Give it the same resource indicators and [group release](../setup/client-registration.md#group-release), or its claims will differ for that reason alone.
3. In OAuth Tools, create a workspace from the issuer `https://login.aai.lifescience-ri.eu/oidc/`.
4. Log in with account A in a Code Flow. The session never shows its tokens, so the subject token has to come from this login.
5. In a Token Exchange Flow, send the request that was in doubt, with the same parameters as in the session. Compare the status, the error and the claims with what the session showed.
6. Afterwards, delete the client and the workspace. Tokens that were already issued stay valid until they expire.

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
| Which role is needed to assign groups to a resource? | Answered: [T3](t3-groups.md#which-role-is-needed-to-assign-groups-to-a-resource) |
| Group entitlements or resource capabilities? | [T3](t3-groups.md#questions-it-answers) |
| What is the exact entitlement value? | [T3](t3-groups.md#questions-it-answers) |
| What does "1 hour" cover, and is it capped by the subject token? | [T4](t4-lifetime.md#questions-it-answers) |
| Can an exchange return a refresh token, limited to the next hop? | [T4](t4-lifetime.md#questions-it-answers) |
| Is the 31 days idle or absolute, and do refresh tokens rotate? | [T4](t4-lifetime.md#questions-it-answers) |
| Are refresh tokens bound to the client, and is reuse detected? | [T4](t4-lifetime.md#questions-it-answers) |
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

### Can users see and revoke what a service holds?

For [delegated access](../testbed/delegated-access.md#user-control), a user should be able to see that Conquest may act for them, and withdraw that at LS Login. The profile has "Revoke consent" per service ([C12](../testbed/assumptions.md#constraints)).

- Does it also end the refresh tokens that the service holds? And the access tokens issued with them?
- Does logging out at LS Login end refresh tokens?
- **If neither:** only the service itself can end a run's access early, by revoking at `/oidc/revoke`, and Conquest's docs have to say so to users.

Checking it by hand ends the session's refresh tokens, so do it last, if at all: revoke the consent of the client in the profile, then try `refresh` once more.

### Can registration be automated?

Is there an API for clients' resource indicators? proTES #391 says that targets are listed by hand for now, later through the Cloud Registry.

- **No API:** this stays manual, and the registry's plans leave it out.
- **API:** the Cloud Registry's plans can include it, with whoever holds the credentials for it.
