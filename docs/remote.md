# Optional: remote machines

You don't need this: the testbed is meant to run on your own machine. **Nothing on this page has been tested.**

If Docker runs on another machine, the login callback needs a way back to it. There are two ways, both only for the [run against LS Login](tutorial/ls-login.md). The mock needs neither, as it doesn't use a browser.

## SSH tunnel

From the machine with the browser, forward the callback port, then run everything as usual on the remote machine:

```sh
ssh -L 18994:localhost:18994 <remote machine>
```

The redirect URI stays `http://localhost:18994/callback`, which the browser reaches through the tunnel. No port is opened to the public.

## Device flow

This needs no redirect, if the client has the device code flow registered. Discovery at `/oidc/` lists it, but we've never run it against a real provider; there are only unit tests with a fake.

```text
login user --as client --flow device
```

The session shows a URL and a code to enter in any browser.
