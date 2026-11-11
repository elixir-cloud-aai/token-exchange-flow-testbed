# T3 Groups and entitlements

## Description

Which entitlements does each client see, does the node's policy work through the chain, and can people outside a group still log in? Uses the tokens of [T1](t1-call-chain.md) and [T2](t2-refused.md), in the same session. Needs the [group release](../setup/client-registration.md#group-release) set up, and otherwise shows what happens without it.

**Runs against:** LS Login. The mock has no entitlements per client, so there it only shows that the commands work. It does show a node's 403, under [Checking the setup](../setup/checking.md#a-user-outside-the-group).

From the LS Login team, 2026-11-03: entitlements are computed for the client calling the exchange ([A5](../testbed/assumptions.md#assumptions)), and they come from assigning a group to a resource on the service's facility ([A9](../testbed/assumptions.md#assumptions)).

## Expectations

1. Entitlements follow the client that a token was issued to, not its audience ([A5](../testbed/assumptions.md#assumptions)). So `to-orch`, issued to the client, shows the group, and `gw-o`, issued to the orchestrator, which has no release, doesn't.
2. For the same reason, the node's token, issued to the gateway, probably shows the *gateway's* release, not the node's ([C4](../testbed/assumptions.md#constraints)).
3. Account A through the chain: 200, and `policy: allowed` at the node.
4. Account B can log in and exchange, the gateway passes the request on, and the node answers **403** with `refused: entitlement`, not 401, so that a portal can offer a way to get access.

## Steps

### Release per client

```text
tb> userinfo user
tb> userinfo to-gw
tb> exchange to-node --as gateway --from to-gw --audience @node
tb> userinfo to-node
tb> userinfo to-orch
tb> exchange gw-o --as orchestrator --from to-orch --audience @gateway
tb> userinfo gw-o
tb> introspect to-node --as node
tb> introspect to-node --as gateway
tb> exchange to-node-s --as gateway --from to-gw --audience @node --scope "openid eduperson_entitlement"
tb> userinfo to-node-s
```

### Account A through the chain

```text
tb> call gateway --token to-gw
```

A 403 here, for a member of the group, means that the release is missing on the gateway. A 502 with `refused: userinfo` means that user info gave no answer. If the previous step needed the `scope`, set `TESTBED_EXCHANGE_SCOPE` and [restart the services](../setup/configuration.md#changing-settings-during-a-session).

### Account B must not be locked out

Paste the URL into a private window, so that the browser's session for A isn't used.

```text
tb> login b --as client --no-browser
tb> exchange b-gw --as client --from b --audience @gateway
tb> userinfo b
tb> call gateway --token b-gw
```

**If LS Login refuses the login or the exchange, B is locked out: raise it before going on.**

## Questions it answers

### Which group release does a node see, and per which client?

Group release as such is confirmed ([A9](../testbed/assumptions.md#assumptions)), but what reaches a node isn't known.

- **The exchanging client's, as proTES #391 assumes:** each gateway's facility needs the group of everything downstream. That goes into #391's registration notes and the operator docs.
- **If `introspect --as node` gives the node's own view, and we want that:** FOCA needs introspection, as it only has user info today.
- **Does the exchange need `scope` for this?** Then FOCA's exchange gets a scope setting per target.

### How can a group be released without locking out users outside it?

From the LS Login team, 2026-11-03: create a second resource for the Lifescience VO and assign its members group ([A10](../testbed/assumptions.md#assumptions)). What's still open:

- **Is the second resource needed on every client in the chain,** or only on those that log in users? In other words: can a gateway exchange for a user who isn't in any group assigned to its facility?
    - **Only those that log in users:** registering a gateway stays simple.
    - **Every client:** each one needs that resource, which goes into the registration notes.
- **Are users outside a group ever stopped at LS Login in the first place, and by what setting?**
    - **No:** node policy decides, with a 403, and Krini shows "request compute access".
    - **Yes:** find out which setting caused it before registering Krini.
- **Does the members group add an entitlement that nodes see for all users?** Node policies must not match it by accident.

### Which role is needed to assign groups to a resource?

This project's maintainer could open a facility and create a resource, but in "Assign groups" the Next button stays greyed out and no groups can be added, possibly because of a missing permission (seen by 2026-11-03).

The LS AAI team confirmed that **TrustedFacilityAdmin within the relevant VO** enables this assignment. The VO admins have chosen not to grant that role for this setup; maintainers create resources and ask the VO admins to assign groups, as described in [Client registration](../setup/client-registration.md#who-can-assign-groups).

**What it changes:** operators should plan for VO-admin involvement when setting up group release, rather than trying to obtain self-service assignment permissions.

### Group entitlements or resource capabilities?

The operator's Entitlements page recommends resource capabilities, as group entitlements change when a group is renamed or moved (see [What public documents say](../testbed/assumptions.md#what-public-documents-say)). Are they available on LS Login, for a client like these?

- **Yes:** node policies can match a capability rather than a group's name. `TESTBED_REQUIRED_ENTITLEMENT` takes either, so the testbed can try it.
- **No:** nodes match group entitlements and break if groups are renamed, which the operator docs should say.

### What is the exact entitlement value?

We derived the example from a known entitlement of the same form ([A12](../testbed/assumptions.md#assumptions)). If it differs, nodes get another value in their settings, and nothing else changes.

## What to record

| Step | Record | Result |
|---|---|---|
| Release per client | The entitlements for each line. Does `introspect --as node` differ? Does the exchange need the `scope`? | |
| Exact value | The entitlement in user info, compared with `TESTBED_REQUIRED_ENTITLEMENT` | |
| Account A | Status, `policy` at the node | |
| Account B | Login, exchange, status and `refused` at the node | |
| Group release | Which role it took, and who granted it | |
