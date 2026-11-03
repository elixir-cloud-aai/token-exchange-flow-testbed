# Coverage

Which test covers which requirement, by way of which part of the design. The ADR column stays empty until after the event: see the [EOC adoption plan](../outcomes/adoption.md).

| Requirement | Design section | Test | ADR |
|---|---|---|---|
| [R-U1](../background/requirements.md#user-requirements) One sign-in | [Authentication](../background/design.md#authentication) | [T1](../tests/t1-call-chain.md) | |
| [R-U2](../background/requirements.md#user-requirements) Work continues | [Delegation across hops](../background/design.md#delegation-across-hops) | [T4](../tests/t4-lifetime.md) | |
| [R-U3](../background/requirements.md#user-requirements) Everyone can sign in | [Authorization](../background/design.md#authorization) | [T3](../tests/t3-groups.md) | |
| [R-U4](../background/requirements.md#user-requirements) Distinct refusals | [Authorization](../background/design.md#authorization) | [T2](../tests/t2-refused.md), [T3](../tests/t3-groups.md) | |
| [R-U5](../background/requirements.md#user-requirements) Portal without a server side | [Authentication](../background/design.md#authentication) | [T1](../tests/t1-call-chain.md) | |
| [R-S1](../background/requirements.md#security-requirements) Credential good at one service | [Delegation across hops](../background/design.md#delegation-across-hops) | [T1](../tests/t1-call-chain.md), [T2](../tests/t2-refused.md) | |
| [R-S2](../background/requirements.md#security-requirements) No standing permission | [Trust model](../background/design.md#trust-model) | [T1](../tests/t1-call-chain.md) | |
| [R-S3](../background/requirements.md#security-requirements) Limited long-lived permission | [Delegation across hops](../background/design.md#delegation-across-hops) | [T4](../tests/t4-lifetime.md) | |
| [R-S4](../background/requirements.md#security-requirements) Each service verifies | [Trust model](../background/design.md#trust-model) | [T2](../tests/t2-refused.md) | |
| [R-S5](../background/requirements.md#security-requirements) Node decides | [Authorization](../background/design.md#authorization) | [T3](../tests/t3-groups.md) | |
| [R-S6](../background/requirements.md#security-requirements) Only set-up targets | [Delegation across hops](../background/design.md#delegation-across-hops) | [T2](../tests/t2-refused.md) | |
| [R-S7](../background/requirements.md#security-requirements) No endless loops | [Attribution](../background/design.md#attribution) | [T5](../tests/t5-attribution.md) | |
| [R-S8](../background/requirements.md#security-requirements) Verifiable path | [Attribution](../background/design.md#attribution) | [T5](../tests/t5-attribution.md) | |
| [R-S9](../background/requirements.md#security-requirements) Ordinary software | [Authentication](../background/design.md#authentication) | [T1](../tests/t1-call-chain.md) | |
| [R-S10](../background/requirements.md#security-requirements) Attribution of use | [Attribution](../background/design.md#attribution) | [T5](../tests/t5-attribution.md) | |
| [R-S11](../background/requirements.md#security-requirements) Following a request | [Attribution](../background/design.md#attribution) | [T5](../tests/t5-attribution.md) | |
| [R-P1](../background/requirements.md#privacy-requirements) Only what's needed | [Authorization](../background/design.md#authorization) | [T3](../tests/t3-groups.md) | |
| [R-P2](../background/requirements.md#privacy-requirements) Stable reference | [Authentication](../background/design.md#authentication) | [T4](../tests/t4-lifetime.md#expired-token), by a second login | |
| [R-P3](../background/requirements.md#privacy-requirements) Nothing in logs | [Attribution](../background/design.md#attribution) | Each end-to-end run ([Checking the setup](../setup/checking.md)) | |
| [R-P4](../background/requirements.md#privacy-requirements) What's released | [Authorization](../background/design.md#authorization) | [T1](../tests/t1-call-chain.md#login-user-to-client), the consent page only | |
