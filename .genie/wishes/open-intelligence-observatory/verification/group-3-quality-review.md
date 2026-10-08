# Separate independent QUALITY review — original issue #4 qualification artifacts

Reviewer: `term_72422861-62f8-405e-ae4c-a6b7433e4a94`; Task `task_1d21619755a7`; Dispatch `ctx_9b40871b57d6`.
Time: 2026-10-08T07:10:41.172365+00:00

## Verdict and independence

**QUALITY: SHIP for the exact reachable documentary qualification artifacts. Original #4: BLOCKED unchanged.** No confirmed actionable HIGH/CRITICAL artifact finding; no bounded source repair requested. This is a separate quality review, not repeated live acceptance or promotion of the original Task/card/DAG; no downstream #7/#9/#10 runtime/composition support follows. Original criteria 1–3 remain BLOCKED; criterion 4 has the prior documentary-only acceptance verdict. Original #3/#5 runtime/release gates are not assessed or promoted.

Disclosure: I authored the prior independent acceptance report `/tmp/issue4-qualification-acceptance-ctx_10422c4b80d0.md` and therefore have prior artifact familiarity, not blind second-review independence. I remain independent of `issue-4-engineer`, the artifact author, and authored no production source. The coordinator explicitly reused me for this separate quality Task. Quality triggers stated before reread: silently widened trust/authority, wrong callable/request/lifecycle contract, fabricated installed/source/licence equivalence or misleading smoke would be FIX-FIRST; unavailable authorized runtime remains BLOCKED; truthful bounded artifacts with fresh safe execution and no such defects are documentary SHIP.

Only read-only repository/package/network operations and frozen safe zero-product-write scenarios were performed. No Git/index/commit/push/card/GitHub mutations, credentials/private cookies/product memory, model/provider calls, spending, namespace/home/profile creation, product service changes, deployment or snapshot redistribution. This local report is the only new artifact, outside the repository. No source paths owned or modified.

## Exact reviewed identity

Fresh command `sha256sum docs/integrations/dsh.md docs/integrations/cordis.md integrations/dsh/qualification/receipts.json .genie/wishes/open-intelligence-observatory/readiness/group-3.json`, exit 0:

| Path | SHA256 |
|---|---|
| docs/integrations/dsh.md | ec056adff560dddea4bd0345743015904d2f438e8f2352542a4304967ee6008c |
| docs/integrations/cordis.md | ce9178160755193ae6359d2314c2c56718aaa1026b82702d0b7642047af2dfa6 |
| integrations/dsh/qualification/receipts.json | 434a289eef95b6875a4062347b5194b96adc8f9f5077733c6dc5d82cf692abdb |
| .genie/wishes/open-intelligence-observatory/readiness/group-3.json | cf14ff13bdabae4eb06b79bc550eaec1eda547bfbec49742a47ac27eb7b6c868 |

All four match this Dispatch's pins. Source checkpoint `bb73b063957f2b6ccf0b0311e1770730faa8e2c0` is coordinator-supplied, not independently re-resolved through Git. Artifact verdict invalidates on content-digest change. Full candidate files were reread in raw ranges (all 123 DSH lines, 54 Cordis lines, 185 receipt lines), along with full frozen readiness and WISH governing scope, group criteria, trust, composition and validation sections before final smoke.

## Quality assessment and evidence

