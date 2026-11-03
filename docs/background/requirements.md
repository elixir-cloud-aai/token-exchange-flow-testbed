# Requirements

What the [use case](use-case.md) needs, in three groups, without saying how to achieve it. The [design](design.md) says how, and [Coverage](../testbed/coverage.md) maps each requirement to the design and to the tests.

## User requirements

| ID | Requirement | Why | From |
|---|---|---|---|
| R-U1 | A researcher signs in once, and that covers all services a request passes through | Researchers don't know which services are involved, and shouldn't need to | UC1, UC2 |
| R-U2 | Work continues while the researcher is away, for as long as it runs | Workflows outlast any browser session | UC3 |
| R-U3 | Everyone with a valid account can sign in, whatever they may later be allowed to use | Otherwise people can't find out how to get access | UC5 |
| R-U4 | A service can tell "you aren't signed in properly" from "you have no access here" | A portal can only offer a way in for the second one | UC5 |
| R-U5 | A portal can take part whether or not it has a server side of its own | Not every portal has or wants one | UC1 |

## Security requirements

| ID | Requirement | Why | From |
|---|---|---|---|
| R-S1 | A credential stolen at one service is of no use at any other | Limits a compromise to that service | UC9 |
| R-S2 | Services in the middle hold no standing permission to act for researchers | A stored permission is a target, and acts without a request behind it | UC1, UC9 |
| R-S3 | Permission that must outlast a request (R-U2) is limited to the one service it's needed for, in time, and can be withdrawn | Long-running work mustn't turn into standing permission | UC3, UC9 |
| R-S4 | Each service verifies each request for itself, without relying on what the previous service says | Services are run by different organisations | UC2, UC9 |
| R-S5 | Each node decides for itself whom it accepts, whatever services before it decided | Node operators answer for their infrastructure | UC4 |
| R-S6 | A service can only pass requests on to services it was set up for | A compromised service can't reach arbitrary others | UC9 |
| R-S7 | Requests can't circulate between services forever | A misconfiguration shouldn't take down a federation | UC2, UC7 |
| R-S8 | A node can verify which services a request passed through | Provenance can't rest on what those services say | UC6 |
| R-S9 | Taking part needs ordinary, standards-based software, without changes specific to one deployment | Some services are outside the federation's control | UC8 |
| R-S10 | Use can be attributed to the researcher, and to the portal or workflow system involved | Operators report on it | UC6 |
| R-S11 | One request can be followed across all services it passed through | Failures cross organisations | UC7 |

## Privacy requirements

| ID | Requirement | Why | From |
|---|---|---|---|
| R-P1 | A service learns only what it needs about a researcher | Data minimisation | UC9 |
| R-P2 | A node can recognise the same researcher over time, without needing their name or email address | Accounting and audits need a stable reference, not personal details | UC6 |
| R-P3 | Credentials and personal details don't end up in logs or reports | Logs are kept longer and read more widely | UC7, UC9 |
| R-P4 | Researchers can see what is released about them, to whom | They have to be able to trust the federation with it | UC9 |
