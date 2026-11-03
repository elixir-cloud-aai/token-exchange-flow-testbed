# References

## Standards

- [OAuth 2.0 (RFC 6749)](https://datatracker.ietf.org/doc/html/rfc6749): the framework, including refresh tokens.
- [PKCE (RFC 7636)](https://datatracker.ietf.org/doc/html/rfc7636): protects the authorization code flow.
- [Token revocation (RFC 7009)](https://datatracker.ietf.org/doc/html/rfc7009): how a refresh token gets withdrawn.
- [Token introspection (RFC 7662)](https://datatracker.ietf.org/doc/html/rfc7662): how a service asks about a token.
- [Token exchange (RFC 8693)](https://datatracker.ietf.org/doc/html/rfc8693): the per-hop exchange, and `act`.
- [Resource indicators (RFC 8707)](https://datatracker.ietf.org/doc/html/rfc8707): how the next hop is named.
- [Device authorization grant (RFC 8628)](https://datatracker.ietf.org/doc/html/rfc8628): login without a browser on the same machine.
- [JWT access tokens (RFC 9068)](https://datatracker.ietf.org/doc/html/rfc9068): the profile that services validate.
- [HTTP semantics (RFC 9110)](https://datatracker.ietf.org/doc/html/rfc9110): 401 and 403, and why `Max-Forwards` doesn't fit.
- [OAuth 2.0 security best current practice (RFC 9700)](https://datatracker.ietf.org/doc/html/rfc9700): applies to all clients here.
- [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html): login, and user info.
- [W3C Trace Context](https://www.w3.org/TR/trace-context/): `traceparent`.
- [AARC-G069](https://aarc-community.org/guidelines/aarc-g069/) and [AARC-G027](https://aarc-community.org/guidelines/aarc-g027/): the forms of group and capability entitlements.
- [Identity and authorization chaining across domains (draft)](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-chaining/): for more than one identity provider.
- [JWT profile for authorization grants (RFC 7523)](https://datatracker.ietf.org/doc/html/rfc7523): used by that draft.

## GA4GH specifications and Work Stream pages

- [GA4GH Federated Analysis Work Stream](https://www.ga4gh.org/work_stream/federated-analysis-work-stream-formerly-cloud-work-stream/): the group whose products this blueprint is for.
- [WES product page](https://www.ga4gh.org/product/workflow-execution-service-wes/), [specification](https://ga4gh.github.io/workflow-execution-service-schemas/), [repository](https://github.com/ga4gh/workflow-execution-service-schemas): the API of a workflow system.
- [TES product page](https://www.ga4gh.org/product/task-execution-service-tes/), [specification](https://ga4gh.github.io/task-execution-schemas/), [repository](https://github.com/ga4gh/task-execution-schemas): the API of gateways and nodes.
- [TRS product page](https://www.ga4gh.org/product/tool-registry-service-trs/), [repository](https://github.com/ga4gh/tool-registry-service-schemas): where tools come from.
- [DRS product page](https://www.ga4gh.org/product/data-repository-service-drs/), [repository](https://github.com/ga4gh/data-repository-service-schemas): where data comes from.
- [GA4GH data security](https://github.com/ga4gh/data-security): the security work of GA4GH, and its AAI profile.
- [2024 Cloud Work Stream roadmap](https://www.ga4gh.org/document/2024-cloud-work-stream-roadmap/): the Work Stream's plans under its earlier name.
- [Cloud APIs comic](https://www.ga4gh.org/document/cloud-apis-comic-v4-0/): an introduction to how the APIs fit together.

## Background

- [proTES #391](https://github.com/elixir-cloud-aai/proTES/issues/391): the proposal that the testbed checks.
- [proTES](https://github.com/elixir-cloud-aai/proTES): the gateway that `gateway` stands in for.
- [Krini](https://github.com/elixir-cloud-aai/krini): the portal that `client` stands in for.
- [FOCA](https://github.com/elixir-cloud-aai/foca): the framework whose token validation the services follow.
- [Cloud Registry](https://github.com/elixir-cloud-aai/cloud-registry): the registry that could one day list targets.
- [ELIXIR On-Cloud](https://elixir-on.cloud/): the setting of this work.
- [ELIXIR Cloud & AAI](https://elixir-cloud.dcc.sib.swiss/): the community behind those services.

## Tooling

- [`mock-oauth2-server`](https://github.com/navikt/mock-oauth2-server): the mock.
- [uv](https://docs.astral.sh/uv/): the optional development path.

## LS Login and Perun docs

These cover several Perun instances, so they may not describe LS Login exactly.

- [LS Login](https://lifescience-ri.eu/ls-login/): the identity provider under test.
- [Service registration app](https://services.aai.lifescience-ri.eu/): where clients are registered.
- [Entitlements](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/209813518/Entitlements), [Group entitlement](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/350879786/Group+entitlement), [Resource capability](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/351272963/Resource+capability): how entitlements get released, and their forms.
- [Facility](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2252570626/Facility), [Resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2261055/Resource): the entities behind the group release.
- [Create (and remove) a resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/670400518/Create+and+remove+a+resource), [How to assign a group(s) to a resource](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/212828196/How+to+assign+a+group+s+to+a+resource): how to set up the release.
- [Perun roles and their rights](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1760100400/Perun+roles+and+their+rights): for which role assigning groups needs.
- [Understanding consent pages](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742536712/Understanding+consent+pages+when+logging+in), [Access denied after login](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1749647367/Access+denied+after+login): for users who lose access.
- [Using Life Science Hostel account](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1741881406/Using+Life+Science+Hostel+account), [Checking your membership](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/1742635055/Checking+your+membership): for test accounts.
- [IdP OP Playground](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/214269953/IdP+OP+Playground): for looking at what an account releases.
- [Terms of Use for Service Providers](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2137948170/Terms+of+Use+for+Service+Providers): apply to services that rely on LS AAI.
- [Service Provider Re-registration](https://perunaai.atlassian.net/wiki/spaces/PERUN/pages/2184773648/Service+Provider+Re-registration+for+use+LS+AAI+Eosc+compatible+AAI): names the `/cas/oidc` issuer.

## Papers

- [The GA4GH Task Execution Application Programming Interface: Enabling Easy Multicloud Task Execution](https://ieeexplore.ieee.org/document/10564576) (2024): the TES API.
- [Sapporo: a workflow execution service that encourages the reuse of workflows in various languages in bioinformatics](https://doi.org/10.12688/f1000research.122924.1): a WES implementation.
- [Executing workflows in the cloud with WESkit](https://doi.org/10.37044/osf.io/2z6nu): another WES implementation.

## Further reading

- [The GA4GH Work Stream's page](https://www.ga4gh.org/work_stream/federated-analysis-work-stream-formerly-cloud-work-stream/): lists more papers and implementations in its "Products in Action" section.