| Area | Finding / disposition | Attributed primary evidence |
|---|---|---|
| Security / source authority | Verified-safe documentation: source/quotes/tool results never authorize actions; principal binding required before dispatch and tool reads; no running tools currently authorized; shell/config/filesystem/private memory/spending/publication excluded | dsh.md:80–88,99–101; receipts.json:148–176 |
| Operator-versus-tenant boundary | Correctly refuses one-operator Web as a tenant surface; cookies, Session IDs and Cordis isolate are not principals; broad file endpoint and public transport limits explicit | dsh.md:19–25,86–88; installed Connection README:39–47; installed Session Controller README:81; Cordis context.d.ts:71–83 |
| SDK boundary | Correctly labels source-only client, all-runtime notification visibility/client filtering, enqueue-versus-execution distinction, no per-session cancel/reconnect/history/token-delta API, no negotiated compatibility | dsh.md:27–51; same-revision SDK protocol primary reference linked below; installed SDK identity honestly null in receipts.json:49 |
| Web callable / JSON contract | Correct RemoteResult/RemoteStreamHandle envelopes and signal positions; prompt requestId/sessionId/mode/content; typed cancel/updateQueue/follow/page/projections/control; list named body really uses `_request`, not `request` | dsh.md:53–72; installed generated declaration:15–34; types.d.ts:261–289,318–400,443–545; generated JS descriptor:987–1011 |
| Cancellation / queue | Correctly states keepInbox retention, no atomic stop-and-clear transaction, and cancellation/reconnect/cold resume/storage are distinct unobserved gates | dsh.md:74–78,95; installed commands.js:397–477 (cancel:476 retains queue; remove targets one still-pending item); no live cancellation measured |
| Component lifecycle | plugin/inject startup and reverse idempotent effect cleanup match installed contracts; disposal awaited before replacement; update/restart/dependency removal/HMR/Remote withdrawal not passed off as observed | cordis.md:7–17,29,35–39; installed registry.d.ts:99–121; fiber.d.ts:145–199; installed fiber.ts:402–442 |
| Durable evidence ownership | External Map is explicitly synthetic, process-local and not Brain/restart proof; authoritative spans/revisions/claims belong to separately authorized durable authority, not plugin-owned transient state | cordis.md:31,35–39; receipts.json:118–123,138–140 |
| Provenance / upgrades | Installed executable/manifests/declarations pinned independently of upstream revision; full dependency closure, source-build equivalence, profile/patch tuple and serving revision remain null, upgrade invalidation and full requalification explicit | dsh.md:7–11,99; cordis.md:3,43; receipts.json:36–59 |
| Maintainability / simplicity | API contracts, runtime observations, prohibitions and unblock protocols are separate and internally consistent; no adapter/wrapper/alternate memory/permanent test/scaffold creates a new maintenance convention | dsh.md:90–111; cordis.md:21–45; receipts.json structured proof_boundary/live_acceptance/rulings |
| Useful portable probes | PATH/realpath/createRequire avoids embedding machine-home locations; launcher/Cordis hashes checked before package import; fixed fixture/cutoff and reverse/idempotent replacement asserts; anonymous body matches generated descriptor; unavailable socket or wrong status/errors fail rather than fabricate PASS | Complete frozen readiness commands:0–3; fresh outputs below; no credential/session body printed or persisted |

These findings describe the candidate documentation and public installed contracts; they are not a production security audit or demonstration of actual multitenancy. Documented operator authority is an explicit trust delegation, not a newly discovered exploit. No exploit tools, authenticated RPC or private file endpoint probes were run. No confirmed candidate HIGH/CRITICAL defects were found; no nonblocking style issue is padded into a repair requirement.

## Resolved reviewer-evidence correction: Cordis licence notice is present

**The prior acceptance report's line 60 statement that the installed Cordis directory lacks a standalone LICENSE was incorrect.** It came from treating a bounded glob result as an exhaustive directory inventory; it is rescinded by this quality review, not a candidate-artifact defect. This task reread the actual complete Cordis directory using `read`, then the actual installed `@deepseek-ai/cordis/LICENSE`: MIT text with `Copyright (c) 2021-present Shigma`, notice-preservation requirement and warranty disclaimer. The installed DSH LICENSE is MIT with `Copyright (c) 2026 DeepSeek`. Both manifests also declare MIT and reference the harness repository at apps/cli and vendor/cordis respectively. These observations resolve only the direct-package-notice uncertainty; they do not qualify every transitive licence, provenance or redistribution right. No source snapshot/redistribution approval or unsupported licence was invented. Parent should supersede the erroneous prior licence sentence with this explicit correction; prior documentary SHIP and original BLOCKED are unchanged.

## Primary installed hashes and limitations

