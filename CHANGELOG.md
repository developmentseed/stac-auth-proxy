# Changelog

## [1.0.0](https://github.com/developmentseed/stac-auth-proxy/compare/v1.0.2...v1.0.0) (2026-03-09)


### ⚠ BREAKING CHANGES

* **auth:** Authentication failures now return 401 instead of 403

### Features

* add `configure_app` for applying middleware to existing FastAPI applications ([#85](https://github.com/developmentseed/stac-auth-proxy/issues/85)) ([3c5cf69](https://github.com/developmentseed/stac-auth-proxy/commit/3c5cf694c26520fd141faf84c23fe621413e244e))
* add aws lambda handler ([#81](https://github.com/developmentseed/stac-auth-proxy/issues/81)) ([214de02](https://github.com/developmentseed/stac-auth-proxy/commit/214de02301b909347e847c66c7e12b88ba74fdea))
* add configurable audiences ([#83](https://github.com/developmentseed/stac-auth-proxy/issues/83)) ([58d05ea](https://github.com/developmentseed/stac-auth-proxy/commit/58d05ea665c48cc86e4774e2e7337b7ad277ab2f))
* add debug endpoint ([cd64125](https://github.com/developmentseed/stac-auth-proxy/commit/cd641258ea5be5db97000b496194c5fe2ed04f6f))
* add healthz endpoints ([4b1f4d1](https://github.com/developmentseed/stac-auth-proxy/commit/4b1f4d1dfeea2a2c19cbc0a8ba7809fe453b77af)), closes [#27](https://github.com/developmentseed/stac-auth-proxy/issues/27)
* Add helm chart auth options. ([#118](https://github.com/developmentseed/stac-auth-proxy/issues/118)) ([cfae34b](https://github.com/developmentseed/stac-auth-proxy/commit/cfae34b5a3a50596dc2ba13bd51cc96144e78d80))
* Add helm README.md and unit tests ([#117](https://github.com/developmentseed/stac-auth-proxy/issues/117)) ([74a1bc8](https://github.com/developmentseed/stac-auth-proxy/commit/74a1bc8e361cbc85bb48dff4fc4019b2ad8d196d))
* Add mock OIDC server ([#40](https://github.com/developmentseed/stac-auth-proxy/issues/40)) ([0e5a23b](https://github.com/developmentseed/stac-auth-proxy/commit/0e5a23b4a1ba1ec1c1dba59b3921c1f08747830c))
* add opa integration ([#47](https://github.com/developmentseed/stac-auth-proxy/issues/47)) ([6f9216b](https://github.com/developmentseed/stac-auth-proxy/commit/6f9216b9c114678710e3149674969364d9da8c4f)), closes [#24](https://github.com/developmentseed/stac-auth-proxy/issues/24)
* add openapi endpoint as default public endpoint ([374b75a](https://github.com/developmentseed/stac-auth-proxy/commit/374b75aaba697d61714d8499d11cc73cdd446f74))
* Add timing middleware ([8d006ef](https://github.com/developmentseed/stac-auth-proxy/commit/8d006efe613cc0e196d9a3001c78ae183d95f77f))
* add x-upstream-time header ([3abf298](https://github.com/developmentseed/stac-auth-proxy/commit/3abf298c7837b4b996970d108ca5d6319ce09f6c))
* allow customize filter paths ([#58](https://github.com/developmentseed/stac-auth-proxy/issues/58)) ([0530ea0](https://github.com/developmentseed/stac-auth-proxy/commit/0530ea02de05eea544e3cad017fd480674f6425b))
* augment openapi spec ([ac981ce](https://github.com/developmentseed/stac-auth-proxy/commit/ac981cea4b5022abdbfb17f8567cae504bd568a3))
* Buildout CQL2 filter tooling for reading Items ([#17](https://github.com/developmentseed/stac-auth-proxy/issues/17)) + Refactor codebase into middleware ([#20](https://github.com/developmentseed/stac-auth-proxy/issues/20)) ([327b9cf](https://github.com/developmentseed/stac-auth-proxy/commit/327b9cfc81ac28dbe4cb9d84c24c0d8174981f36))
* buildout filter for item read ([#45](https://github.com/developmentseed/stac-auth-proxy/issues/45)) ([3b9977e](https://github.com/developmentseed/stac-auth-proxy/commit/3b9977efc4920fb40760519fcf22f97c316c444a))
* check upstream API health at startup ([#32](https://github.com/developmentseed/stac-auth-proxy/issues/32)) ([12f2973](https://github.com/developmentseed/stac-auth-proxy/commit/12f29734c7ee6ac46a42b90fb976f090970e10bd))
* **config:** add root path GET requests to default public endpoints ([#62](https://github.com/developmentseed/stac-auth-proxy/issues/62)) ([59c6a97](https://github.com/developmentseed/stac-auth-proxy/commit/59c6a9740cf5cbcf43aaf5b556c37714db40ada7))
* **config:** expand default endpoints ([#79](https://github.com/developmentseed/stac-auth-proxy/issues/79)) ([6718991](https://github.com/developmentseed/stac-auth-proxy/commit/67189917c2b38620dc92fb7836d25b68901f59ae))
* configurable root_path ([#50](https://github.com/developmentseed/stac-auth-proxy/issues/50)) ([34ba6b7](https://github.com/developmentseed/stac-auth-proxy/commit/34ba6b7c7e88eb19e6ffde6bb62fe22f62a21c5b))
* enable collections filtering ([#52](https://github.com/developmentseed/stac-auth-proxy/issues/52)) ([df9330e](https://github.com/developmentseed/stac-auth-proxy/commit/df9330ed28478654acb73c51ec95d4b6ef77c6e0))
* enable hosting custom Swagger UI ([#53](https://github.com/developmentseed/stac-auth-proxy/issues/53)) ([ca913a0](https://github.com/developmentseed/stac-auth-proxy/commit/ca913a068d9871ed8819b60de97205847a937b2b))
* handle CORS by default ([#133](https://github.com/developmentseed/stac-auth-proxy/issues/133)) ([4c49b95](https://github.com/developmentseed/stac-auth-proxy/commit/4c49b955d73276fe5d995f1cd742e6f202834f7a))
* **helm:** add extraContainers in helm-chart ([#132](https://github.com/developmentseed/stac-auth-proxy/issues/132)) ([e0acecb](https://github.com/developmentseed/stac-auth-proxy/commit/e0acecb56cf4d74e3226d50bd7e3e306ac9d6609))
* **helm:** Add support for initContainers. ([#104](https://github.com/developmentseed/stac-auth-proxy/issues/104)) ([a7ca408](https://github.com/developmentseed/stac-auth-proxy/commit/a7ca408b73379cd75980f005a5e2fac2d815b700))
* increase default healthcheck retries ([d19b8aa](https://github.com/developmentseed/stac-auth-proxy/commit/d19b8aa8b491beb1464427f32ef0c47a7439300e))
* integrate with Authentication Extension ([#41](https://github.com/developmentseed/stac-auth-proxy/issues/41)) ([bd87d38](https://github.com/developmentseed/stac-auth-proxy/commit/bd87d385594cc5eac8660a1848adc8c9c479e291)), closes [#35](https://github.com/developmentseed/stac-auth-proxy/issues/35)
* make use of Server-Timing header ([c894026](https://github.com/developmentseed/stac-auth-proxy/commit/c8940260cbe69bdc7868f16f5c8a76f9ae29b9d6)), closes [#69](https://github.com/developmentseed/stac-auth-proxy/issues/69)
* proxy headers, override host ([#49](https://github.com/developmentseed/stac-auth-proxy/issues/49)) ([2961a48](https://github.com/developmentseed/stac-auth-proxy/commit/2961a48eb2e5dc0681a6d659eb9b2ec8ce834c78)), closes [#34](https://github.com/developmentseed/stac-auth-proxy/issues/34)
* **proxy:** Add proxy context headers to upstream requests ([3903e89](https://github.com/developmentseed/stac-auth-proxy/commit/3903e891afae2b7c29e951843a7a705ef49d3256))
* relax ServerHealthCheck defaults ([ad29ee7](https://github.com/developmentseed/stac-auth-proxy/commit/ad29ee79694684b7c299366bdb2ad3c78aa5ab2b))
* remove applied filters on response links ([#67](https://github.com/developmentseed/stac-auth-proxy/issues/67)) ([2b2b224](https://github.com/developmentseed/stac-auth-proxy/commit/2b2b22459c0e577b5a1d5d1e04c7de406d074a99)), closes [#64](https://github.com/developmentseed/stac-auth-proxy/issues/64)
* reorg config for better customization ([4fcf7d1](https://github.com/developmentseed/stac-auth-proxy/commit/4fcf7d163e636e3a58523d51d5713ff8122f1207))
* skip json middleware based on response data type ([#103](https://github.com/developmentseed/stac-auth-proxy/issues/103)) ([16b05c3](https://github.com/developmentseed/stac-auth-proxy/commit/16b05c3c201e04b2027c6a7ef632477febdbecfb))
* support brottli compression ([0c5cf4e](https://github.com/developmentseed/stac-auth-proxy/commit/0c5cf4ed7ce67876119fd6df703e7b0bc79c780e))
* Support CEL access policies ([#13](https://github.com/developmentseed/stac-auth-proxy/issues/13)) ([9373dee](https://github.com/developmentseed/stac-auth-proxy/commit/9373dee6ecabecb9c460974e809d6f3e5f7c173c))
* support custom OpenAPI auth scheme ([#51](https://github.com/developmentseed/stac-auth-proxy/issues/51)) ([de6a946](https://github.com/developmentseed/stac-auth-proxy/commit/de6a9463e3195ea2dfdb687d91f06145cf820dac))
* support customizing port when running as a module ([9a18c49](https://github.com/developmentseed/stac-auth-proxy/commit/9a18c49f74695dfdde516f6554a6bb6f6244937c))
* support scopes in private endpoints ([#33](https://github.com/developmentseed/stac-auth-proxy/issues/33)) ([b44d28a](https://github.com/developmentseed/stac-auth-proxy/commit/b44d28a1d27fe4c8c7c5bb293c9468a924beb151)), closes [#28](https://github.com/developmentseed/stac-auth-proxy/issues/28)
* support specifying cls & args & kwargs separately ([b3dd73e](https://github.com/developmentseed/stac-auth-proxy/commit/b3dd73e488dc395ef8129102f8cbfc47f52a80d0))
* tooling to disable auth extension & compression ([046c731](https://github.com/developmentseed/stac-auth-proxy/commit/046c731f98f8fe30927172a62b1eeb3c365a4875))
* update authentication extension integratino to use discovery URL ([1ce8ed5](https://github.com/developmentseed/stac-auth-proxy/commit/1ce8ed58a4353cc8ca78a9744f4a22f2363da76a))
* use HTTP2 ([45b4e38](https://github.com/developmentseed/stac-auth-proxy/commit/45b4e389a1e248e29b8c53f960e849b754a79d0f)), closes [#38](https://github.com/developmentseed/stac-auth-proxy/issues/38)
* Use PydanticSettings for config management ([4895bca](https://github.com/developmentseed/stac-auth-proxy/commit/4895bcac4b0d6755ef22ffa36ab29e3df79ccaa9))
* validate auth tokens ([b5ecada](https://github.com/developmentseed/stac-auth-proxy/commit/b5ecadaefa6ae1b009702184ba565b15df1f6a47))
* validate transaction requests with CQL2 filters ([#131](https://github.com/developmentseed/stac-auth-proxy/issues/131)) ([254bd82](https://github.com/developmentseed/stac-auth-proxy/commit/254bd82576f09b0dab63f6c75ee8725ab1962879)), closes [#21](https://github.com/developmentseed/stac-auth-proxy/issues/21) [#22](https://github.com/developmentseed/stac-auth-proxy/issues/22)


### Bug Fixes

* **auth-extension:** consider link method when adding auth:refs ([158f507](https://github.com/developmentseed/stac-auth-proxy/commit/158f50756ffb44086eb872b427c46e8101518c50))
* **auth:** correct HTTP status codes for authentication and authorization failures ([#108](https://github.com/developmentseed/stac-auth-proxy/issues/108)) ([17227e4](https://github.com/developmentseed/stac-auth-proxy/commit/17227e447c188d73426ed1771cc45d95b141a4e9))
* avoid flaky assertion ([1b8fa28](https://github.com/developmentseed/stac-auth-proxy/commit/1b8fa282bfe71cc794b821e85459c4de56345749))
* check private endpoint scopes when default_public=False ([6dfa54d](https://github.com/developmentseed/stac-auth-proxy/commit/6dfa54d13d23addf7371493c369a1fc7902d168c))
* correct required conformance classes for filters ([9d4d211](https://github.com/developmentseed/stac-auth-proxy/commit/9d4d2110bd7b1d5ed3e09183caeb64225d59eb51))
* correctly catch JSON parse errors ([9d8599f](https://github.com/developmentseed/stac-auth-proxy/commit/9d8599f6bbecb23e525a2d2ebafbe4acef258576))
* Disable openAPI tooling ([6595df0](https://github.com/developmentseed/stac-auth-proxy/commit/6595df058ff3ec22e65a5d620d99d7a7ad83acf5))
* disable server reload by default ([c109801](https://github.com/developmentseed/stac-auth-proxy/commit/c1098010e02b301041f05ad5401ab6a514366c85)), closes [#142](https://github.com/developmentseed/stac-auth-proxy/issues/142)
* don't set host header ([0c89e09](https://github.com/developmentseed/stac-auth-proxy/commit/0c89e09ce7cb3e094d63f06d6ceebded6a6dfb0b))
* Enhance type safety in middleware and utility functions ([#122](https://github.com/developmentseed/stac-auth-proxy/issues/122)) ([52cdd0e](https://github.com/developmentseed/stac-auth-proxy/commit/52cdd0eaf8eb0c98cdb4c18d54c2d23979e5d72a))
* ensure openapi spec demonstrates auth when cql2 filters apply ([#135](https://github.com/developmentseed/stac-auth-proxy/issues/135)) ([7310cee](https://github.com/developmentseed/stac-auth-proxy/commit/7310ceef462afadbc0a361211011549505aace94))
* ensure OPTIONS requests are sent upstream without auth check ([#76](https://github.com/developmentseed/stac-auth-proxy/issues/76)) ([855183a](https://github.com/developmentseed/stac-auth-proxy/commit/855183a7ccf0331d772cb91411b8dca905b05181)), closes [#75](https://github.com/developmentseed/stac-auth-proxy/issues/75)
* Ensure x-forwarded-port header is used in Forwarded header ([#115](https://github.com/developmentseed/stac-auth-proxy/issues/115)) ([78525b1](https://github.com/developmentseed/stac-auth-proxy/commit/78525b131b259748e00df1e38c54fb152414da4d))
* fix status check for 2xx responses ([#59](https://github.com/developmentseed/stac-auth-proxy/issues/59)) ([5b03cb3](https://github.com/developmentseed/stac-auth-proxy/commit/5b03cb35e6fb7a10cd51e0fcd1ab86d4bb4292cc))
* handle compressed OpenAPI responses & ensure paths correctly marked private ([#29](https://github.com/developmentseed/stac-auth-proxy/issues/29)) ([2fe0852](https://github.com/developmentseed/stac-auth-proxy/commit/2fe0852c18cbf72c520f1c35ed0415242b85f7ca))
* handle deeply nested security dependencies ([#14](https://github.com/developmentseed/stac-auth-proxy/issues/14)) ([5ff51ca](https://github.com/developmentseed/stac-auth-proxy/commit/5ff51caf5bde8c2362435aba4c7483d7897786f4))
* Helm chart and app version mismatch. ([#120](https://github.com/developmentseed/stac-auth-proxy/issues/120)) ([7998675](https://github.com/developmentseed/stac-auth-proxy/commit/79986751390ae243dee565b2b273d8d67aab5ba5))
* improve link processing ([#95](https://github.com/developmentseed/stac-auth-proxy/issues/95)) ([e52b5a9](https://github.com/developmentseed/stac-auth-proxy/commit/e52b5a972539232da4fc0a74b3a8abad7579f41e))
* **jinja2:** use sandboxed environment ([504074f](https://github.com/developmentseed/stac-auth-proxy/commit/504074f9bf5cb17129ad38261d5bb499daced8b4))
* **lifespan:** allow endpoints that don't support trailing slashes ([2e6e24b](https://github.com/developmentseed/stac-auth-proxy/commit/2e6e24b9b39ce9bf06b6416ea639b0f610754682))
* **lifespan:** handle gateway errors on server health checks ([4e00c0e](https://github.com/developmentseed/stac-auth-proxy/commit/4e00c0e2952c7c368802cd41ca67c9e3cc4ec5f2)), closes [#141](https://github.com/developmentseed/stac-auth-proxy/issues/141)
* Make docker image to run as non-root. ([#116](https://github.com/developmentseed/stac-auth-proxy/issues/116)) ([35e06f3](https://github.com/developmentseed/stac-auth-proxy/commit/35e06f3c4fe518c02ab269724ae5c41f3f60ae04))
* **middleware:** enhance JSON parsing error handling ([#73](https://github.com/developmentseed/stac-auth-proxy/issues/73)) ([daf5d09](https://github.com/developmentseed/stac-auth-proxy/commit/daf5d095660ebe2401200fed1399168afe23e717)), closes [#72](https://github.com/developmentseed/stac-auth-proxy/issues/72)
* only transform non-errors ([8c66ba8](https://github.com/developmentseed/stac-auth-proxy/commit/8c66ba851612648330ea377a789687cc74481715))
* **openapi:** remove upstream servers ([#90](https://github.com/developmentseed/stac-auth-proxy/issues/90)) ([b54059b](https://github.com/developmentseed/stac-auth-proxy/commit/b54059bbdebd32078e9272701fa753e4a7e0f4ed)), closes [#74](https://github.com/developmentseed/stac-auth-proxy/issues/74)
* prevent double-declaration of openapi endpoint ([814145d](https://github.com/developmentseed/stac-auth-proxy/commit/814145d0fa1cfb4f2b864f53d29a77df7d4051ee))
* prevent down OIDC server from interfering with lifespan ([#31](https://github.com/developmentseed/stac-auth-proxy/issues/31)) ([4c9f4f9](https://github.com/developmentseed/stac-auth-proxy/commit/4c9f4f9acb99799357b13f03cd71ca3fda78d555))
* prevent JSON middleware from throwing 500s on non-transformed content ([aa27887](https://github.com/developmentseed/stac-auth-proxy/commit/aa2788703bb0f9d46cc87e2ef3bb8f7f4abb285d))
* prevent sending automatic accept-encoding headers upstream ([1189f97](https://github.com/developmentseed/stac-auth-proxy/commit/1189f9736f7113597b6bb6bb44fd4cf5de7be41e))
* process links w/o the prefix ([#70](https://github.com/developmentseed/stac-auth-proxy/issues/70)) ([8a09873](https://github.com/developmentseed/stac-auth-proxy/commit/8a098737ad578f37c10e65e3ef99b0de2c03a358))
* properly return error on invalid CQL2 filters ([5c5c856](https://github.com/developmentseed/stac-auth-proxy/commit/5c5c8562dc32994c6748f53f80ed101725962f9d))
* remove helm chart auth options. ([#126](https://github.com/developmentseed/stac-auth-proxy/issues/126)) ([42015b3](https://github.com/developmentseed/stac-auth-proxy/commit/42015b399938fc92589e8b377352420da9bc217c))
* retain proxy headers when behind proxy ([#88](https://github.com/developmentseed/stac-auth-proxy/issues/88)) ([74780f0](https://github.com/developmentseed/stac-auth-proxy/commit/74780f02e47963eb04be01a285895049a0cb1da3))
* Rework body augmentor to avoid error on empty POSTs ([f0ec9a5](https://github.com/developmentseed/stac-auth-proxy/commit/f0ec9a58892d602315bb4724ebb7c273019f03a7))
* run lin/tests on all pushes ([c565ae7](https://github.com/developmentseed/stac-auth-proxy/commit/c565ae7269d3d09bb8d725b406ba614885ef4752))
* serve healthz without trailing slash ([13acd0f](https://github.com/developmentseed/stac-auth-proxy/commit/13acd0f787c6b6a322c77062069b03c036503b0a))
* simplify cache by handling expired keys as KeyErrors ([a2d275d](https://github.com/developmentseed/stac-auth-proxy/commit/a2d275dee505d497bed08590c450ed3c5d5139ce))
* Skip CQL2 filter build for OPTIONS requests ([#123](https://github.com/developmentseed/stac-auth-proxy/issues/123)) ([6ee043e](https://github.com/developmentseed/stac-auth-proxy/commit/6ee043e5742d876df4fc34e63e538ae83997f8a1)), closes [#110](https://github.com/developmentseed/stac-auth-proxy/issues/110)
* stac-fastapi health checks. ([#128](https://github.com/developmentseed/stac-auth-proxy/issues/128)) ([42db5ef](https://github.com/developmentseed/stac-auth-proxy/commit/42db5efdb8d50c7a699640176673412371bc8d82))
* support filtering bulk item creation ([2c4a791](https://github.com/developmentseed/stac-auth-proxy/commit/2c4a791b9dc6d21a99722da73af8c4623a6470c5))
* update link transformation logic to prevent duplicate root_path in responses ([a71bd8e](https://github.com/developmentseed/stac-auth-proxy/commit/a71bd8e68c047d3a8feb51805cd2dde6775d45d5))


### Documentation

* add author ([add5630](https://github.com/developmentseed/stac-auth-proxy/commit/add56303fc7677fdb7dbe7d13f52c2f89e6bddaa))
* add callout for eoAPI usage discussion ([5915de4](https://github.com/developmentseed/stac-auth-proxy/commit/5915de4681a571d13061e114d759aca0a072a4ef))
* add changelog ([5710853](https://github.com/developmentseed/stac-auth-proxy/commit/57108531a5259f0d5db81a449e9b2246b2f0a522))
* add illustration for appying filters on non-filter compliant endpoints ([1a75550](https://github.com/developmentseed/stac-auth-proxy/commit/1a75550c56dcf39a316fce7b9f8c27689e5efc6e))
* add upgrade callout ([33a57c7](https://github.com/developmentseed/stac-auth-proxy/commit/33a57c7ae48d8eae5d007896fb21a32401019724))
* add version badges to README ([d962230](https://github.com/developmentseed/stac-auth-proxy/commit/d9622300275f4488cf1cda90a60f2f4ee013aa69))
* **architecture:** add data filtering diagrams ([48afd7e](https://github.com/developmentseed/stac-auth-proxy/commit/48afd7e353144b98e5b97bfc87cc067f34933634))
* build out separate documentation website ([#78](https://github.com/developmentseed/stac-auth-proxy/issues/78)) ([6c9b6ba](https://github.com/developmentseed/stac-auth-proxy/commit/6c9b6ba15c63a39410a71cac13de87daa84284f3))
* **cicd:** correct filename in deploy-mkdocs workflow ([5f00eca](https://github.com/developmentseed/stac-auth-proxy/commit/5f00eca440926652d4bb7abcf20748aac96e16bb))
* **cicd:** fix deploy step ([5178b92](https://github.com/developmentseed/stac-auth-proxy/commit/5178b92b189a8af8aff6ed923b312a494b03b573))
* **config:** add admonitions for more details ([40444cf](https://github.com/developmentseed/stac-auth-proxy/commit/40444cf2cfdd6cb8e660ecd35ce5f03055ca3f7e))
* **config:** cleanup formatting ([8a82d3d](https://github.com/developmentseed/stac-auth-proxy/commit/8a82d3d99156cf046d35e04278e78b33fe861899))
* correct swagger UI config details ([7684925](https://github.com/developmentseed/stac-auth-proxy/commit/768492521370bb9ccee7336ebf639df913aa14b9))
* **deployment:** Add details of deploying STAC Auth Proxy ([aaf3802](https://github.com/developmentseed/stac-auth-proxy/commit/aaf3802ed97096ffb1233875b1be59230da2a043))
* describe installation via pip ([bfb9ca8](https://github.com/developmentseed/stac-auth-proxy/commit/bfb9ca8e20fa86d248e9c5c375eb18359206761b))
* describe missing list collections filter functionality ([fe46940](https://github.com/developmentseed/stac-auth-proxy/commit/fe469400b7c18314552483320ad2efce4a612207))
* describe response validation ([d0b9099](https://github.com/developmentseed/stac-auth-proxy/commit/d0b909971a70e979ea5a8d2f013c04987f39a883))
* **docker:** Add OpenSearch backend stack to docker-compose ([#71](https://github.com/developmentseed/stac-auth-proxy/issues/71)) ([d779321](https://github.com/developmentseed/stac-auth-proxy/commit/d779321e992b0ae724520a38d3353cd7bbb07fcf))
* enhance middleware stack documentation with detailed descriptions and execution order ([06b51cb](https://github.com/developmentseed/stac-auth-proxy/commit/06b51cb8a48801d71f01aa1c433516e4832bcfcc))
* fix getting started link ([8efe5e5](https://github.com/developmentseed/stac-auth-proxy/commit/8efe5e5d6c449d91b2f957bad259649008bcc308))
* fix JSON ([f217216](https://github.com/developmentseed/stac-auth-proxy/commit/f2172161723d80c40b8d7ed07a6ab3e261a7fc68))
* fix/simplify footnote links ([0b53cab](https://github.com/developmentseed/stac-auth-proxy/commit/0b53cab026f6bf705d866da06b03b8c266aadcec))
* generalize example docker command ([e39778a](https://github.com/developmentseed/stac-auth-proxy/commit/e39778a2fdacd606c2bb546a090800d66a3d86ca))
* link + typo ([0d58b35](https://github.com/developmentseed/stac-auth-proxy/commit/0d58b35400b545d57570c74f36ccd9fcd329ef12))
* missing word ([7496b76](https://github.com/developmentseed/stac-auth-proxy/commit/7496b766dfe80825f3fcb0f1e3ec79e9e026c926))
* place docker instructions before installation ([6a14912](https://github.com/developmentseed/stac-auth-proxy/commit/6a1491293ed6ed78900ea86ba35a8d8bbb5afc21))
* prefer headings over nested list ([447a13d](https://github.com/developmentseed/stac-auth-proxy/commit/447a13d0ff4639d95e02009695d6fac62821c7c3))
* PRIVATE_ENDPOINTS can be used in DEFAULT_PUBLIC=False scenarios ([024f37c](https://github.com/developmentseed/stac-auth-proxy/commit/024f37c5c8b83fb07afd7677f00ee31451e9a9bc))
* **record-level-auth:** add filter factory guidance ([47c4e68](https://github.com/developmentseed/stac-auth-proxy/commit/47c4e6820501992ea1dc96dc7c8575a786dfd58e))
* Remove unused import of 'Expr' from record-level-auth ([4f86e7b](https://github.com/developmentseed/stac-auth-proxy/commit/4f86e7bb5a9306ba90584c86efb3017a96bb57fc))
* reorder callout ([3194bb3](https://github.com/developmentseed/stac-auth-proxy/commit/3194bb36470d69660a419ac19eb36aabc2a3025c))
* reorg comments ([2da2a26](https://github.com/developmentseed/stac-auth-proxy/commit/2da2a26c6060d3ee2d073fd455122c8d039c8a5b))
* rm experimental warning ([5c7f290](https://github.com/developmentseed/stac-auth-proxy/commit/5c7f2907662fd051d23059e789694ef60eb35634))
* temporarily disable starlette docstrings ([c4fd9e0](https://github.com/developmentseed/stac-auth-proxy/commit/c4fd9e07d3a03b0b77bdf1621f0402241a0c5ac2))
* **tips:** add details about CORS configuration ([#84](https://github.com/developmentseed/stac-auth-proxy/issues/84)) ([fc1e217](https://github.com/developmentseed/stac-auth-proxy/commit/fc1e2173e778f148f4f23cabe19611eb43c2df6a))
* update default public endpoints ([526c34c](https://github.com/developmentseed/stac-auth-proxy/commit/526c34c27229de2b24beb625e1ab1ec34284d79e))
* update filter class path syntax ([a7f5b1b](https://github.com/developmentseed/stac-auth-proxy/commit/a7f5b1b81606ae33e67cb6a98627367600d1e0db))
* update middleware descriptions ([d3d3769](https://github.com/developmentseed/stac-auth-proxy/commit/d3d3769593052900cf56c64b26962605cf3e48e5))
* update README to include ROOT_PATH configuration and usage tips ([e13a89d](https://github.com/developmentseed/stac-auth-proxy/commit/e13a89d6f8bed65d10bdc359311e189450917b91))
* update tips to describe non-upstream URL ([ebadd52](https://github.com/developmentseed/stac-auth-proxy/commit/ebadd52fd050543906f3a6c61b110900de62b330))
* updated features list ([625fc91](https://github.com/developmentseed/stac-auth-proxy/commit/625fc91a658f0150971ac0271184b9aaed86efe7))
* use footnotes for issue links ([5b94c7d](https://github.com/developmentseed/stac-auth-proxy/commit/5b94c7d0c45f97375c77025989f80446ad2b0b4b))
* **user-guide:** Add record-level auth section ([89377c6](https://github.com/developmentseed/stac-auth-proxy/commit/89377c6e23b3d21751b08eceb0dd222f8217663a))
* **user-guide:** Add route-level auth user guide ([#80](https://github.com/developmentseed/stac-auth-proxy/issues/80)) ([a840234](https://github.com/developmentseed/stac-auth-proxy/commit/a84023431634f933db965d09632736d55b3d26e8))
* **user-guide:** create getting-started section ([6ba081e](https://github.com/developmentseed/stac-auth-proxy/commit/6ba081ef174d529a2341058d262f324b6354819a))
* **user-guide:** fix configuration links ([11a5d28](https://github.com/developmentseed/stac-auth-proxy/commit/11a5d28756057e868d731d72ca3174e613f1a474))
* **user-guide:** fix tips file ref ([2d5d2ac](https://github.com/developmentseed/stac-auth-proxy/commit/2d5d2ac511fc304e8d88cae1567fb065c0316b4d))
* **user-guide:** formatting ([8ed08bc](https://github.com/developmentseed/stac-auth-proxy/commit/8ed08bc0713c816dbb0af336f147a62756114ffc))
* **user-guide:** Mention row-level authorization ([5fbd5df](https://github.com/developmentseed/stac-auth-proxy/commit/5fbd5dff311518684b566b6837a835ee1b753962))
* **user-guide:** Move configuration & installation to user guide ([170f001](https://github.com/developmentseed/stac-auth-proxy/commit/170f0015a6349cfdd45b7ea13464082128f70b7b))
* **user-guide:** Mv tips to user-guide ([d829800](https://github.com/developmentseed/stac-auth-proxy/commit/d829800fa838cb34a977e135e7576e4dc0ea03b7))
* **user-guide:** Reword authentication to authorization ([37fa12d](https://github.com/developmentseed/stac-auth-proxy/commit/37fa12d315ba6bd0f01a41cf906510a9f149e88b))
* whitespace ([b6a6319](https://github.com/developmentseed/stac-auth-proxy/commit/b6a6319cddc1fe6687ba33b226bb5469db752c63))


### Miscellaneous Chores

* release 0.11.1 ([976dfab](https://github.com/developmentseed/stac-auth-proxy/commit/976dfaba7bf01287045298e4834388f9fa6b1f45))

## [1.0.2](https://github.com/developmentseed/stac-auth-proxy/compare/v1.0.1...v1.0.2) (2026-03-03)


### Bug Fixes

* update link transformation logic to prevent duplicate root_path in responses ([a71bd8e](https://github.com/developmentseed/stac-auth-proxy/commit/a71bd8e68c047d3a8feb51805cd2dde6775d45d5))

## [1.0.1](https://github.com/developmentseed/stac-auth-proxy/compare/v1.0.0...v1.0.1) (2026-02-21)


### Bug Fixes

* ensure openapi spec demonstrates auth when cql2 filters apply ([#135](https://github.com/developmentseed/stac-auth-proxy/issues/135)) ([7310cee](https://github.com/developmentseed/stac-auth-proxy/commit/7310ceef462afadbc0a361211011549505aace94))
* support filtering bulk item creation ([2c4a791](https://github.com/developmentseed/stac-auth-proxy/commit/2c4a791b9dc6d21a99722da73af8c4623a6470c5))


### Documentation

* **record-level-auth:** add filter factory guidance ([47c4e68](https://github.com/developmentseed/stac-auth-proxy/commit/47c4e6820501992ea1dc96dc7c8575a786dfd58e))

## [1.0.0](https://github.com/developmentseed/stac-auth-proxy/compare/v0.11.1...v1.0.0) (2026-02-19)


### Features

* handle CORS by default ([#133](https://github.com/developmentseed/stac-auth-proxy/issues/133)) ([4c49b95](https://github.com/developmentseed/stac-auth-proxy/commit/4c49b955d73276fe5d995f1cd742e6f202834f7a))
* **helm:** add extraContainers in helm-chart ([#132](https://github.com/developmentseed/stac-auth-proxy/issues/132)) ([e0acecb](https://github.com/developmentseed/stac-auth-proxy/commit/e0acecb56cf4d74e3226d50bd7e3e306ac9d6609))
* validate transaction requests with CQL2 filters ([#131](https://github.com/developmentseed/stac-auth-proxy/issues/131)) ([254bd82](https://github.com/developmentseed/stac-auth-proxy/commit/254bd82576f09b0dab63f6c75ee8725ab1962879)), closes [#21](https://github.com/developmentseed/stac-auth-proxy/issues/21) [#22](https://github.com/developmentseed/stac-auth-proxy/issues/22)

> [!IMPORTANT]
> Previously, filters only applied to _read_ requests but they now also apply to _create/update/delete_ requests. If upgrading from v0.* and using record-level auth, ensure that your CQL2 filter factories are built to support both read and edit requests.


### Bug Fixes

* **jinja2:** use sandboxed environment ([504074f](https://github.com/developmentseed/stac-auth-proxy/commit/504074f9bf5cb17129ad38261d5bb499daced8b4))
* remove helm chart auth options. ([#126](https://github.com/developmentseed/stac-auth-proxy/issues/126)) ([42015b3](https://github.com/developmentseed/stac-auth-proxy/commit/42015b399938fc92589e8b377352420da9bc217c))
* stac-fastapi health checks. ([#128](https://github.com/developmentseed/stac-auth-proxy/issues/128)) ([42db5ef](https://github.com/developmentseed/stac-auth-proxy/commit/42db5efdb8d50c7a699640176673412371bc8d82))

## [0.11.1](https://github.com/developmentseed/stac-auth-proxy/compare/v0.11.0...v0.11.1) (2026-01-13)


### Features

* Add helm chart auth options. ([#118](https://github.com/developmentseed/stac-auth-proxy/issues/118)) ([cfae34b](https://github.com/developmentseed/stac-auth-proxy/commit/cfae34b5a3a50596dc2ba13bd51cc96144e78d80))
* Add helm README.md and unit tests ([#117](https://github.com/developmentseed/stac-auth-proxy/issues/117)) ([74a1bc8](https://github.com/developmentseed/stac-auth-proxy/commit/74a1bc8e361cbc85bb48dff4fc4019b2ad8d196d))


### Bug Fixes

* Enhance type safety in middleware and utility functions ([#122](https://github.com/developmentseed/stac-auth-proxy/issues/122)) ([52cdd0e](https://github.com/developmentseed/stac-auth-proxy/commit/52cdd0eaf8eb0c98cdb4c18d54c2d23979e5d72a))
* Helm chart and app version mismatch. ([#120](https://github.com/developmentseed/stac-auth-proxy/issues/120)) ([7998675](https://github.com/developmentseed/stac-auth-proxy/commit/79986751390ae243dee565b2b273d8d67aab5ba5))
* Make docker image to run as non-root. ([#116](https://github.com/developmentseed/stac-auth-proxy/issues/116)) ([35e06f3](https://github.com/developmentseed/stac-auth-proxy/commit/35e06f3c4fe518c02ab269724ae5c41f3f60ae04))
* Skip CQL2 filter build for OPTIONS requests ([#123](https://github.com/developmentseed/stac-auth-proxy/issues/123)) ([6ee043e](https://github.com/developmentseed/stac-auth-proxy/commit/6ee043e5742d876df4fc34e63e538ae83997f8a1)), closes [#110](https://github.com/developmentseed/stac-auth-proxy/issues/110)


### Documentation

* temporarily disable starlette docstrings ([c4fd9e0](https://github.com/developmentseed/stac-auth-proxy/commit/c4fd9e07d3a03b0b77bdf1621f0402241a0c5ac2))


### Miscellaneous Chores

* release 0.11.1 ([976dfab](https://github.com/developmentseed/stac-auth-proxy/commit/976dfaba7bf01287045298e4834388f9fa6b1f45))

## [0.11.0](https://github.com/developmentseed/stac-auth-proxy/compare/v0.10.1...v0.11.0) (2025-12-15)


### Bug Fixes

* **auth:** Authentication failures now return 401 instead of 403
* **auth:** correct HTTP status codes for authentication and authorization failures ([#108](https://github.com/developmentseed/stac-auth-proxy/issues/108)) ([17227e4](https://github.com/developmentseed/stac-auth-proxy/commit/17227e447c188d73426ed1771cc45d95b141a4e9))
* Ensure x-forwarded-port header is used in Forwarded header ([#115](https://github.com/developmentseed/stac-auth-proxy/issues/115)) ([78525b1](https://github.com/developmentseed/stac-auth-proxy/commit/78525b131b259748e00df1e38c54fb152414da4d))

## [0.10.1](https://github.com/developmentseed/stac-auth-proxy/compare/v0.10.0...v0.10.1) (2025-12-03)


### Features

* **helm:** Add support for initContainers. ([#104](https://github.com/developmentseed/stac-auth-proxy/issues/104)) ([a7ca408](https://github.com/developmentseed/stac-auth-proxy/commit/a7ca408b73379cd75980f005a5e2fac2d815b700))


### Bug Fixes

* **lifespan:** allow endpoints that don't support trailing slashes ([2e6e24b](https://github.com/developmentseed/stac-auth-proxy/commit/2e6e24b9b39ce9bf06b6416ea639b0f610754682))


### Documentation

* Remove unused import of 'Expr' from record-level-auth ([4f86e7b](https://github.com/developmentseed/stac-auth-proxy/commit/4f86e7bb5a9306ba90584c86efb3017a96bb57fc))

## [0.10.0](https://github.com/developmentseed/stac-auth-proxy/compare/v0.9.2...v0.10.0) (2025-10-14)


### Features

* skip json middleware based on response data type ([#103](https://github.com/developmentseed/stac-auth-proxy/issues/103)) ([16b05c3](https://github.com/developmentseed/stac-auth-proxy/commit/16b05c3c201e04b2027c6a7ef632477febdbecfb))
* support customizing port when running as a module ([9a18c49](https://github.com/developmentseed/stac-auth-proxy/commit/9a18c49f74695dfdde516f6554a6bb6f6244937c))


### Documentation

* **config:** add admonitions for more details ([40444cf](https://github.com/developmentseed/stac-auth-proxy/commit/40444cf2cfdd6cb8e660ecd35ce5f03055ca3f7e))
* **config:** cleanup formatting ([8a82d3d](https://github.com/developmentseed/stac-auth-proxy/commit/8a82d3d99156cf046d35e04278e78b33fe861899))
* update tips to describe non-upstream URL ([ebadd52](https://github.com/developmentseed/stac-auth-proxy/commit/ebadd52fd050543906f3a6c61b110900de62b330))

## [0.9.2](https://github.com/developmentseed/stac-auth-proxy/compare/v0.9.1...v0.9.2) (2025-09-08)


### Bug Fixes

* improve link processing ([#95](https://github.com/developmentseed/stac-auth-proxy/issues/95)) ([e52b5a9](https://github.com/developmentseed/stac-auth-proxy/commit/e52b5a972539232da4fc0a74b3a8abad7579f41e))
* properly return error on invalid CQL2 filters ([5c5c856](https://github.com/developmentseed/stac-auth-proxy/commit/5c5c8562dc32994c6748f53f80ed101725962f9d))


### Documentation

* enhance middleware stack documentation with detailed descriptions and execution order ([06b51cb](https://github.com/developmentseed/stac-auth-proxy/commit/06b51cb8a48801d71f01aa1c433516e4832bcfcc))
* update filter class path syntax ([a7f5b1b](https://github.com/developmentseed/stac-auth-proxy/commit/a7f5b1b81606ae33e67cb6a98627367600d1e0db))

## [0.9.1](https://github.com/developmentseed/stac-auth-proxy/compare/v0.9.0...v0.9.1) (2025-09-04)


### Bug Fixes

* **openapi:** remove upstream servers ([#90](https://github.com/developmentseed/stac-auth-proxy/issues/90)) ([b54059b](https://github.com/developmentseed/stac-auth-proxy/commit/b54059bbdebd32078e9272701fa753e4a7e0f4ed)), closes [#74](https://github.com/developmentseed/stac-auth-proxy/issues/74)

## [0.9.0](https://github.com/developmentseed/stac-auth-proxy/compare/v0.8.0...v0.9.0) (2025-09-03)


### Features

* make use of Server-Timing header ([c894026](https://github.com/developmentseed/stac-auth-proxy/commit/c8940260cbe69bdc7868f16f5c8a76f9ae29b9d6)), closes [#69](https://github.com/developmentseed/stac-auth-proxy/issues/69)
* remove applied filters on response links ([#67](https://github.com/developmentseed/stac-auth-proxy/issues/67)) ([2b2b224](https://github.com/developmentseed/stac-auth-proxy/commit/2b2b22459c0e577b5a1d5d1e04c7de406d074a99)), closes [#64](https://github.com/developmentseed/stac-auth-proxy/issues/64)


### Bug Fixes

* **middleware:** enhance JSON parsing error handling ([#73](https://github.com/developmentseed/stac-auth-proxy/issues/73)) ([daf5d09](https://github.com/developmentseed/stac-auth-proxy/commit/daf5d095660ebe2401200fed1399168afe23e717)), closes [#72](https://github.com/developmentseed/stac-auth-proxy/issues/72)
* retain proxy headers when behind proxy ([#88](https://github.com/developmentseed/stac-auth-proxy/issues/88)) ([74780f0](https://github.com/developmentseed/stac-auth-proxy/commit/74780f02e47963eb04be01a285895049a0cb1da3))

## [0.8.0](https://github.com/developmentseed/stac-auth-proxy/compare/v0.7.1...v0.8.0) (2025-08-16)


### Features

* add `configure_app` for applying middleware to existing FastAPI applications ([#85](https://github.com/developmentseed/stac-auth-proxy/issues/85)) ([3c5cf69](https://github.com/developmentseed/stac-auth-proxy/commit/3c5cf694c26520fd141faf84c23fe621413e244e))
* add aws lambda handler ([#81](https://github.com/developmentseed/stac-auth-proxy/issues/81)) ([214de02](https://github.com/developmentseed/stac-auth-proxy/commit/214de02301b909347e847c66c7e12b88ba74fdea))
* add configurable audiences ([#83](https://github.com/developmentseed/stac-auth-proxy/issues/83)) ([58d05ea](https://github.com/developmentseed/stac-auth-proxy/commit/58d05ea665c48cc86e4774e2e7337b7ad277ab2f))
* **config:** expand default endpoints ([#79](https://github.com/developmentseed/stac-auth-proxy/issues/79)) ([6718991](https://github.com/developmentseed/stac-auth-proxy/commit/67189917c2b38620dc92fb7836d25b68901f59ae))


### Documentation

* add changelog ([5710853](https://github.com/developmentseed/stac-auth-proxy/commit/57108531a5259f0d5db81a449e9b2246b2f0a522))
* add version badges to README ([d962230](https://github.com/developmentseed/stac-auth-proxy/commit/d9622300275f4488cf1cda90a60f2f4ee013aa69))
* **architecture:** add data filtering diagrams ([48afd7e](https://github.com/developmentseed/stac-auth-proxy/commit/48afd7e353144b98e5b97bfc87cc067f34933634))
* build out separate documentation website ([#78](https://github.com/developmentseed/stac-auth-proxy/issues/78)) ([6c9b6ba](https://github.com/developmentseed/stac-auth-proxy/commit/6c9b6ba15c63a39410a71cac13de87daa84284f3))
* **cicd:** correct filename in deploy-mkdocs workflow ([5f00eca](https://github.com/developmentseed/stac-auth-proxy/commit/5f00eca440926652d4bb7abcf20748aac96e16bb))
* **cicd:** fix deploy step ([5178b92](https://github.com/developmentseed/stac-auth-proxy/commit/5178b92b189a8af8aff6ed923b312a494b03b573))
* **deployment:** Add details of deploying STAC Auth Proxy ([aaf3802](https://github.com/developmentseed/stac-auth-proxy/commit/aaf3802ed97096ffb1233875b1be59230da2a043))
* describe installation via pip ([bfb9ca8](https://github.com/developmentseed/stac-auth-proxy/commit/bfb9ca8e20fa86d248e9c5c375eb18359206761b))
* **docker:** Add OpenSearch backend stack to docker-compose ([#71](https://github.com/developmentseed/stac-auth-proxy/issues/71)) ([d779321](https://github.com/developmentseed/stac-auth-proxy/commit/d779321e992b0ae724520a38d3353cd7bbb07fcf))
* fix getting started link ([8efe5e5](https://github.com/developmentseed/stac-auth-proxy/commit/8efe5e5d6c449d91b2f957bad259649008bcc308))
* **tips:** add details about CORS configuration ([#84](https://github.com/developmentseed/stac-auth-proxy/issues/84)) ([fc1e217](https://github.com/developmentseed/stac-auth-proxy/commit/fc1e2173e778f148f4f23cabe19611eb43c2df6a))
* **user-guide:** Add record-level auth section ([89377c6](https://github.com/developmentseed/stac-auth-proxy/commit/89377c6e23b3d21751b08eceb0dd222f8217663a))
* **user-guide:** Add route-level auth user guide ([#80](https://github.com/developmentseed/stac-auth-proxy/issues/80)) ([a840234](https://github.com/developmentseed/stac-auth-proxy/commit/a84023431634f933db965d09632736d55b3d26e8))
* **user-guide:** create getting-started section ([6ba081e](https://github.com/developmentseed/stac-auth-proxy/commit/6ba081ef174d529a2341058d262f324b6354819a))
* **user-guide:** fix configuration links ([11a5d28](https://github.com/developmentseed/stac-auth-proxy/commit/11a5d28756057e868d731d72ca3174e613f1a474))
* **user-guide:** fix tips file ref ([2d5d2ac](https://github.com/developmentseed/stac-auth-proxy/commit/2d5d2ac511fc304e8d88cae1567fb065c0316b4d))
* **user-guide:** formatting ([8ed08bc](https://github.com/developmentseed/stac-auth-proxy/commit/8ed08bc0713c816dbb0af336f147a62756114ffc))
* **user-guide:** Mention row-level authorization ([5fbd5df](https://github.com/developmentseed/stac-auth-proxy/commit/5fbd5dff311518684b566b6837a835ee1b753962))
* **user-guide:** Move configuration & installation to user guide ([170f001](https://github.com/developmentseed/stac-auth-proxy/commit/170f0015a6349cfdd45b7ea13464082128f70b7b))
* **user-guide:** Mv tips to user-guide ([d829800](https://github.com/developmentseed/stac-auth-proxy/commit/d829800fa838cb34a977e135e7576e4dc0ea03b7))
* **user-guide:** Reword authentication to authorization ([37fa12d](https://github.com/developmentseed/stac-auth-proxy/commit/37fa12d315ba6bd0f01a41cf906510a9f149e88b))

## [0.7.1](https://github.com/developmentseed/stac-auth-proxy/compare/v0.7.0...v0.7.1) (2025-07-31)


### Bug Fixes

* ensure OPTIONS requests are sent upstream without auth check ([#76](https://github.com/developmentseed/stac-auth-proxy/issues/76)) ([855183a](https://github.com/developmentseed/stac-auth-proxy/commit/855183a7ccf0331d772cb91411b8dca905b05181)), closes [#75](https://github.com/developmentseed/stac-auth-proxy/issues/75)
* process links w/o the prefix ([#70](https://github.com/developmentseed/stac-auth-proxy/issues/70)) ([8a09873](https://github.com/developmentseed/stac-auth-proxy/commit/8a098737ad578f37c10e65e3ef99b0de2c03a358))


### Documentation

* update middleware descriptions ([d3d3769](https://github.com/developmentseed/stac-auth-proxy/commit/d3d3769593052900cf56c64b26962605cf3e48e5))

## [0.7.0](https://github.com/developmentseed/stac-auth-proxy/compare/v0.6.1...v0.7.0) (2025-07-19)


### Features

* **config:** add root path GET requests to default public endpoints ([#62](https://github.com/developmentseed/stac-auth-proxy/issues/62)) ([59c6a97](https://github.com/developmentseed/stac-auth-proxy/commit/59c6a9740cf5cbcf43aaf5b556c37714db40ada7))

## [0.6.1](https://github.com/developmentseed/stac-auth-proxy/compare/0.6.0...v0.6.1) (2025-07-18)


### Bug Fixes

* fix status check for 2xx responses ([#59](https://github.com/developmentseed/stac-auth-proxy/issues/59)) ([5b03cb3](https://github.com/developmentseed/stac-auth-proxy/commit/5b03cb35e6fb7a10cd51e0fcd1ab86d4bb4292cc))


### Documentation

* add illustration for appying filters on non-filter compliant endpoints ([1a75550](https://github.com/developmentseed/stac-auth-proxy/commit/1a75550c56dcf39a316fce7b9f8c27689e5efc6e))
* prefer headings over nested list ([447a13d](https://github.com/developmentseed/stac-auth-proxy/commit/447a13d0ff4639d95e02009695d6fac62821c7c3))
