# Delegated access: consent and lifetime

Conquest runs a workflow for hours or days, long after the user's tokens have expired, and still has to start tasks on their behalf. Asking the user again every hour isn't practical once they've agreed to the whole run. Refreshing without a bounded, explicit grant isn't acceptable either. The [Design](../background/design.md#delegation-across-hops) describes the end state for this. This page takes its six points one by one: what each needs from the identity provider, what we know of LS Login, what the testbed does and shows, and what's open.

!!! warning "Little of this is known for LS Login"
    What we know of LS Login comes from its team's answers of 2026-11-03, its public discovery document and the operator's public pages, all under [Assumptions and constraints](assumptions.md), and is cited by number here. **Nothing on this page has run against LS Login.** Where we don't know, it says so. [T4](../tests/t4-lifetime.md) is where most of it gets answered.

## Summary

| Point | Needs from the identity provider | LS Login | Testbed |
|---|---|---|---|
| [Consent once](#consent-once-explicitly) | A consent page for offline access that names the workflow system and a duration | `offline_access` listed; what the consent page says about it is unknown | Requests `offline_access` at login; never logs users in at the orchestrator |
| [Bounded grant](#bounded-grant) | Absolute lifetime per grant, rotation, reuse detection, binding to a confidential client | 31 days for all, idle or absolute unknown; rotation and reuse detection unknown; no sender-constrained tokens | Shows rotation and the 31 days' kind; checks binding and reuse detection |
| [Least privilege downstream](#least-privilege-downstream) | Short-lived access tokens for one audience, by exchange or refresh | 1 hour; `aud` limited to registered targets | Services keep no refresh token, and pass on access tokens only |
| [User control](#user-control) | A list of grants to revoke; a revocation endpoint | Revocation endpoint listed; "Revoke consent" in the profile, effect on refresh tokens unknown | Revokes, then checks that the refresh fails |
| [New consent only on change](#new-consent-only-on-change) | Refresh can't widen scope; new targets need new consent | Targets come from the client's registration, not from the user | Not tested |
| [Delegation in tokens](#delegation-visible-in-tokens) | `act` | Not supported | Compares the paths, and relies on logs |

## Consent once, explicitly

**What it needs.** At submission, the user agrees once, on the identity provider's page, to the workflow system acting for them, and for how long. The request for it is `offline_access`. [OpenID Connect Core, section 11](https://openid.net/specs/openid-connect-core-1_0.html#OfflineAccess) requires consent for it, and `prompt=consent` with the request, unless "other conditions" allow offline access. Refreshing within the grant asks nothing more.

**LS Login.** It lists `offline_access`, and refresh tokens come with it ([A6](assumptions.md#assumptions), [What we've seen](assumptions.md#what-weve-seen)). The operator's pages describe the consent page as a list of attributes released to the service. They say nothing about offline access, or for how long a service may act ([What public documents say](assumptions.md#what-public-documents-say)). Whether the page mentions either, we don't know.

**Testbed.** `login` asks for `openid entitlements offline_access` by default, and sends no `prompt` parameter. So whether LS Login returns a refresh token without `prompt=consent` is part of [T1](../tests/t1-call-chain.md#login-user-to-client), as is what the consent page lists. Consent is then given to `tx-test-client`, the portal, and not to the orchestrator:

- The orchestrator's client is registered without the authorization code flow or a redirect URI ([Client registration](../setup/client-registration.md#five-clients)), so the user never sees a page that names it.
- Its refresh token can only come from an exchange ([T4](../tests/t4-lifetime.md#refresh-token-from-an-exchange)), at the token endpoint, with no user present. If LS Login issues one there, its own policy decides, not a consent the user gave to Conquest.

**Open.** How to get explicit consent for the workflow system: by naming it as a resource in the portal's login, if LS Login shows that on the consent page, or by a login at the workflow system's own client. Neither is in the testbed.

## Bounded grant

**What it needs.** The refresh token ends at a fixed time, the expected length of the run plus a margin, however often it's used. It rotates at each use, and the reuse of an old one revokes the grant ([RFC 9700, section 4.14](https://datatracker.ietf.org/doc/html/rfc9700#section-4.14)). Only the workflow system can redeem it, as a confidential client: [RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749#section-6) already binds a confidential client's refresh token to that client.

**LS Login.**

- **Lifetime:** 31 days "for now", the same for all, and configurable per service only in the new stack ([A6](assumptions.md#assumptions), [C5](assumptions.md#constraints)). A lifetime per run, from what the user agreed to, isn't offered. Whether the 31 days are idle or absolute, we don't know.
- **Rotation and reuse detection:** unknown.
- **Binding:** by client authentication only. The discovery document lists client secrets and `none`, and no DPoP or certificate-bound tokens ([C11](assumptions.md#constraints)). A public client's refresh token still belongs to its client ID, but without a secret, whoever holds it can redeem it as that client. So the workflow system must be a confidential client.

**Testbed.**

- `refresh` reports `refresh_token_rotated`: `true` if a new refresh token came back, `false` if the same one did, `null` if none did. Without a new one, the session keeps the old one, as RFC 6749 allows.
- [T4](../tests/t4-lifetime.md#31-days-idle-or-absolute) compares `exp` of two refresh tokens, 10 minutes apart, if the tokens are JWTs or introspection shows `exp`. A fixed `exp` shows an absolute limit. A moving one shows a sliding window for each token, but doesn't rule out a separate cap on the whole grant: only LS Login can confirm that. The 31 days themselves can't be waited for.
- [T4](../tests/t4-lifetime.md#binding-and-reuse) tries to redeem the client's refresh token as another client, and to reuse a rotated one.
- On the mock, none of this is evidence: any client can redeem any refresh token, and nothing rotates or ends ([What the mock can't show](limits.md#what-the-mock-cant-show)).

**Open.** With one lifetime for all, the workflow system can only end the grant earlier by itself: by revoking the refresh token when the run ends or its deadline has passed. That's a duty of Conquest's, not a limit the identity provider enforces.

## Least privilege downstream

**What it needs.** The refresh token never leaves the workflow system. For each step, the workflow system gets a short-lived access token for the one TES or WES that step needs, by exchange ([RFC 8693](https://datatracker.ietf.org/doc/html/rfc8693)) or by a refresh limited to that target.

**LS Login.** Exchanged tokens live "currently 1 hour" ([A7](assumptions.md#assumptions)), and their `aud` is checked against the targets registered for the exchanging client ([A2](assumptions.md#assumptions)). Whether `aud` then holds only that target is a question for [T1](../tests/t1-call-chain.md#questions-it-answers).

**Testbed.**

- The services, `gateway` and `orchestrator`, exchange the access token they received, once per request, without `requested_token_type`, so that LS Login picks the type. They forward only the access token, and keep nothing after the request. `TESTBED_EXCHANGE_SCOPE` sets the scope they ask for. If LS Login returns a refresh token anyway, the report shows it as decoded claims, or "present", and the service drops it.
- In the session, `--as orchestrator` plays the part of Conquest's long-running side: [T4](../tests/t4-lifetime.md#only-if-that-returned-one) redeems the orchestrator's refresh token with `--audience @gateway`, and calls the gateway with the result.

## User control

**What it needs.** The user can see the grant at the identity provider, and revoke it there. Cancelling the run makes the workflow system revoke it, at the revocation endpoint ([RFC 7009](https://datatracker.ietf.org/doc/html/rfc7009)).

**LS Login.** Its discovery document lists `https://login.aai.lifescience-ri.eu/oidc/revoke` ([What we've seen](assumptions.md#what-weve-seen)). A user's profile lists the services they have consented to, with a "Revoke consent" button. Whether that also ends the service's refresh tokens, and whether users can see refresh tokens at all, nothing public says ([C12](assumptions.md#constraints)). [RFC 9700](https://datatracker.ietf.org/doc/html/rfc9700#section-4.14) also allows a provider to revoke refresh tokens at logout, which would end a run when the user logs out elsewhere. Whether LS Login does, we don't know.

**Testbed.**

- `revoke <name> --as <role> --refresh` sends the refresh token to the revocation endpoint. Its `ok` only means status 200, which RFC 7009 also returns for a token that wasn't valid. What counts is the refresh after it, which must fail: [T4](../tests/t4-lifetime.md#only-if-that-returned-one).
- There are no workflows to cancel. Revoking `ro-b` in T4 stands for it.
- **Revoking doesn't reach access tokens already issued.** The services validate access tokens offline, from signature and `exp`, as FOCA does. A gateway accepts a token issued before the revocation until it expires, up to an hour later ([A7](assumptions.md#assumptions)). Whether LS Login then refuses to exchange it, or the node's call to user info fails, depends on whether revoking a refresh token also revokes the access tokens issued with it. We don't know.

## New consent only on change

**What it needs.** New consent for broader scopes, other services or more sensitive data. Not because time has passed. [RFC 6749, section 6](https://datatracker.ietf.org/doc/html/rfc6749#section-6) already forbids a refresh from widening the scope.

**LS Login.** Whether it refuses a refresh with a wider scope, we don't know. The targets a client can exchange for are set in its registration ([A2](assumptions.md#assumptions), [C2](assumptions.md#constraints)), not by the user: a new TES node becomes reachable when the gateway's registration lists it, without any new consent.

**Testbed.** No test asks for a wider scope. `refresh --scope` could, if this needs an answer.

## Delegation visible in tokens

**What it needs.** An `act` claim ([RFC 8693, section 4.1](https://datatracker.ietf.org/doc/html/rfc8693#section-4.1)) that names the workflow system as the party acting for the user, set by the identity provider.

**LS Login.** No `act` or `can_act`. Both are under consideration for the new stack ([C1](assumptions.md#constraints)).

**Testbed.** Each service reports `act`, if a token has one. Instead of `act`, [T5](../tests/t5-attribution.md) shows what's left: `sub` names the user, `aud` the next service, and `client_id`, at best, the last caller. Whether Conquest was involved can't be read from a token. Accounting and provenance then rest on the services' logs, and on `traceparent`, which any hop can reset.

## Questions for LS Login

Still to find out from LS Login. Each test's page says what its answer changes.

| Question | Where it gets answered |
|---|---|
| Are the 31 days idle or absolute? | [T4](../tests/t4-lifetime.md#is-the-31-days-idle-or-absolute-and-do-refresh-tokens-rotate) |
| Do refresh tokens rotate, and is reuse detected? | [T4](../tests/t4-lifetime.md#are-refresh-tokens-bound-to-the-client-and-is-reuse-detected) |
| Can an exchange return a refresh token, limited to the next hop? | [T4](../tests/t4-lifetime.md#can-an-exchange-return-a-refresh-token-limited-to-the-next-hop) |
| Can exchanged tokens be limited to one audience? | [T1](../tests/t1-call-chain.md#questions-it-answers) |
| Does the consent page mention offline access, and for how long? | [T1](../tests/t1-call-chain.md#login-user-to-client), by looking |
| Can users see and revoke a service's refresh tokens? | [Outside the tests](../tests/index.md#can-users-see-and-revoke-what-a-service-holds) |
