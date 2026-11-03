# What LS Login requires

This page separates what we were told, what public documents say, and what we've seen. None of it has been tested with exchanges yet: see [Open questions](../open-questions.md).

## What the LS Login team told us

From the LS Login team, 2026-11-03, in our own words:

- **Exchange** is allowed per client, in the [service registration app](https://services.aai.lifescience-ri.eu/): a dropdown of flows has a value that includes token exchange.
- **Targets:** `aud` and `resource` are validated against the client's registered resource indicators ([RFC 8707](https://datatracker.ietf.org/doc/html/rfc8707)).
- **Subject token:** the client ID of the exchanging service must be in the subject token's `aud`, otherwise there's an error. This is the current proxy stack; the new stack, planned for next year, may drop it.
- **`act` and `can_act`** aren't supported. They're under consideration for the new stack.
- **Subject and groups:** `sub` is always persistent. Entitlements come from user info or introspection, computed for the client calling the exchange.
- **Refresh tokens** come with the scope `offline_access` and last 31 days for now; configurable per service in the new stack.
- **Lifetime:** "currently 1 hour", configurable in the new stack. It isn't clear whether this means only exchanged tokens: a login token of Krini's lived 4 hours on 2026-10-20.
- **Testing** against production LS AAI is fine.

On group release, also from the LS Login team, 2026-11-03:

- A **facility** is a client's representation in Perun IDM. A **resource** represents the relationship between that facility and a VO.
- To get a group entitlement, assign the group to a resource on the service's facility. Krini does this with `ECP_CLN:ADMIN`.
- A client that needs admin mapping only needs that one group, not the whole `ECP_CLN` structure.
- To let anyone with a valid LS Login account log in, create a second resource for the Lifescience VO and assign its members group.

## What follows for a chain

The first two rules together shape the chain. A service can only exchange a token that names it in `aud`, and it can only ask for targets it has registered. So:

- Each client lists its next hops as resource indicators, and proTES's client lists every TES node.
- The `aud` rule needs a client ID, whereas RFC 8707 resources are absolute URIs. If LS Login refuses a bare client ID as an indicator, or a token with only a URL in `aud` can't be exchanged again, chains can't work today.
- Because entitlements are computed for the exchanging client, each exchanging client probably needs the group too, not only the node. Then the node's token shows what the gateway's facility releases.

## What public documents say

The operator's public documentation describes Perun and its proxy, not this flow. It has nothing on token exchange or resource indicators, as far as we could find, and nothing on the flows of the registration app. What does apply:

- [Entitlements](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/209813518/Entitlements): in OIDC, the values are in the `entitlements` or `eduperson_entitlement` claim of user info, and the scope `eduperson_entitlement` is required. A group entitlement is released for each group the user is in, if that group is assigned to a resource on the facility of the service.
- [Group entitlement](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/350879786/Group+entitlement): the value depends on group names, in the form `<NAMESPACE>:group:<GROUP>[:<SUBGROUP>*][#<AUTHORITY>]`, so it changes if a group is renamed or moved.
- [Resource capability](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/351272963/Resource+capability): the alternative that doesn't depend on group names. The Entitlements page recommends it for that reason.
- [Facility](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2252570626/Facility) and [Resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2261055/Resource): the entities behind the group release described above.
- [Understanding consent pages](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742536712/Understanding+consent+pages+when+logging+in): users can deselect attributes at login, and withholding entitlements can break access.
- [Terms of Use for Service Providers](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2137948170/Terms+of+Use+for+Service+Providers): apply to services that rely on LS AAI.

These pages cover several Perun instances, so they may not describe LS Login exactly.

## What we've seen

Public discovery documents, read on 2026-11-03, without credentials:

| | `/oidc/` | `/cas/oidc` |
|---|---|---|
| Token exchange, refresh token, client credentials, device code | listed | listed |
| Auth method `none` at the token endpoint | listed | not listed |
| Scope `eduperson_entitlement` | listed | listed |
| Scope `entitlements` | listed | not listed |

The testbed uses `https://login.aai.lifescience-ri.eu/oidc/` by default. [A page on re-registration](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2184773648/Service+Provider+Re-registration+for+use+LS+AAI+Eosc+compatible+AAI) names `https://login.aai.lifescience-ri.eu/cas/oidc` as the issuer for the LS AAI EOSC node, and says other production services still use the standard process. It doesn't say whether this is the new proxy stack, so that's an [open question](../open-questions.md). Being listed says nothing about what a given client may do.

A login token of Krini's, seen on 2026-10-20: `typ` was `at+jwt`, and `aud` held the client's ID.
