# Prepare accounts and clients

Only needed for the [LS Login run](ls-login.md). Do it as early as possible: we don't know whether registrations need approval.

!!! note "Partly inferred"
    We haven't gone through the whole registration app, so fields may differ from what's described here. The client settings are inferred from the LS Login team's answers. If something doesn't match, record it for the [open questions](../open-questions.md).

## Two test accounts

- **Account A** inside the group, here `ECP_CLN`.
- **Account B** outside it.

Use test accounts only: sessions record their claims. If you need one, [Life Science Hostel accounts](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1741881406/Using+Life+Science+Hostel+account) don't depend on an institution. To see what an account belongs to, see [Checking your membership](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742635055/Checking+your+membership). How to add one to a group depends on the group's managers.

## Five clients

Register them at the [service registration app](https://services.aai.lifescience-ri.eu/), in this order, because each one lists the IDs of the next. Note each client ID and secret, and put them only in `lslogin.env` (below). The identifiers under `elixir-on.cloud` never need to resolve.

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

Both forms of each indicator are deliberate. The subject token's `aud` must hold the exchanging client's *ID*, whereas RFC 8707 resources are absolute URIs. **If the app refuses a bare client ID as an indicator, that's the first thing to raise.**

**Record:** what the app accepted, and anything that needed approval.

## Group release

Confirmed by the LS Login team, 2026-11-03: a **facility** is a client's representation in Perun IDM, and a **resource** represents the relationship between that facility and a VO.

**To get a group entitlement,** assign the group to a resource on the service's facility. Krini does this with `ECP_CLN:ADMIN`. A client that needs admin mapping only needs that one group, not the whole `ECP_CLN` structure.

**To let anyone with a valid LS Login account log in,** create a second resource for the Lifescience VO and assign its members group. Users outside `ECP_CLN` must be able to log in here, so that step 16 shows a 403 from the node, and not a lockout.

For the test:

1. On the facilities of `tx-test-client`, `tx-test-gateway` and `tx-test-node`, create a resource for the VO that holds the group, and assign the group.
2. Don't do this for `tx-test-orchestrator`: its missing release is what [step 14](ls-login.md#groups) compares against.
3. On the facilities of the clients that log in users, `tx-test-client` and `tx-test-public`, create the second resource for the Lifescience VO and assign its members group. Whether clients that only exchange need it, too, is an [open question](../open-questions.md#release).

The operator's pages on this: [Create (and remove) a resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/670400518/Create+and+remove+a+resource), [How to assign a group(s) to a resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/212828196/How+to+assign+a+group+s+to+a+resource), [Entitlements](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/209813518/Entitlements), [Perun roles and their rights](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1760100400/Perun+roles+and+their+rights).

!!! warning "Known problem: \"Assign groups\""
    It has been possible to open a facility and create a resource, but in "Assign groups" the Next button stays greyed out and no groups can be added, possibly because of a missing permission. [Which role is needed](../open-questions.md#role) is an open question. Until that's settled, ask the LS Login team to assign the groups, and otherwise go on without: the steps on groups then show what happens without a release.

**Record:** the exact entitlement in user info (step 14). Compare it with `TESTBED_REQUIRED_ENTITLEMENT`, whose example value we derived from a known entitlement of the same form.

## Environment

```sh
cp lslogin.env.example lslogin.env
```

Fill in `lslogin.env` with an editor. It's git-ignored and the image build doesn't see it: Compose passes it to the containers at runtime only. It holds client secrets, so keep it private, and delete it after the session. See [Settings](../reference/settings.md).
