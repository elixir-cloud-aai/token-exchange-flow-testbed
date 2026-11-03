# Assumptions and constraints

All LS Login specifics are on this page. Other pages refer to its numbers. None of this has been tested with exchanges yet, which is what the [tests](../tests/index.md) are for.

## Assumptions

Taken as true until a test shows otherwise. A1 to A10 are from **the LS Login team, 2026-11-03**, in our own words.

| ID | Assumption |
|---|---|
| A1 | Exchange is allowed per client, in the [service registration app](https://services.aai.lifescience-ri.eu/): a dropdown of flows has a value that includes token exchange. |
| A2 | `aud` and `resource` are validated against the client's registered resource indicators ([RFC 8707](https://datatracker.ietf.org/doc/html/rfc8707)). |
| A3 | The client ID of the exchanging service must be in the subject token's `aud`, otherwise there's an error. This is the current proxy stack; the new stack, planned for next year, may drop it. |
| A4 | `sub` is always persistent. |
| A5 | Entitlements come from user info or introspection, computed for the client calling the exchange. |
| A6 | Refresh tokens come with the scope `offline_access`, and last 31 days for now; configurable per service in the new stack. |
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

## Constraints

| ID | Constraint | Source |
|---|---|---|
| C1 | No `act` or `can_act`. They're under consideration for the new stack. | The LS Login team, 2026-11-03 |
| C2 | A service can only exchange a token that names it in `aud` (A3), and only for targets it has registered (A2). So each client lists its next hops, and proTES's client lists every TES node, by hand. | Follows from A2 and A3 |
| C3 | The `aud` rule needs a client ID, whereas RFC 8707 resources are absolute URIs. If LS Login refuses a bare client ID as an indicator, or a token with only a URL in `aud` can't be exchanged again, chains can't work today. | Follows from A2 and A3, to be [tested in T1](../tests/t1-call-chain.md) |
| C4 | Because entitlements are computed for the exchanging client (A5), each exchanging client probably needs the group, too, not only the node. A node's token would then show what the gateway's facility releases. | Follows from A5, to be [tested in T3](../tests/t3-groups.md) |
| C5 | Lifetimes can't be set per service, until the new stack. | The LS Login team, 2026-11-03 |
| C6 | The operator's public documentation has nothing on token exchange or resource indicators, as far as we could find, and nothing on the flows of the registration app. | Our reading, 2026-11-03 |
| C7 | The testbed is local: no public hosting. LS Login only sees your browser and the testbed's outgoing requests, and the redirect URI is `http://localhost:18994/callback`. | Our choice |
| C8 | Test accounts only, as sessions record their claims. | Our choice |
| C9 | FOCA doesn't exchange tokens yet, so the testbed has its own small implementation. | FOCA 0.19.0 |
| C10 | The new proxy stack may change the `aud` rule, `act` and lifetimes. Nothing specific to the current stack should be hard-coded in FOCA or proTES. | Follows from A3, A6, A7, C1 |

## What we've been unable to do

"Assign groups" in Perun: this project's maintainer could open a facility and create a resource, but the Next button stays greyed out and no groups can be added, possibly because of a missing permission (seen by 2026-11-03). See [T3](../tests/t3-groups.md#which-role-is-needed-to-assign-groups-to-a-resource).

## What public documents say

These pages describe Perun and its proxy. They cover several Perun instances, so they may not describe LS Login exactly.

- [Entitlements](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/209813518/Entitlements): in OIDC, the values are in the `entitlements` or `eduperson_entitlement` claim of user info, and the scope `eduperson_entitlement` is required. A group entitlement is released for each group the user is in, if that group is assigned to a resource on the facility of the service.
- [Group entitlement](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/350879786/Group+entitlement): the value depends on group names, in the form `<NAMESPACE>:group:<GROUP>[:<SUBGROUP>*][#<AUTHORITY>]`, so it changes if a group is renamed or moved.
- [Resource capability](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/351272963/Resource+capability): the alternative that doesn't depend on group names. The Entitlements page recommends it for that reason.
- [Facility](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2252570626/Facility) and [Resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2261055/Resource): the entities behind A9.
- [Understanding consent pages](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742536712/Understanding+consent+pages+when+logging+in): users can deselect attributes at login, and withholding entitlements can break access.
- [Perun roles and their rights](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1760100400/Perun+roles+and+their+rights): lists assigning groups under Trusted facility admin, Resource admin and Resource self service, and not under Facility admin.
- [Terms of Use for Service Providers](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2137948170/Terms+of+Use+for+Service+Providers): apply to services that rely on LS AAI.

## What we've seen

Public discovery documents, read on 2026-11-03, without credentials:

| | `/oidc/` | `/cas/oidc` |
|---|---|---|
| Token exchange, refresh token, client credentials, device code | listed | listed |
| Auth method `none` at the token endpoint | listed | not listed |
| Scope `eduperson_entitlement` | listed | listed |
| Scope `entitlements` | listed | not listed |

The testbed uses `https://login.aai.lifescience-ri.eu/oidc/` by default. [A page on re-registration](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2184773648/Service+Provider+Re-registration+for+use+LS+AAI+Eosc+compatible+AAI) names `https://login.aai.lifescience-ri.eu/cas/oidc` as the issuer for the LS AAI EOSC node, and says other production services still use the standard process. It doesn't say whether this is the new proxy stack, which is [a question for the event](../tests/index.md#questions-outside-the-tests). Being listed says nothing about what a given client may do.

A login token of Krini's, seen by us on 2026-10-20: `typ` was `at+jwt`, and `aud` held the client's ID.
