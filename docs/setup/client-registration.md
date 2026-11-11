# Client registration

Only needed for LS Login. Do it as early as possible: we don't know whether registrations need approval.

!!! note "Partly inferred"
    We haven't gone through the whole registration app, so fields may differ from what's described here. The client settings are inferred from the LS Login team's answers of 2026-11-03 ([A13](../testbed/assumptions.md#assumptions)). If something doesn't match, record it.

## Two test accounts

- **Account A** inside the group, here `ECP_CLN`.
- **Account B** outside it.

Use test accounts only: sessions record their claims. If you need one, [Life Science Hostel accounts](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1741881406/Using+Life+Science+Hostel+account) don't depend on an institution. To see what an account belongs to, see [Checking your membership](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742635055/Checking+your+membership). How to add one to a group depends on the group's managers.

## Five clients

Register them at the [service registration app](https://services.aai.lifescience-ri.eu/), in this order, because each one lists the IDs of the next. Note each client ID and secret, and put them only in `lslogin.env` (see [Configuration](configuration.md)). The identifiers under `elixir-on.cloud` never need to resolve.

| Name | Stands for | Type | Flows | Scopes |
|---|---|---|---|---|
| `tx-test-node` | TES node | confidential | client credentials (only so that it has a secret for introspection) | `openid`, `eduperson_entitlement` |
| `tx-test-gateway` | proTES | confidential | token exchange, client credentials | `openid`, `eduperson_entitlement`, `offline_access` |
| `tx-test-orchestrator` | Conquest | confidential | token exchange, refresh token, client credentials | `openid`, `eduperson_entitlement`, `offline_access` |
| `tx-test-client` | Krini with a backend | confidential | authorization code with PKCE, refresh token, token exchange, device code | `openid`, `eduperson_entitlement`, `offline_access` |
| `tx-test-public` | Krini without a backend | public, PKCE | as `tx-test-client` | as `tx-test-client` |

Redirect URI of the last two: `http://localhost:18994/callback`. The others have none.

Resource indicators:

| Client | Resource indicators |
|---|---|
| `tx-test-node` | none |
| `tx-test-gateway` | `<node client ID>`, `https://tx-test-node.elixir-on.cloud/` |
| `tx-test-orchestrator` | `<gateway client ID>`, `https://tx-test-gateway.elixir-on.cloud/` |
| `tx-test-client` | `<gateway client ID>`, `<orchestrator client ID>`, `https://tx-test-gateway.elixir-on.cloud/`, `https://tx-test-orchestrator.elixir-on.cloud/` |
| `tx-test-public` | `<gateway client ID>`, `https://tx-test-gateway.elixir-on.cloud/` |

Both forms of each indicator are deliberate. The subject token's `aud` must hold the exchanging client's *ID*, whereas RFC 8707 resources are absolute URIs. **If the app refuses a bare client ID as an indicator, that's the first thing to raise** ([C3](../testbed/assumptions.md#constraints)).

**Record:** what the app accepted, and anything that needed approval.

## Group release

From the LS Login team, 2026-11-03 ([A9, A10](../testbed/assumptions.md#assumptions)): a **facility** is a client's representation in Perun IDM, and a **resource** represents the relationship between that facility and a VO.

**To get a group entitlement,** create a resource on the facility representing the client and ask the VO admins to assign the group to it. Krini does this with `ECP_CLN:ADMIN`. A client that needs admin mapping only needs that one group, not the whole `ECP_CLN` structure.

**To let anyone with a valid LS Login account log in,** create a second resource for the Lifescience VO and ask the VO admins to assign its members group. Users outside `ECP_CLN` must be able to log in here, so that [T3](../tests/t3-groups.md#account-b-must-not-be-locked-out) shows a 403 from the node, and not a lockout.

For the test:

1. On the facilities of `tx-test-client`, `tx-test-gateway` and `tx-test-node`, the maintainer creates a resource for the VO that holds the group, then asks the VO admins to assign the group to each resource.
2. Don't do this for `tx-test-orchestrator`: its missing release is what [T3](../tests/t3-groups.md#release-per-client) compares against.
3. On the facilities of the clients that log in users, `tx-test-client` and `tx-test-public`, the maintainer creates the second resource for the Lifescience VO, then asks the VO admins to assign its members group to each resource. Whether clients that only exchange need it, too, is [a question for T3](../tests/t3-groups.md#questions-it-answers).

The operator's pages on this: [Create (and remove) a resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/670400518/Create+and+remove+a+resource), [How to assign a group(s) to a resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/212828196/How+to+assign+a+group+s+to+a+resource), [Entitlements](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/209813518/Entitlements), [Perun roles and their rights](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1760100400/Perun+roles+and+their+rights).

### Who can assign groups

Being able to open a facility and create a resource does not establish permission to assign a VO's groups. A greyed-out Next button under "Assign groups" may indicate missing permissions.

The LS AAI team confirmed that **TrustedFacilityAdmin within the relevant VO** enables a maintainer to assign that VO's groups to resources. The VO admins have chosen not to grant this role for this setup and require assignments to be delegated to them.

The VO admins perform group assignments to the resource. The client maintainer creates the resources, then sends the VO admins links to the resource and to groups he wants to assign to the resource.

### Assigning groups and verifying release

1. Create a resource for the relevant VO on the facility representing the client.
2. Send the VO admins links to the resource and the groups to assign. Ask them to complete the assignment and confirm it. Verify that the groups appear among the resource's assigned groups.
3. Log in with a test account belonging to the assigned group, and use the session's `userinfo <token-name>` command to inspect the released entitlements. Compare the exact value with `TESTBED_REQUIRED_ENTITLEMENT` in `lslogin.env`; do not assume the example value matches.
4. Repeat the release setup for each service that needs it. For this testbed, follow the facility list above, preserving the deliberate omission for the orchestrator in T3.
5. Use T3 to verify that a user outside the required group can still log in but receives 403 from the node.

**Record:** the exact entitlement in user info ([T3](../tests/t3-groups.md)). Compare it with `TESTBED_REQUIRED_ENTITLEMENT`, whose example value we derived from a known entitlement of the same form.
