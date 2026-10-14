# DSH assistant integration qualification — issue #4

**Verdict: BLOCKED for application embedding and multi-user acceptance.** All four original criteria remain required. [Historical contract/component receipts](../../integrations/dsh/qualification/receipts.json) and [the later failed-once diagnostic/disposition record](../../integrations/dsh/qualification/sandbox-readiness.json) have distinct proof boundaries; neither is an implemented assistant or deployment receipt. Live acceptance observations remain null. No paid model call, personal operator-session access, installation, shared-service restart or deployment follows from this qualification.

## Identity and compatibility

The candidate tuple is `@deepseek-ai/dsh@0.2.0-rc.1`, upstream revision [`4878cdabd87d4041bdaff61d04c966883b9fd07a`](https://github.com/deepseek-ai/deepseek-harness/tree/4878cdabd87d4041bdaff61d04c966883b9fd07a), and its installed `@deepseek-ai/cordis@4.0.4`. Installed manifest/executable and generated declaration hashes are recorded separately in the receipt. Matching release labels do **not** attest that emitted installed JavaScript reproduces the upstream commit. The full installed dependency closure, dedicated profile, ordered patch digests and running Web service identity are not qualified. The anonymous loopback fence does not establish which revision the serving process uses.

The same-release TypeScript `@deepseek-ai/dsh-sdk-client` is a supported source contract, not an installed/started client in this slice. Do not mix a newer alpha SDK, Cordis fork or wrapper with rc1 and present it as this tuple. [SDK resolution and lifecycle][sdk-client]; [profile architecture][architecture]; [Cordis contract](cordis.md).

Upgrade gates: pin the complete launcher/SDK/Cordis/profile/patch/dependency artifact tuple; compare generated Remote types, codecs, wire notifications, tool policy and Session persistence generations; repeat every real acceptance probe below on that tuple; independently review the new exact artifact. SDK `serverInfo.version = '0.0.1'` is not negotiated compatibility. Preserve accepted source revisions, spans and assessments when replacing agents/plugins; do not reinterpret stored claims under a new method without a distinct assessment revision. [SDK wire limits][sdk-protocol]; [Session log and migration ownership][architecture].

## Supported launcher and hosting decision

Supported application launch is `dsh --profile <name>` or `dsh <name>`. Shipped profiles include `web`, `headless`, `sdk`, `sdk-minimal` and `acp`. Additional overlays use repeatable `--patch <path>` in argument order. The composition order is listed bundles, profile patch, home patch, then overlays; a patch replaces the targeted row's whole config. A supported custom tree is a named profile plus patches, not a hand-built in-process Harness application. `sdk-minimal` is an upstream standalone bundle, not an arbitrary caller tree. [Architecture][architecture].

Qualification launch requires an approved dedicated `DSH_HOME`, named profile, persistent Session storage, ordered patches and scrubbed credential environment. Historical help/version reads did not launch a profile. A later isolated, no-model named-profile diagnostic was admitted, but failed before native metadata; it supplies no accepted running profile or Session store. Do not use the current operator's home, browser cookie, session list or tool registry as tenant fixtures. The supported Web launch shape is `dsh --profile web --no-open --port <approved-port>` under an explicitly approved dedicated home; it is not execution permission. [Web launcher][web-app].

| Hosting surface | Validated contract constraint | Decision |
|---|---|---|
| Same-release SDK subprocess | Durable enqueue/events and whole-agent status; no per-session cancel, history/reconnect or incremental assistant chunks in the SDK wire | Insufficient for unchanged #4 acceptance |
| Named Web profile and generated API client | Follow/cancel/page/projections and connection generations exist; every authenticated request is the operator Peer | Candidate for further authorized qualification; not tenant-safe |
| Cordis preset or third-party wrapper | Component composition does not establish application embedding or authorization | Not acceptance evidence or a substitute runtime |

The host webserver itself provides no TLS/authentication/origin policy. The Connection and feature route owners provide their policies; a public endpoint needs an explicitly reviewed transport and authorization boundary, not just a non-loopback bind or reverse proxy. Upstream Web and Connection prose contains differing LAN/bind statements; no public-hosting guarantee is inferred. [Webserver limits][webserver]; [Connection trust][connection].

## SDK signature and limits

At the pinned source revision, the supported high-level client is:

```ts
new DeepSeekHarness({ profile, patches, provider, model, reasoningEffort?, maxTokens?, /* launch options */ })
harness.start()
harness.run(input, { sessionId?, onNotification? })
// RunResult: { sessionId, finalResponse, events, notifications }
harness.session(id?)
harness.close()
```

The newline-delimited JSON-RPC request set is exactly:

```text
initialize({ cwd, provider, model, reasoningEffort?, maxTokens? })
  -> { serverInfo: { name: 'deepseek-harness-sdk-runtime', version } }
session/prompt({ sessionId, contentBlocks }) -> { messageId }
shutdown() -> {}
```

`maxTokens` must be a positive safe integer. Initialization resolves the exact provider/model route before prompt admission. Notifications are `session.event`, `session.status` (`running`/`idle`), `subagent.started` and `subagent.finished`. Events are sent for **every Session in the runtime**; client-side session-tree filtering is not access control. `run().finalResponse` is the last committed root assistant text between prompt receipt and whole-agent idle, not a causally exclusive per-prompt answer. Supplied client `env` replaces the child environment. [Client][sdk-client]; [protocol][sdk-protocol].

There is no SDK prompt-cancel/session-close method, no history/read/reconnect method, and no assistant token-delta notification. Closing its owned subprocess affects all Sessions in that runtime. Durable `session.event` facts are not the process-local `agent/assistant-stream` presentation frames consumed remotely by Web follow. An SDK close, subscription filter or cached answer cannot satisfy the missing Web/cancel/tenant criteria. [SDK wire][sdk-protocol]; [stream ownership][architecture].

## Exact rc1 Web/API caller surface

Installed rc1 generated `dsh-api-session-controller/lib/typert.remote-client.d.ts` and `lib/types/types.d.ts` are the caller authority. Their digests are in the receipt; the installed declaration is not a live invocation receipt. Host request/response types are also at [the immutable source][session-types]. The generated unary methods return `Promise<RemoteResult<T>>`, not bare `T`; generated streams return `RemoteStreamHandle<T, never>`. Consumers must handle the result envelope and explicit failures rather than treating acknowledgement as completion.

```ts
ctx.remote.session.create(request: SessionCreateRequest)
ctx.remote.session.prompt(request: SessionPromptRequest, signal?: AbortSignal)
ctx.remote.session.cancel(request: SessionCancelRequest)
ctx.remote.session.updateQueue(request: SessionUpdateQueueRequest)
ctx.remote.session.follow(request: SessionFollowRequest, signal?: AbortSignal)
ctx.remote.session.page(request: SessionPageRequest, signal?: AbortSignal)
ctx.remote.session.projections(request: { sessionId }, signal?: AbortSignal)
ctx.remote.session.control(signal?: AbortSignal)
```

`SessionCreateRequest` has optional `workspaceId`, `cwd`, `sessionId`, `agentPreset`; `workspaceId` and `cwd` cannot be combined. Explicit Session adoption/resume retains a writer lock; contention returns `session/writer-held`. Prompt fields are `requestId`, `sessionId`, `mode: 'queue' | 'steer'`, `content: PromptContentPart[]`, optional `clientTimeZone`; receipt is `{accepted:true}` after inbox admission. It is not proof of tool/model execution. Cancellation has only `sessionId`; it requires a live Agent. [Controller policy][session-controller]; [command implementation][session-commands].

Follow fields are `address: {kind:'session',sessionId}` (or the separately typed direct-subagent address), optional `assistantStream:true`, `maxMessages`, `turnWindow:{minMessages,minTurns}`. Page adds required inclusive `throughSeq` and optional `beforeSeq`. Follow begins with `snapshot` containing `header`, `cursor`, `records`, `hasMore`, `projections` and optional active-assistant baseline. Subsequent entries are durable events or cursorless `assistant-stream` start/chunk/end frames. The generated client journal repairs carrier loss/sequence gaps using tail pages and reopened follow; business/persistence/continuity failures remain visible. [Request/frame types][session-types]; [journal contract][session-controller].

Unary HTTP is `POST /api/<namespace>/<method>` with a named `args` object. Parameter names matter: e.g. cancel uses `{"args":{"request":{"sessionId":"..."}}}`; installed rc1 session list uses `{"args":{"_request":{}}}`. Logical streams use authenticated `/api/remote.mux` WebSocket through the generated client, **not** an invented SSE or REST `/follow` endpoint. `AbortSignal` cancels transport/handler work; aborting an accepted prompt is not cancelling its live Agent. [Gateway][gateway]; [controller][session-controller].

### Cancellation and reconnect are unresolved acceptance, not acknowledgements

Pinned `SessionCommandController.cancel` calls `agent.cancel({kind:'user'}, {keepInbox:true})`. **Queued work is intentionally retained.** A cancel acknowledgement therefore cannot establish “stops new work.” `updateQueue` targets one pending `itemId` with a typed `QueueAction`; removal races with inbox claims and cannot be assumed atomic with cancellation. No stop-and-clear admission transaction is qualified here. The accepted application cancellation policy must prevent further admission/queued execution and prove it against real active and queued work; silently redefining the criterion as “cancel the current turn only” is not allowed. [Exact command source][session-commands].

`ctx.connection.reconnect()` starts a new connection generation; observable states are `connecting`, `connected`, `disconnected`, with `connected` only after a ready item. Control baselines replace process-local projection state. Reopened history retains durable Session identity/cursors, not unsettled ephemeral chunks across hard process loss. Cancellation, cold resume, carrier reconnect and durable storage/restart are separate observations; none was exercised against an authorized fixture Session here. [Connection generations][connection]; [Session follow][session-controller]; [durable settlement][architecture].

## Allowed tools and public/private boundary

This qualification authorizes **no model-visible tools in a running tenant profile**. The permitted assistant design is read-only access to the caller-authorized Scene and its exact cited Claim/EvidenceSpan/SourceRevision/PublicationRevision records. Actual tool names/signatures, implementing plugin, ACL and principals remain unqualified; no fake tool API is introduced. Mutations, shell/filesystem/process access, credential/config/plugin management, arbitrary MCP access, private-memory recall, publication and spending are excluded. [Tool restriction/guard seams][tools].

Scene wire authority is contract `1.0.0` at `schemas/evidence.schema.json`: `id`, nullable `publication_revision_id`, `assessment_ids`, `entity_ids`, `evidence_cutoff`, `method_version`. Preserve these exact IDs and cutoff when assembling model context or following citations. The supplied synthetic fixture is `scene:example:1`, entities `entity:builder`, `entity:investor-a`, `entity:investor-b`, cutoff `2020-02-03T00:00:00Z`, method `fixture-method/1`. Its draft publication is **not** publication approval; its amounts/authority remain null. [Accepted evidence contract](../contracts/evidence.md); [fixture](../../tests/fixtures/evidence_contracts.json).

A trusted server must bind principal → Session → allowed Scene/evidence/tool set before model dispatch and at tool execution/read-back. IDs/cutoff/prompt prose are not authorization. A public Session may cite only approved public evidence; a private Session's history, prompts, tool arguments/results, projections, storage, attachments and links must stay within its explicit principal scope. Different cookies, different Session IDs or Cordis `isolate()` do not provide that enforcement. Source text/quotes/tool results remain untrusted evidence, never grants to run tools or change policy. [Operator authentication][connection]; [Cordis scope](cordis.md).

The default Web API is a one-operator surface: launch token exchanged only at `GET /`, authority-bound signed HttpOnly SameSite=Strict cookie, Host/Origin checks before authentication; trusted unauthenticated requests return 401 and trust failures 403. All admitted requests speak for the operator Peer. Generic authenticated `/api/file?path=...` reads include files outside workspaces without directory containment. **Never expose this default operator API to tenants.** Two cookies only prove cookie handling, not two principals or data isolation. [Authentication][connection]; [unrestricted file route][session-controller].

## Actual failed-once diagnostic and disposition

The coordinator separately admitted one no-model diagnostic on the exact prospective plan SHA256 `2398f73b1f1a919695e2c3e45d5eaf69d456bf171965a61dfae1046f8e96c4a0`: pinned Node 26.7.0, installed rc1/Cordis 4.0.4 and cached `node:22-slim` image digest `sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c`. The proposed wrapper used a fresh owned A root, seven scoped mounts, clear environment, non-root/read-only/resource limits and `--network none`; actual inner mount/resource inspection was not reached. Historical `ctx_c6c545d20063` labels identified lab assets only; actual task/dispatch ownership was `task_0a936d713c67` / `ctx_a979a9a2c022`. A/B labels are not authenticated tenant principals. [Exact admission](../../.genie/wishes/open-intelligence-observatory/readiness/group-3-native-zero-model-diagnostic-1.json).

The historical command is preserved as **evidence data, not a runnable integration or permission to retry**, in the [actual checkpoint](../../.genie/wishes/open-intelligence-observatory/verification/group-3-actual-zero-model-diagnostic-1-checkpoint.json). It exited **1 after 2.17 seconds**, with primary `docker-startup / DOCKER_EXIT_BEFORE_METADATA`, code null, and one `docker-stderr / ABI_LOAD_FAILED` classification covering a consumed 122-byte line. Raw error text was not retained. The precise missing or incompatible library remains **unknown**; public Node ELF dependencies do not prove the cached image's library inventory. No unchanged rerun, guessed library fix, installation or third prospective repair occurred.

Native metadata, catalog, inner confinement inspection, cited answer, tool call, cancellation, reconnect and restricted-principal observations remain null. No model/provider call occurred. Model spend for this diagnostic was USD 0; coding/storage/all-cost totals remain unknown. The user's USD 20 sandbox ceiling reserves USD 12 for DSH and USD 8 for Brain, but does not supply current tariffs, enforceable input/dispatch/retry/ancillary usage limits or paid-call admission. A guided provider choice and fresh-key locator, including BWS, are not proof of usable credentials or authority to read secret values; none were read here.

The runner reported owned container removal with no secondary cleanup failure; a separate exact-name listing was empty. [Independent outcome review](../../.genie/wishes/open-intelligence-observatory/verification/group-3-actual-zero-model-diagnostic-outcome-review-1.txt), SHA256 `636bf654d74eb36c4635d11b3250fe8d34c24b751c28312245094e8eb29d2219`, returned **qualified SHIP for diagnostic attribution/custody only**. Full staged-bootstrap S1–S4 and original runtime acceptance remain BLOCKED. Process/container exit cannot attest whole-native disposal: the pinned launcher uses indistinguishable force-exit branches, and no supported independent global-completion receipt was qualified. See [Cordis lifecycle limits](cordis.md).

After explicit disposition, the coordinator preserved only the safe [classified metadata](../../.genie/wishes/open-intelligence-observatory/verification/group-3-failed-once-classified-metadata.json), SHA256 `7a830a2aae61a3a74b0b9c0815f388fecc220a4a482c3d37123f383babf9f7ed`. The author removed its throwaway `policy.mjs`/`probe.mjs` and exact nonsymlink owned A root without enumerating or copying private native state; B was never created. The two temporary root ignore rules were removed only after state absence, restoring all original ignore bytes. No probe code or private runtime state is retained as an application integration. The disposition record's earlier document HOLD describes its historical checkpoint; [the later serialized release](../../.genie/wishes/open-intelligence-observatory/readiness/group-3-actual-failed-diagnostic-serialized-docs-release.json) authorized this documentation update, not runtime execution.

## Required live proof and unblock requirements

| Original issue criterion | Current disposition | Required direct proof |
|---|---|---|
| A cited answer references the same entity IDs and evidence cutoff as the supplied scene | BLOCKED; live answer/tool/citation observation null | On the approved pinned Web runtime, create one fixture Session, follow with `assistantStream:true`, prompt with Scene-bound tool scope; observe actual chunks, `tool/call`/`tool/result`, final answer and exact entity/cutoff/revision/span citations; reject post-cutoff or foreign evidence |
| Cancellation stops new work; reconnect preserves the session and returns a clear status | BLOCKED; live cancellation/reconnect observation null | Cancel during active model/tool work with another item queued; assert no later model/tool/queued execution and terminal/status settlement; physically reconnect, compare Session ID, durable cursor/history and new ready/status baseline; exercise cold read on approved persistent storage |
| Two isolated sessions cannot access each other's restricted records or tools | BLOCKED; restricted principals/fixture/denial observation null | Independent principals A/B, each with unique restricted records/tool capability; attempted foreign Session/history/tool/record/attachment requests denied by server before execution, both directions, including direct IDs and after reconnect; own authorized reads still work |
| Verdict names validated constraints and remaining blockers; probe code is labeled throwaway unless separately accepted | Qualification disclosure reviewed; original acceptance unclosed | Historical and failed-once records preserve exact tuple, SDK/operator/queue/global-completion constraints, null live proof and unblock requirements; diagnostic attribution/custody SHIP is not original runtime SHIP; throwaway code was removed after evidence transfer |

Remaining requirements: a compatible, directly qualified isolated runtime and complete dependency/installed-to-source attestation; approved profile/patch and persistent Session artifacts; usable fresh product credentials with current provider/model compatibility and enforceable paid-use counters under the reserved ceiling; an authenticated principal issuer and two restricted record/tool fixtures; an all-transport server-enforced principal boundary; source/fixture retention rights; lifecycle permission and an observable completion route; durable stopped-admission state that survives reconnect/cold read. Product Brain authority and persistence proof remain owned by #5/#7, not replaced by a local store. No secret values belong in receipts. The admitted failed-once sandbox route and user budget are real, but fill none of the missing live acceptance observations.

Groups #7/#9/#10 may use the pinned contracts and preserved historical snapshots to locate APIs and blockers; these are not accepted DSH runtime/tenancy prerequisites. The four earlier safe commands are bound only to historical `receipts.json`; the later diagnostic failed, and its removed source paths are not runnable instructions. No issue closure, CI, deployed acceptance, native global completion or multi-user support follows from component smoke, qualified diagnostic review or repository aggregate success. The coordinator owns the current integrated aggregate checkpoint and original acceptance review.

## Engineering rulings

All attributed to `issue-4-engineer`:

- **Ruling: pin installed rc1 plus Cordis 4.0.4, separately from upstream source attestation** — real local bytes can be exercised without an unauthorized upgrade — cost if wrong: stale release or dependency drift blocks adoption until the complete tuple is requalified.
- **Ruling: select the supported Web/API path for future full qualification, not SDK-only or a wrapper** — SDK lacks required streaming/cancel/reconnect capabilities — cost if wrong: a future supported SDK extension requires a new pinned comparison, not a silent cutover.
- **Ruling: refuse operator Web as tenant authorization and require server-enforced principal boundaries** — one Peer and unrestricted file access cannot prove isolation — cost if wrong: tenant integration waits for a reviewed supported boundary rather than risking private data/tool exposure.
- **Ruling: do not equate keepInbox cancellation with stop-new-work** — pinned cancellation retains queued inputs — cost if wrong: the application stop/admission contract needs explicit qualification before #4 can pass.
- **Ruling: retain unknown approvals, live observations and persistence as null, and report BLOCKED** — the real sandbox/budget authorization and failed-once receipt do not supply the missing supported runtime, principal or paid-use gates — cost if wrong: dependent groups cannot proceed on an unsupported acceptance claim.
- **Ruling: require the exact supported HTTP 303 launch-token exchange, preserving all other guards** — pinned public Connection writes 303, not 302; final repair was independently closed statically — cost if wrong: metadata exchange fails before acceptance, without broadening admitted statuses.
- **Ruling: stop after the actual classified startup failure and preserve the cause as unknown** — one ABI category is not a library-inventory diagnosis; prospective repair budget remains 2/2, configuration-sourced, with zero effort escalations — cost if wrong: a future compatible route needs new evidence and explicit authority, not a silent retry.
- **Ruling: dispose only owned throwaway code/private custody after safe classified transfer** — failed diagnostic code is not accepted integration, and native state must not enter reports — cost if wrong: qualification must restart from separately admitted exact artifacts, never retained operator secrets.

[architecture]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/architecture.md
[sdk-client]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/sdk/client/README.md
[sdk-protocol]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/sdk/protocol/README.md
[web-app]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/bundle/web-app/README.md
[webserver]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/host/webserver/README.md
[connection]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/client/connection/README.md
[gateway]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/api-gateway.md
[session-controller]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/api/session-controller/README.md
[session-types]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/api/session-controller/src/types.ts
[session-commands]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/api/session-controller/src/commands.ts
[tools]: https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/core/tools/README.md
