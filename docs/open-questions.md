# Open questions

Everything we don't know, for the LS Login team to answer or for the [session](session.md) to show. Each question has what its outcome changes. Decisions refer to the design in [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391). Step numbers are those of the [session page](session.md).

## Decide the design

### Are bare client IDs accepted as resource indicators? {#bare-ids}

Or how else does the next hop's ID get into `aud`? (Steps 3, 4)

- **Yes:** FOCA's outgoing exchange names targets by client ID, and #391's token flow stands.
- **No:** the `aud` rule and URL indicators clash, and chains can't work. This blocks #391's token flow until one of them changes. proTES 0.5.0's architecture stays the fallback.

### Can a token with only a URL in `aud` be exchanged again?

(Step 4) We expect not, since the exchanging client's ID must be in `aud`.

- **No:** tokens for a service that forwards must carry its client ID. URL forms only work for the last hop.
- **Yes:** the `aud` rule is looser than described, and either form works. Then we need to know how LS Login maps a URL to a client.

### Can an exchange return a refresh token, limited to the next hop?

(Steps 19, 20)

- **Yes:** the orchestrator holds it per run. FOCA adds encrypted storage and revocation helpers.
- **No:** Conquest can't mint tokens days later. Options to weigh: Krini's backend holds the user's refresh token and exchanges on demand, or service tokens for that hop only. #391's "Long-running work" changes.

### Is the 31 days idle or absolute, and do refresh tokens rotate?

(Steps 17, 18)

- **Absolute:** it's the maximum length of a run, which goes into Conquest's docs.
- **Idle:** runs are unlimited, as long as they refresh in time.
- **Rotation:** FOCA's helper has to store the new token atomically, as a lost one ends the run.

### Can public clients exchange?

(Step 8) Discovery at `/oidc/` lists the auth method `none`, and at `/cas/oidc` doesn't. That says nothing about exchange.

- **Yes:** Krini's backend can wait, and #391 gets its tick.
- **No:** the backend comes with proTES 0.6.0, as #391 expects. No FOCA change either way.

## Groups {#groups}

### Which group release does a node see, and per which client? {#release}

Entitlements are computed for the client calling the exchange. (Steps 14, 15) Group release as such is confirmed: the group is assigned to a resource on the service's facility.

- **The exchanging client's, as #391 assumes:** each gateway's facility needs the group of everything downstream. That goes into #391's registration notes and the operator docs.
- **If `introspect --as node` gives the node's own view, and we want that:** FOCA needs introspection, as it only has user info today.
- **Does the exchange need `scope` for this?** Then FOCA's exchange gets a scope setting per target.

### How can a group be released without locking out users outside it?

Confirmed by the LS Login team, 2026-11-03: to let anyone with a valid LS Login account log in, create a second resource for the Lifescience VO and assign its members group. What's still open (step 16):

- **Is the second resource needed on every client in the chain,** or only on those that log in users? In other words: can a gateway exchange for a user who isn't in any group assigned to its facility?
  - **Only those that log in users:** registering a gateway stays simple.
  - **Every client:** each one needs that resource, which goes into the registration notes.
- **Are users outside a group ever stopped at LS Login in the first place, and by what setting?**
  - **No:** node policy decides, with a 403, and Krini shows "request compute access".
  - **Yes:** find out which setting caused it before registering Krini.
- **Does the members group add an entitlement that nodes see for all users?** Node policies must not match it by accident.

### Which role is needed to assign groups to a resource? {#role}

It has been possible to open a facility and create a resource, but in "Assign groups" the Next button stays greyed out and no groups can be added, possibly because of a missing permission.

The operator's [roles page](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1760100400/Perun+roles+and+their+rights) lists assigning groups under Trusted facility admin, Resource admin and Resource self service, and not under Facility admin, which is what creating a facility gives. It doesn't say which one applies here, or who grants it for a VO's group.

**What it changes:** which role a service's operators need to ask for, and from whom. Without it, nobody can set up group release for a new service by themselves, so this goes into the operator docs of every service in the chain.

