# Glossary

| Term | Meaning |
|---|---|
| **`act`** | Claim of RFC 8693 that names who acts for the subject. Nests for each earlier actor |
| **Audience (`aud`)** | Claim that names who a token is meant for |
| **Client** | A registered application at the identity provider. Here, also each service, as it exchanges tokens |
| **Confidential client** | A client with a secret |
| **`can_act`, `may_act`** | Claims for restricting who may act. `may_act` is in RFC 8693; `can_act` is the name that the LS Login team used |
| **DRS, TES, TRS, WES** | The GA4GH Data Repository, Task Execution, Tool Registry and Workflow Execution Service APIs |
| **Entitlement** | A value that says what a user is or may do, such as group membership or a capability |
| **Exchange** | Getting a new token for a token you hold, per RFC 8693 |
| **Exchanging client** | The client that calls the exchange |
| **Facility** | A client's representation in Perun IDM |
| **Hop** | One call from one service to the next |
| **Identity provider** | The service that vouches for users and issues tokens |
| **Issuer (`iss`)** | Claim that names the identity provider of a token |
| **Node** | A TES service that runs tasks |
| **Public client** | A client without a secret, such as an app that runs in the browser |
| **Refresh token** | A long-lived token, for getting new access tokens without the user |
| **Resource** | In Perun: the relationship between a facility and a VO. In RFC 8707: the target of a token |
| **Resource indicator** | The name of a target that a token is requested for, per RFC 8707 |
| **Subject (`sub`)** | Claim that names the user. Stays the same across hops |
| **Subject token** | The token that goes into an exchange |
| **VO** | Virtual organisation: a group of users in Perun |
