# Assumptions and constraints

All LS Login specifics are on this page. Other pages refer to its numbers. Most of it comes from the LS Login team's answers, and the [tests](../tests/index.md) check it with exchanges.

## Assumptions

Taken as true until a test shows otherwise. A1 to A10 are from **the LS Login team, 2026-11-03**, in our own words.

| ID | Assumption |
|---|---|
| A1 | Exchange is allowed per client, in the [service registration app](https://services.aai.lifescience-ri.eu/): a dropdown of flows has a value that includes token exchange. |
| A2 | `aud` and `resource` are validated against the client's registered resource indicators ([RFC 8707](https://datatracker.ietf.org/doc/html/rfc8707)). |
| A3 | The client ID of the exchanging service must be in the subject token's `aud`, otherwise there's an error. This is the current proxy stack; the new stack, planned for next year, may drop it. |
| A4 | `sub` is always persistent. |
| A5 | Entitlements come from user info or introspection, computed for the client calling the exchange. |
| A6 | Refresh tokens come with the scope `offline_access`, and last 31 days for now; configurable per service in the new stack. The LS Login team added on 2026-11-19 that the limit is idle: see [A17](#assumptions). |
| A7 | The lifetime is "currently 1 hour", configurable in the new stack. It isn't clear whether this means only exchanged tokens: a login token of Krini's lived 4 hours on 2026-10-20 (our own observation). |
| A8 | Testing against production LS AAI is fine. |
| A9 | A **facility** is a client's representation in Perun IDM. A **resource** represents the relationship between that facility and a VO. To get a group entitlement, assign the group to a resource on the service's facility. Krini does this with `ECP_CLN:ADMIN`. A client that needs admin mapping only needs that one group, not the whole `ECP_CLN` structure. |
| A10 | To let anyone with a valid LS Login account log in, create a second resource for the Lifescience VO and assign its members group. |

Our own assumptions, from no statement at all:

| ID | Assumption |
|---|---|
| A11 | LS Login checks the signature and expiry of the subject token. The mock doesn't, so the testbed's rules do it for local runs. |
| A12 | The value of `TESTBED_REQUIRED_ENTITLEMENT` in the template, `urn:geant:lifescience-ri.eu:group:elixir:ECP_CLN#aai.lifescience-ri.eu`. We derived it from a known entitlement of the same form. `ECP_CLN` is a configurable example. |
| A13 | The client settings under [Client registration](../setup/client-registration.md), inferred from A1 to A10. We haven't gone through the whole registration app. |

From **the LS Login team, 2026-11-19**, in our own words ([#36](https://github.com/elixir-cloud-aai/token-exchange-flow-testbed/issues/36)):

| ID | Assumption |
|---|---|
| A14 | Resource indicators of type URI, and for now bare client IDs, are added to a client's registration by the operators, by hand. |
| A15 | All test clients have the admin group of `ECP_CLN` released, except the orchestrator's, so that T3 has one client without it to compare. |
| A16 | Every LS AAI user may use the testbed's services. |
| A17 | Refresh tokens expire 31 days after they're issued, unless used; each refresh returns a new one with another 31 days. An absolute limit on the grant wasn't mentioned. |
| A18 | Refresh tokens rotate: the one used is revoked. Reuse detection is enabled. |
| A19 | `aud` of an exchanged token holds the values requested with `resource` or `audience`, and the client ID of the client calling the exchange. |
| A20 | Users probably can't review the grants they gave a service. They can revoke their tokens themselves. Consent can only be revoked through a support request. |
| A21 | Refresh tokens probably stay valid when the user logs out. Users can have several sessions, and single logout across services isn't implemented. |

## Constraints

| ID | Constraint | Source |
|---|---|---|
| C1 | No `act` or `can_act`. They're under consideration for the new stack. | The LS Login team, 2026-11-03 |
| C2 | A service can only exchange a token that names it in `aud` (A3), and only for targets it has registered (A2). So each client lists its next hops, and proTES's client lists every TES node, by hand. | Follows from A2 and A3 |
| C3 | The `aud` rule needs a client ID, whereas RFC 8707 resources are absolute URIs. If LS Login refuses a bare client ID as an indicator, or a token with only a URL in `aud` can't be exchanged again, chains can't work today. The operators add bare client IDs as indicators by hand, for now ([A14](#assumptions)). | Follows from A2 and A3, to be [tested in T1](../tests/t1-call-chain.md) |
| C4 | Because entitlements are computed for the exchanging client (A5), each exchanging client probably needs the group, too, not only the node. A node's token would then show what the gateway's facility releases. | Follows from A5, to be [tested in T3](../tests/t3-groups.md) |
| C5 | Lifetimes can't be set per service, until the new stack. | The LS Login team, 2026-11-03 |
| C6 | The operator's public documentation has nothing on token exchange or resource indicators, as far as we could find, and nothing on the flows of the registration app. | Our reading, 2026-11-03 |
| C7 | The testbed is local: no public hosting. LS Login only sees your browser and the testbed's outgoing requests, and the redirect URI is `http://localhost:18994/callback`. | Our choice |
| C8 | Test accounts only, as sessions record their claims. | Our choice |
| C9 | FOCA doesn't exchange tokens yet, so the testbed has its own small implementation. | FOCA 0.19.0 |
| C10 | The new proxy stack may change the `aud` rule, `act` and lifetimes. Nothing specific to the current stack should be hard-coded in FOCA or proTES. | Follows from A3, A6, A7, C1 |
| C11 | No sender-constrained tokens: the discovery document lists neither DPoP nor certificate-bound tokens. A refresh token belongs to the client ID it was issued to, and only that client's authentication proves who redeems it. A public client has no secret, so whoever holds its refresh token can redeem it as that client. | [What we've seen](#what-weve-seen), 2026-11-13 |
| C12 | Users probably can't see a service's grant, and consent can only be revoked through a support request ([A20](#assumptions)), whereas the operator's privacy page describes a "Revoke consent" button in the profile. Whether revoking consent, or a user revoking their tokens, ends a service's refresh tokens, nobody has said. | [What public documents say](#what-public-documents-say); the LS Login team, 2026-11-19 |

## What we've been unable to do

"Assign groups" in Perun: this project's maintainer could open a facility and create a resource, but the Next button stays greyed out and no groups can be added (seen by 2026-11-03). This is now answered: it takes TrustedFacilityAdmin within the relevant VO, which the VO admins don't grant for this setup; they assign groups on request. See [Client registration](../setup/client-registration.md#who-can-assign-groups) and [T3](../tests/t3-groups.md#which-role-is-needed-to-assign-groups-to-a-resource).

## What public documents say

These pages describe Perun and its proxy. They cover several Perun instances, so they may not describe LS Login exactly.

- [Entitlements](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/209813518/Entitlements): in OIDC, request the `entitlements` scope to receive the values in the `entitlements` claim at the UserInfo endpoint, as specified by [AARC-G069](https://aarc-community.org/guidelines/aarc-g069/). Other clients of the same issuer got another claim, though: see [What we've seen](#what-weve-seen). The testbed's login asks for the scope `entitlements`, and the node reads both claims (`TESTBED_ENTITLEMENT_CLAIMS` in [Configuration](../setup/configuration.md#settings)). A group entitlement is released for each group the user is in, if that group is assigned to a resource on the facility of the service.
- [Group entitlement](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/350879786/Group+entitlement): the value depends on group names, in the form `<NAMESPACE>:group:<GROUP>[:<SUBGROUP>*][#<AUTHORITY>]`, so it changes if a group is renamed or moved.
- [Resource capability](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/351272963/Resource+capability): the alternative that doesn't depend on group names. The Entitlements page recommends it for that reason.
- [Facility](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2252570626/Facility) and [Resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2261055/Resource): the entities behind A9.
- [Understanding consent pages](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742536712/Understanding+consent+pages+when+logging+in): users can deselect attributes at login, and withholding entitlements can break access.
- [Perun roles and their rights](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1760100400/Perun+roles+and+their+rights): lists assigning groups under Trusted facility admin, Resource admin and Resource self service, and not under Facility admin.
- [Terms of Use for Service Providers](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2137948170/Terms+of+Use+for+Service+Providers): apply to services that rely on LS AAI.
- [Privacy: what data does Perun AAI keep about me?](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742700554/Privacy+What+data+does+Perun+AAI+keep+about+me): the user's profile has a Consents section, which lists the services a user has granted access to their personal data, with the attributes each one gets, and a **Revoke consent** button that "immediately withdraws the service's permission to use your personal information". It says nothing about refresh tokens or offline access ([C12](#constraints)).
- The consent page (see above) is about attributes: which ones are released to the service, and which the user may deselect. It says nothing about offline access, or how long a service may act.
- Nothing we found in the operator's pages (read on 2026-11-03) states lifetimes of refresh tokens, rotation, reuse detection, or what revoking does. For lifetimes, A6 and A7 were all we had until the answers below.
- The LS Login team's answers of 2026-11-19 on refresh tokens and consent: [A17](#assumptions) to [A21](#assumptions), [C12](#constraints).

## What we've seen

Public discovery documents, read on 2026-11-03, without credentials:

| | `/oidc/` | `/cas/oidc` |
|---|---|---|
| Token exchange, refresh token, client credentials, device code | listed | listed |
| Auth method `none` at the token endpoint | listed | not listed |
| Scope `entitlements` | listed | not listed |

The testbed uses `https://login.aai.lifescience-ri.eu/oidc/` by default. [A page on re-registration](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2184773648/Service+Provider+Re-registration+for+use+LS+AAI+Eosc+compatible+AAI) names `https://login.aai.lifescience-ri.eu/cas/oidc` as the issuer for the LS AAI EOSC node, and says other production services still use the standard process. It doesn't say whether this is the new proxy stack, which is [a question for the event](../tests/index.md#questions-outside-the-tests). Being listed says nothing about what a given client may do.

The `/oidc/` document again, on 2026-11-13, for [delegated access](delegated-access.md):

- **Listed:** the scope `offline_access`; the grants `refresh_token` and token exchange; a revocation endpoint, `https://login.aai.lifescience-ri.eu/oidc/revoke`; an introspection endpoint; the token endpoint authentication methods `client_secret_basic`, `client_secret_post` and `none`.
- **Not listed:** `prompt_values_supported`, `dpop_signing_alg_values_supported`, `tls_client_certificate_bound_access_tokens` and `backchannel_logout_supported`. A missing field doesn't prove that a feature is missing, but no standard way of binding tokens to a client instance is advertised ([C11](#constraints)).

Entitlements as LS Login released them to other clients of the `/oidc/` issuer (read on 2026-11-12 and 2026-11-15, recorded in [generic-issues#46](https://github.com/elixir-cloud-aai/generic-issues/issues/46)): in the claim **`eduperson_entitlement`**, not `entitlements`, and in user info only. The access token carried the scope `eduperson_entitlement`, but not the values. Which claim the testbed's clients get with the scope `entitlements` is unknown until [T1](../tests/t1-call-chain.md) and [T3](../tests/t3-groups.md) have run, so the node reads both, and trusts them equally. That's only safe if LS Login fills both from Perun's groups, not from attributes of a user's home organisation, which nothing public says. Once T3 has shown which claim the clients get, set `TESTBED_ENTITLEMENT_CLAIMS` to that one.

A login token of Krini's, seen by us on 2026-10-20: `typ` was `at+jwt`, and `aud` held the client's ID.
