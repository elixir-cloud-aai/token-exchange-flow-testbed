# Troubleshooting

## Starting things

**`e2e` says that service ports are taken.** It starts its own services. Run `docker compose down -v` first.

**The session says that it can't write the record file.** The container's user can't write to `results/`. See [Configuration](configuration.md#results).

**A client ID is missing.** With LS Login, the client IDs of `client`, `orchestrator`, `gateway` and `node` are required in `lslogin.env`.

**A secret doesn't work, or Compose warns about an unset variable.** Compose changes values with `$`, `#` or spaces: put them in single quotes. A warning may show part of the secret, so treat that one as exposed.

## Logging in

**A container can't open a browser.** Copy the URL that the session shows into a browser. It returns to `http://localhost:18994/callback`, which Compose forwards to the session.

**Port 18994 is in use, or a second session can't log in.** Only one session can log in at a time, as they share the callback port.

**The app refuses the localhost redirect URI.** Add `--flow device` to `login`, if the client has the device code flow registered. It has never been run against a real provider.

**Access is denied after login.** The operator's [Access denied after login](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1749647367/Access+denied+after+login) page lists general causes. For account B, this is a result: see T3.

**The entitlements are missing for a member of the group.** Check the group release under [Client registration](client-registration.md#group-release), and don't deselect entitlements at the [consent page](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742536712/Understanding+consent+pages+when+logging+in). For what an account belongs to, see [Checking your membership](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742635055/Checking+your+membership).

## Groups

**"Assign groups" has its Next button greyed out.** This is a known problem: see [Client registration](client-registration.md#group-release).

## Calling services

**A token is "not yet valid".** Check the machine's clock: as in FOCA, there's no leeway.

**A node answers 502 with `refused: userinfo`.** The node couldn't find out the entitlements: `entitlements_error` in its row says why. This isn't a decision about the user. Perhaps the exchanged token lacks a scope for user info: see `TESTBED_EXCHANGE_SCOPE`.

**A node answers 403 for a member of the group.** The release is probably missing on the exchanging client ([C4](../testbed/assumptions.md#constraints)).

**A service answers 502 with `refused: exchange`.** LS Login refused the next hop's exchange, or couldn't be reached. The row says which.

**The services' settings don't seem to apply.** They only read them at the start: see [Changing settings during a session](configuration.md#changing-settings-during-a-session).

For the meaning of all statuses, see [Commands](../about/commands.md#reasons-a-service-gives).
