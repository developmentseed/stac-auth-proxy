# Changelog

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
