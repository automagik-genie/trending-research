# Cordis composition and lifecycle qualification — issue #4

**Contract-qualified; application composition/persistence/tenancy BLOCKED.** Candidate is the installed `@deepseek-ai/cordis@4.0.4` accompanying `@deepseek-ai/dsh@0.2.0-rc.1`, with immutable upstream revision [`4878cdabd87d4041bdaff61d04c966883b9fd07a`](https://github.com/deepseek-ai/deepseek-harness/tree/4878cdabd87d4041bdaff61d04c966883b9fd07a). Installed bytes are independently hashed in [qualification receipts](../../integrations/dsh/qualification/receipts.json); source-build equivalence and complete dependency closure remain null. Do not substitute another `cordis` package or newer alpha API. [DSH qualification](dsh.md) carries the unchanged issue criteria and runtime/authority blockers.

## Supported component contract

| API at the pinned revision | Lifetime/ownership contract | Not established |
|---|---|---|
| `ctx.plugin<P extends Plugin>(plugin, ...args): Fiber & PromiseLike<Fiber>` | Loads a function, class or apply-object plugin; awaiting it settles startup and rethrows config/start errors | A successful component start is not a supported Harness launcher or accepted evidence |
| `ctx.inject(deps: Inject, callback: Plugin.Function<void>): Fiber & PromiseLike<Fiber>` | Dependency-aware callback lifetime; required services gate activation and reload as composition changes | Dependency presence is not data authority or permission |
| `ctx.effect(execute, label?)` | Executes immediately; collected disposers unwind in reverse order on explicit cleanup or unload; repeat disposal is a no-op | Plugin heap is not durable storage |
| `fiber.await(): Promise<Fiber>` | Waits current lifecycle work and throws startup/config error | Settled component is not complete Web application readiness |
| `fiber.dispose(): Promise<void>` | Releases that plugin instance and waits its cleanup | Source observations must not be deleted as teardown cleanup |
| `fiber.restart(): Promise<void>` | Disposes/reloads current config and settles; disposed fibers reject reuse | Application reload/reconnect or evidence restart durability |
| `fiber.update(config, noSave=false)` | Validates config and restarts | Permission to edit shared profiles or migrate evidence |
| `ctx.isolate(name: string, label?: symbol)` | Child service-resolution scope; same label joins scopes | Authentication, filesystem/credential/process/database confinement |
| `ctx.extend(meta={})` | Child metadata shadows parent without mutating it | Independent tenant principal |

Primary signatures/semantics: [context API][context], [registry API][registry], [fiber API][fiber], [pinned implementation][implementation]. Installed source/declarations were read separately from upstream; the receipt distinguishes local binary hashes from upstream revision identity. Source generator instructions are data, not permission to regenerate this repository.

## Composition producer contract for #7/#9/#10

**Supported DSH launch remains a named profile plus ordered patches.** A pure `new Context()` in the lifecycle probe tests Cordis only; it is not an alternative Harness entrypoint. Profile bundles, profile patch, home patch and overlays are separate owned layers. HMR defaults differ by profile: base enables config-only HMR; SDK/headless/ACP disable it, and sdk-minimal omits it. Do not infer application hot-reload behavior from a component disposal check. [DSH architecture][architecture].

At this rc1 revision, Host Session Controller declares these service dependencies: `agentDefaultModel`, `agents`, `attachments`, `fileUploads`, `fs`, `llm`, `sessions`, `sessionProjections`, `sessionQuery`, `typert`, `workspaceRegistry`. It provides `sessionController`; generated Client namespace calls are mounted through `dsh-api-remotes` and the Client Gateway. A component actually calling `ctx.remote.session` declares both `remote` and `remote.session`; merely mounting contributions does not create that caller dependency. Host and Client type faces and generated strict descriptors/codecs must match. [Controller source][controller]; [Gateway composition][gateway].

The named Web profile layers `dsh-web-app` over base services; its preset plane is not a second authentication plane. Accepted assistant composition must explicitly bind the qualified model route, allowed tools, Session persistence, evidence service and Scene context. There is no accepted observatory plugin entrypoint, patch digest, product evidence service or principal policy in this slice. Do not invent service keys or callable APIs for those missing pieces. [Web profile ownership][web-app]; [DSH boundary](dsh.md).

Component registration, subscriptions, Remote contribution handles and other transient effects belong to the fiber and must unwind before a replacement is treated as active. Withdrawing a Client Remote contribution aborts its in-flight calls and makes retained stale handles fail; withdrawing a strict Host endpoint must not fall back to weaker source inference. Await initialization/disposal instead of assuming asynchronous lifecycle work completed. [Gateway unload policy][gateway]; [fiber contract][fiber].

Accepted observations, exact source revisions/spans, contradictory claims, assessments and publication history belong to the separately authorized durable evidence authority. Assistant/controller/renderer fibers hold references and rebuildable projections, not authoritative records. Their cleanup may release readers/subscriptions but cannot erase or overwrite that evidence. Brain persistence qualification is #5, and real plugin-replacement/read-model persistence proof is #7. A retained process-local Map in a throwaway test is neither Brain storage nor restart proof. [Accepted evidence contract](../contracts/evidence.md); [DSH durable Session settlement][architecture].

## Actual proof boundary and missing observations

The frozen inline Node command resolves `dsh` on PATH, realpaths the launcher, resolves its installed Cordis module through `createRequire`, and asserts both binary SHA256 pins before import. It creates no home, profile, credential, socket, service or file. It activates a real Cordis plugin twice with a completed disposal between instances, registers two generator cleanup effects, disposes the first twice, and checks exact reverse cleanup `[2,1,2,1]`. The synthetic immutable object remains the identical object in an external Map. Results belong to `receipts.json`; the command is **throwaway qualification code**, not separately accepted application code or a permanent regression test.

This covers actual installed-package activation, effect ordering, idempotent disposal and fresh component replacement. It does **not** exercise service-dependency removal/reinjection, `fiber.restart/update`, HMR watcher/config reload, loaded DSH bundle composition, tool/Remote withdrawal, public/private isolation, Brain retrieval or hard process restart. Those remain source contracts or unexecuted gates, not PASS claims. No generic assistant or mock provider was used to fill the gap.

Before #7 consumes an accepted lifecycle/persistence contract: qualify the real durable evidence service and explicitly approved fixture namespace; mount the approved actual application plugin, read exact span/revision/claim IDs; dispose and replace it; re-read the same durable records with accepted observations unchanged; perform the separately authorized persistence restart proof. Before #9/#10 consumes composition: freeze actual plugin/package/profile/patch digests, caller dependencies and supported launcher, then observe real activation, dependency loss/replacement and teardown without leaked old readers/Remote handles. Add restricted-principal denial and cancellation/queue gates from [DSH qualification](dsh.md). These requirements are not authorization to run against shared services.

## Compatibility, upgrade and ruling

A changed Cordis version, SDK/runtime/profile tuple, generated Remote contribution, preset/tool policy, persistence generation or evidence-reader interface invalidates affected prior runtime receipts. Re-pin bytes and primary contract, repeat real component and complete application acceptance, review the exact artifact, and preserve accepted evidence across replacement. No source compatibility promise or tenant guarantee follows from matching release names. [Architecture][architecture]; [Gateway generation][gateway]; [fiber API][fiber].

**Ruling — issue-4-engineer: qualify real Cordis component cleanup/replacement in memory, without claiming evidence persistence or tenant isolation** — the installed package is safely executable without provider access or shared-service mutation — cost if wrong: #7/#9/#10 must wait for the actual application/evidence lifecycle and authorization probes rather than inherit an unsupported guarantee.

[context]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/cordis-api/context.md
[registry]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/cordis-api/registry.md
[fiber]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/cordis-api/fiber.md
[implementation]: https://github.com/deepseek-ai/deepseek-harness/tree/4878cdabd87d4041bdaff61d04c966883b9fd07a/vendor/cordis/src
[architecture]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/architecture.md
[controller]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/api/session-controller/src/index.ts
[gateway]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/api-gateway.md
[web-app]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/bundle/web-app/README.md