### Group entitlements or resource capabilities?

The operator's [Entitlements page](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/209813518/Entitlements) recommends [resource capabilities](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/351272963/Resource+capability), as group entitlements change when a group is renamed or moved. Are they available on LS Login, for a client like these?

- **Yes:** node policies can match a capability rather than a group's name. `TESTBED_REQUIRED_ENTITLEMENT` takes either, so the testbed can try it.
- **No:** nodes match group entitlements and break if groups are renamed, which the operator docs should say.

### What is the exact entitlement value?

`TESTBED_REQUIRED_ENTITLEMENT` holds `urn:geant:lifescience-ri.eu:group:elixir:ECP_CLN#aai.lifescience-ri.eu`, derived from a known entitlement of the same form. (Step 14) It's a configurable example: if it differs, nodes get another value in their settings, and nothing else changes.

## Tokens

### What does "1 hour" cover, and is it capped by the subject token?

Does it cover only exchanged tokens? (Steps 2, 3, 7) A login token of Krini's lived 4 hours on 2026-10-20.

- Sets the margin of FOCA's cache per user and audience, until shortly before expiry.
- **If it's capped:** an old login token shortens each hop, so clients have to refresh before exchanging. That goes into the docs for #391's clients.

Lifetimes stay configurable in FOCA either way, as the new stack will change them.

### What's in `client_id` after an exchange?

(Steps 3, 5)

- **The exchanging client:** nodes can allow-list their callers with FOCA's `security.auth.clients`. As `sub` is the user, FOCA treats them as user tokens, which is right.
- **The original client:** nodes can't see even the last hop. That goes into #391's "Identity and tracing", and strengthens the case for `act`.

### Do exchanged tokens have the same `typ`, `alg` and keys as login tokens?

(Steps 3, 5)

- **Yes:** nothing changes.
- **No:** FOCA's settings `token_types` and `algorithms` have to allow them, on every node. That would need to go into the operator docs, or ideally get fixed on LS Login's side.

### Which parameter names the target: `audience`, `resource` or both?

(Step 3) The LS Login team says that both are validated. The outcome decides the default of FOCA's outgoing exchange, and what ends up in `aud` for each.

### What are the error codes of refusals?

(Steps 9 to 11) The testbed's codes on the mock are guesses. FOCA has to tell a refused exchange from an unreachable provider, and report it to callers.

## The future

### What does the new proxy stack change, and when?

The `aud` rule, `act`, lifetimes and refresh token lifetimes were named as possibly changing. (Step 21)

- The timeline decides whether FOCA reads `act` as optional from the start. We'd do so, as it's cheap and changes nothing today.
- #391 and FOCA keep these configurable either way.
- Is there a test instance, so that we can check our chain before the switch?

### Is `/cas/oidc` the new proxy stack?

A [page on re-registration](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2184773648/Service+Provider+Re-registration+for+use+LS+AAI+Eosc+compatible+AAI) names that issuer for the LS AAI EOSC node. The discovery documents differ, as shown in What LS Login requires.

- **If it is:** do the rules on this site apply to it already? The testbed can be pointed to it with `TESTBED_ISSUER`.
- **Which issuer should new test clients use?** Tokens of one aren't accepted by services that trust the other, so all services of a chain have to move together.

### Is `act` coming?

The ask: nested `act` ([RFC 8693, section 4.1](https://datatracker.ietf.org/doc/html/rfc8693#section-4.1)), set by LS Login from the exchanging client. See What can't work yet.

- **Yes:** the chain comes from nested `act` claims, and a gateway finding itself in the chain refuses the request.
- **No:** provenance and accounting stay in logs, with `traceparent`.

### Can registration be automated?

Is there an API for clients' resource indicators? #391 says that targets are listed by hand for now, later through the Cloud Registry.

- **No API:** this stays manual. Note that in #391, and leave it out of the registry's plans.
- **API:** the Cloud Registry's plans can include it, with whoever holds the credentials for it.