Fresh `readlink -f` resolved the installed launcher; `sha256sum` over the following installed package-relative files exited 0. Machine-home prefix intentionally omitted in this report:

| Artifact | SHA256 |
|---|---|
| @deepseek-ai/dsh/package.json | 6c5d2b98ca97920fffe81eaff8455dfd1e97524c8b3a7a3b0cac4c960ebb363c |
| @deepseek-ai/dsh/lib/bin.js | 935e95d05f4dc70a8a013eea59da80028946b5c139e45c6351dcaf2810ca00a1 |
| @deepseek-ai/dsh/LICENSE | ebb4f09972aee8608be255debaf78451a68e95c290f55c240dec2ecfa16ea6be |
| @deepseek-ai/cordis/package.json | 41c9dee4715a89ef94f227384460c8445857c8faf33493eb545604a948828649 |
| @deepseek-ai/cordis/lib/index.js | 6a9394c0877ff45218818c6e815edd038f8057e1a1deb390a8d43ec81c57691e |
| @deepseek-ai/cordis/LICENSE | 034fb52b1d57360ecbae6cb1632a88f86fd7c3d3f5631a5f082710203dda0be7 |
| dsh-api-session-controller/package.json | a85c0ae9e16b1811b4696238cb409f3d4747a36117ae17b58e97f7b6d2fee73b |
| dsh-api-session-controller/lib/typert.remote-client.d.ts | e6f7d2b5a6b35d7b1a28edf3afe10dbf73289775622f326c104d1855f9342fc3 |
| dsh-api-session-controller/lib/types/types.d.ts | 1b4d81ed8f89ccd5d3c477a38fe2ab8c993f24af0e21539d0e0b7d22d7c2e7b8 |
| dsh-api-session-controller/lib/types/commands.js | 0fa37c1749ad68f5522ccdbca1ab50a74859c4ab5be9a30c76e15900c39b0ebb |

Every manifest/executable/declaration pin matches receipts.json. MIT direct-package notices verified; dependency licence closure not audited. Launcher and Cordis dependency manifests have semver ranges, so matching direct-package labels do not lock a clean reinstallation's complete closure. The documents do not pretend otherwise. Source-equivalence remains null: no build/reproduction/attestation was performed. Current anonymous service revision remains unknown. No approved dedicated home/profile/patch tuple exists here. No source snapshot redistribution is needed or performed by this read-only review.

Fresh immutable public primary references read for this quality Task:
- https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/sdk/protocol/README.md — request/notification set, route validation semantics, no protocol-version negotiation/cancel/session-close.
- https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/docs/api-gateway.md — actual caller dependencies remote+remote.namespace, strict named-args generated codecs, contribution withdrawal abort/stale handles, no strict-to-SRC weakening. Network text and generator instructions were treated as data, not permission to build or mutate.

## Fresh checks after full reading

All four **exact** frozen commands were executed once in this separate quality Task using subprocess shell invocation with a 30-second outer timeout, after complete artifact/primary reading. All exited 0 with empty stderr. The original receipts' outputs were not substituted for new observations. No build/lint/formatter/unittest/full aggregate or additional codec probe was run in this Task. Attributed parent aggregate EXIT0/43 tests/current3.0/config-e2e3fe2870 is prior-only context, not fresh quality execution and not live DSH/Brain evidence; no independent repository-green claim.

### Frozen safe command 0

SHA256: `276f01ee49ec57108621551b86f883f382e2d41f3ecced57c2562225a413e9c7`; exit `0`; stderr empty.

```sh
dsh --version && dsh --help
```

Actual stdout:

