# Coverage

Which test covers which requirement, by way of which part of the design. The ADR column stays empty until after the event: see the EOC adoption plan.

| Requirement | Design section | Test | ADR |
|---|---|---|---|
| [R-U1](../background/requirements.md#user-requirements) One sign-in | [Authentication](../background/design.md#authentication) | T1 | |
| [R-U2](../background/requirements.md#user-requirements) Work continues | [Delegation across hops](../background/design.md#delegation-across-hops) | T4 | |
| [R-U3](../background/requirements.md#user-requirements) Everyone can sign in | [Authorization](../background/design.md#authorization) | T3 | |
| [R-U4](../background/requirements.md#user-requirements) Distinct refusals | [Authorization](../background/design.md#authorization) | T2, T3 | |
| [R-U5](../background/requirements.md#user-requirements) Portal without a server side | [Authentication](../background/design.md#authentication) | T1 | |
| [R-S1](../background/requirements.md#security-requirements) Credential good at one service | [Delegation across hops](../background/design.md#delegation-across-hops) | T1, T2 | |
| [R-S2](../background/requirements.md#security-requirements) No standing permission | [Trust model](../background/design.md#trust-model) | T1 | |
| [R-S3](../background/requirements.md#security-requirements) Limited long-lived permission | [Delegation across hops](../background/design.md#delegation-across-hops) | T4 | |
| [R-S4](../background/requirements.md#security-requirements) Each service verifies | [Trust model](../background/design.md#trust-model) | T2 | |
| [R-S5](../background/requirements.md#security-requirements) Node decides | [Authorization](../background/design.md#authorization) | T3 | |
| [R-S6](../background/requirements.md#security-requirements) Only set-up targets | [Delegation across hops](../background/design.md#delegation-across-hops) | T2 | |
| [R-S7](../background/requirements.md#security-requirements) No endless loops | [Attribution](../background/design.md#attribution) | T5 | |
| [R-S8](../background/requirements.md#security-requirements) Verifiable path | [Attribution](../background/design.md#attribution) | T5 | |
| [R-S9](../background/requirements.md#security-requirements) Ordinary software | [Authentication](../background/design.md#authentication) | T1 | |
| [R-S10](../background/requirements.md#security-requirements) Attribution of use | [Attribution](../background/design.md#attribution) | T5 | |
| [R-S11](../background/requirements.md#security-requirements) Following a request | [Attribution](../background/design.md#attribution) | T5 | |
| [R-P1](../background/requirements.md#privacy-requirements) Only what's needed | [Authorization](../background/design.md#authorization) | T3 | |
| [R-P2](../background/requirements.md#privacy-requirements) Stable reference | [Authentication](../background/design.md#authentication) | T4, by a second login | |
| [R-P3](../background/requirements.md#privacy-requirements) Nothing in logs | [Attribution](../background/design.md#attribution) | Each end-to-end run (Checking the setup) | |
| [R-P4](../background/requirements.md#privacy-requirements) What's released | [Authorization](../background/design.md#authorization) | T1, the consent page only | |
