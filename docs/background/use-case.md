# Use case

Researchers want to run analyses across several institutions. The data often can't leave the place where it is held, so the analysis goes to the data. This page describes who does that, and what they want from it. It's the starting point for how people and services prove who they are, and what they may do, in federated architectures based on the Workflow Execution Service (WES), the Task Execution Service (TES) and the other products of the [GA4GH Federated Analysis Work Stream](https://www.ga4gh.org/work_stream/federated-analysis-work-stream-formerly-cloud-work-stream/) (formerly the Cloud Work Stream).

## Who acts

| Actor | Wants | Runs |
|---|---|---|
| **Researcher** | To run an analysis wherever the data is, without dealing with each site | Nothing: uses a portal |
| **Portal** | To offer researchers one place to start and follow work | A website, with or without its own server side |
| **Workflow system** | To carry out a multi-step analysis on behalf of a researcher, over hours or days | A WES service |
| **Task gateway** | To send each task to a suitable node, on behalf of a researcher | A TES service that forwards to other TES services |
| **Compute node** | To run tasks, for people it decides to accept, on infrastructure it answers for | A TES service |
| **Node operator** | To stay in control of their own infrastructure, and to report who used it | One compute node |
| **Identity provider** | To vouch for researchers across institutions | Sign-in, and a record of group memberships |
| **Data or tool service** | To hand out data or tools, to those allowed to have them | A Data Repository Service (DRS) or Tool Registry Service (TRS) |

Several organisations run these services. None of them is in charge of the others, and some may not know each other directly.

## What they want to do

Each scenario has a number, which the [requirements](requirements.md) refer to.

**UC1: run a single task.** A researcher signs in at a portal and starts a task. The portal hands it to the task gateway, which picks a node. The node runs it and reports back. The researcher signed in once, and never dealt with the gateway or the node.

**UC2: run a workflow.** The same, with a workflow system between the portal and the gateway. It turns one request into many tasks, on one or more nodes.

**UC3: run a workflow for days.** A workflow goes on long after the researcher has closed the browser. It still starts new tasks, on behalf of that researcher, and is still bound by what that researcher may do.

**UC4: decide who may use a node.** A node operator accepts members of a particular group, for instance a project with an agreement for that site. Another node accepts other people. Neither decision is made for them by a service further up the chain.

**UC5: find a way in.** A researcher who isn't in such a group can still sign in, look around, and find out how to get access. Being refused a node is something a portal can explain, and not an error.

**UC6: account for use.** A node operator reports how much was used, by whom, and through which portal or workflow system. An auditor later asks how a particular task reached a node.

**UC7: follow a request.** Something failed. Operators of different services need to find the same request in each of their logs.

**UC8: join the federation.** A new node joins, or an existing service is run by someone new. They set this up from documentation, using ordinary software, without changes in anyone else's code.

**UC9: lose as little as possible.** One service in the chain is compromised, or misconfigured. The damage stays limited to that service, and doesn't spread to every node the same researcher can reach. Researchers also expect that services only learn about them what they need to.

## Why this deserves a blueprint

Each of these services has its own API standard, and those standards leave open how a researcher's identity travels from one service to the next. Without a shared answer, each deployment makes one up: services then store credentials they shouldn't hold, or a node has to trust whatever the service before it claims. The [design](design.md) describes a shared answer for the end state, and the [testbed](../testbed/index.md) shows how much of it works today.