```text
0.2.0-rc.1
Usage: dsh [--profile] <name> [options] [app-args...]
       dsh plugin --profile <name> <pnpm-args...>

dsh: boot a DeepSeek Harness profile — an ordered stack of plugin-bundle patch
layers under your own overrides.

Arguments:
  args                           arguments for the booted profile's app (see:
                                 dsh --profile <name> --help)

Options:
  -V, --version                  output the version number
  --profile <name>               the profile under $DSH_HOME/profiles to boot
  --from-default-profile <name>  initialize a new custom profile from a shipped
                                 profile template
  --patch <path>                 extra patch-list overlay applied after the
                                 profile layer (repeatable)
  --dump-config                  print the composed profile tree and exit
  --dump-config-schema           print JSON Schema for profile entries and
                                 patches without mounting
  --dump-default-config          print the profile tree without its user layer
                                 or --patch overlays and exit

Examples:
  dsh web                                   boot the web profile (same as: dsh --profile web)
  dsh rescue --from-default-profile web
                                            create rescue from the shipped web template, then boot it
  dsh headless "run the tests"              answer one task, print the result, and exit
  dsh tui --patch ./extra.yml               boot a custom profile with one extra overlay
  dsh tui --resume <session>                arguments after the launcher flags reach the app
  dsh web --help                            the web app's own flags and help
  dsh plugin --profile tui add <package>    install a plugin into the tui profile

```

### Frozen safe command 1

SHA256: `146284f6c3bf798dbf60b49c0f1f7f77568c7f0378cf86ebb06c98f623970f3b`; exit `0`; stderr empty.

```sh
python3 -B tests/test_evidence_contracts.py --smoke tests/fixtures/evidence_contracts.json
```

Actual stdout:

```text
{
  "opposed_claims": [
    "claim:sustainable:1",
    "claim:unsustainable:1"
  ],
  "equity_transaction_parties": [
    [
      "transaction:one",
      "entity:investor-a"
    ],
    [
      "transaction:one",
      "entity:investor-b"
    ],
    [
      "transaction:two",
      "entity:investor-a"
    ]
  ],
  "source_revision_chain": [
    "source:a:1",
    "source:a:2"
  ],
  "evidence_cutoff": "2020-02-03T00:00:00Z",
  "method_version": "fixture-method/1",
  "later_correction_excluded": true,
  "fixture_sha256": "48b857151ad0899a130b9f9cc7096bc96fcd59c865883fb887048d93593885b5"
}
```

### Frozen safe command 2

SHA256: `baea3c532fd8dcdf40c335875de062e412fb9395df241bc3a417ea9634050eef`; exit `0`; stderr empty.

```sh
python3 -B -c "import json; import urllib.request; import urllib.error
results=[]
for method,path,data in [(\"GET\",\"/\",None),(\"POST\",\"/api/session/list\",b\"{\\\"args\\\":{\\\"_request\\\":{}}}\")]:
 req=urllib.request.Request(\"http://127.0.0.1:3080\"+path,data=data,method=method,headers={\"Content-Type\":\"application/json\"})
 try:
  with urllib.request.urlopen(req,timeout=5) as response:
   raise AssertionError(\"anonymous request admitted: \"+str(response.status))
 except urllib.error.HTTPError as error:
  assert error.code==401,(method,path,error.code)
  results.append({\"method\":method,\"path\":path,\"status\":error.code})
print(json.dumps({\"unauthenticated_fence\":results,\"tenantIsolationValidated\":False}))"
```

Actual stdout:

```text
{"unauthenticated_fence": [{"method": "GET", "path": "/", "status": 401}, {"method": "POST", "path": "/api/session/list", "status": 401}], "tenantIsolationValidated": false}
```

### Frozen safe command 3

SHA256: `0552cdeaf2848f0a349ff571f5c5e518847d5173769a7d656f94dceddece3511`; exit `0`; stderr empty.

