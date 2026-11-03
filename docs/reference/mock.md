# What the mock can't show

The mock is [`mock-oauth2-server`](https://github.com/navikt/mock-oauth2-server) 6.0.7. It supports the token exchange grant, but it's not LS Login. All of this was seen in probes, and most of it is checked again in each end-to-end run, in the section `MOCK GAP`.

It **accepts:** a subject token without the exchanging client in `aud`, for an unregistered target, expired, or with a broken signature, and any client secret. A refresh token can be redeemed by any client.

It **ignores** `audience` and `resource`, unless a mapping says otherwise. `aud` and `client_id` after an exchange come from **our** `mock/oidc.json`, so they're no evidence. Only one target ends up in `aud`.

It **refuses** exchange without a client secret (`invalid_request`), so public clients can't be shown.

It **doesn't have:**

- `act` (`actor_token` is ignored);
- refresh tokens from exchanges (`requested_token_type` is ignored), rotation, or idle and absolute limits;
- entitlements per client: user info just returns the token's claims, whereas LS Login only has them in user info;
- a device flow;
- a separate `typ` for ID tokens.

## What the testbed does about it

`src/testbed/rules.py` makes a local run behave like LS Login as its team described it: the exchanging client must be in the subject's `aud`, targets must be registered, and the subject must be valid. **These checks run in the testbed, on the mock only**, with `refused_by: testbed rule (mock only; not LS Login)`, and with error codes of our choosing. Whether the subject's signature and expiry are checked is our assumption of what LS Login does. `--no-rules` turns them off, to show what the mock itself lets through.

## Untested until real clients exist

**Everything against LS Login: no step has ever run there.** Its discovery document was read, which is public and needs no credentials. A local run shows that our code works and handles refusals, not that LS Login behaves as expected.

Beyond that:

- **Never run at all, on the mock or elsewhere:** the real browser login (the mock run fills in its login form), `--flow device` (unit tests with a fake only), the public client's exchange, a refresh token from an exchange, a real rotation, entitlements that differ by client.
- **Ran on the mock, but the results are no evidence:** `client_id`, `aud`, lifetimes and refresh tokens. In the mock, these follow our own `mock/oidc.json`.
- **Refusals** of a subject without our client in `aud`, unregistered targets, tampered and expired subjects come from the testbed's own rules on the mock, with made-up error codes.
- **The registration instructions:** we haven't gone through the whole app, so its fields may differ.
- **Platforms:** the Docker path has only run on Linux. macOS and WSL are expected to work, as nothing in it is specific to Linux, but haven't been tried. That includes a browser on the host returning to the published callback port.