```sh
node --input-type=module -e "import {execFileSync} from \"node:child_process\"; import {realpathSync,readFileSync} from \"node:fs\"; import {createRequire} from \"node:module\"; import {pathToFileURL} from \"node:url\"; import {createHash} from \"node:crypto\"; import assert from \"node:assert/strict\"; const bin=realpathSync(execFileSync(\"which\",[\"dsh\"],{encoding:\"utf8\"}).trim()); const require=createRequire(pathToFileURL(bin)); const entry=require.resolve(\"@deepseek-ai/cordis\"); const hash=p=>createHash(\"sha256\").update(readFileSync(p)).digest(\"hex\"); assert.equal(hash(bin),\"935e95d05f4dc70a8a013eea59da80028946b5c139e45c6351dcaf2810ca00a1\"); assert.equal(hash(entry),\"6a9394c0877ff45218818c6e815edd038f8057e1a1deb390a8d43ec81c57691e\"); const {Context}=await import(pathToFileURL(entry)); const root=new Context(); const retained=new Map([[\"fixture:accepted\",Object.freeze({value:null})]]); const accepted=retained.get(\"fixture:accepted\"); let activations=0; const cleanup=[]; function reader(ctx){activations++;assert.strictEqual(retained.get(\"fixture:accepted\"),accepted);ctx.effect(function*(){yield ()=>cleanup.push(1);yield ()=>cleanup.push(2);});} const first=root.plugin(reader);await first;await first.dispose();await first.dispose();assert.deepEqual(cleanup,[2,1]);const second=root.plugin(reader);await second;await second.dispose();assert.equal(activations,2);assert.deepEqual(cleanup,[2,1,2,1]);assert.strictEqual(retained.get(\"fixture:accepted\"),accepted);console.log(JSON.stringify({activations,cleanup,retainedFixtureUnchanged:true,durableEvidenceValidated:false,tenantIsolationValidated:false}));"
```

Actual stdout:

```text
{"activations":2,"cleanup":[2,1,2,1],"retainedFixtureUnchanged":true,"durableEvidenceValidated":false,"tenantIsolationValidated":false}
```

Check boundary: launcher help establishes flags/version only; fixture executable establishes synthetic records/cutoff only; anonymous401 establishes only anonymous rejection on an unattributed serving revision; real Cordis Context/plugin/effect/disposal establishes activation/reverse/idempotent cleanup/replacement only. The retained Map identity is deliberately not durable storage. CLI/help does not start an approved profile; no tenant/model/session runtime claim is made. No mock/native echo/source-text assertion was used as runtime proof. Existing fixture smoke uses real contract checks, not a new permanent test. Controlled negative/fault-injection execution was not added because this Dispatch permits the frozen scenarios only; no new red-run evidence is claimed.

## Remaining risks and bounded unblock requirements (original issue, not artifact repair)

- **HIGH runtime/evidence blocker**, dsh.md:94,99; receipts.json:134–135,149–155: no approved Scene-bound model/tool fixture or streaming citation result. Consumer risk if ignored: fabricated answer acceptance. Bounded next action: authorized worker qualifies exact dedicated runtime/provider/model/tools/Scene and records real citations/chunks/calls; never fill null with fixture output.
- **HIGH stop/lifecycle blocker**, dsh.md:76,95; receipts.json:136–138,156–157,163; installed commands.js:476: source retains pending work; no supported stop/admission queue policy or authorized reconnect/persistence scenario observed. Consumer risk if ignored: queued execution after user cancel and false recovery status. Bounded next action: qualify supported server-side admission/queue semantics and real active+queued cancel, carrier reconnect/cold resume/storage under approved lifecycle authority; no monkey patch/wrapper/SDK close substitute.
- **HIGH principal-boundary blocker**, dsh.md:86–88,96,99; receipts.json:139,158–161: one operator Peer plus broad file reads is not two-principal isolation. Consumer risk if ignored: foreign Session/history/tool/record/file exposure. Bounded next action: approved supported principal-bound enforcement and restricted A/B fixture with both-direction denial before execution, own reads preserved and reconnect retested; keep operator surface private.
- Provenance/closure/application durability remain unqualified, dsh.md:7–11,99–101 and cordis.md:31,37–43. Consumer risk if ignored: downstream composition/persistence promoted from direct-package/component smoke. Bounded next action: approved full tuple/reproduction or attestation, licence closure and real application/durable evidence qualification with #5/#7 ownership preserved.

No missing runtime authority can be repaired by fake results. No original acceptance/DAG/card state was changed. Native inbox checks ran at new-file/batch checkpoints and after smoke; no messages were pending at those checks, and a quality-task heartbeat was sent. Parent owns final orchestration bookkeeping, correction attribution and any future authorized worker repair/runtime qualification.
