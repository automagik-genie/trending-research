# Brain evidence qualification

**Verdict: BLOCKED for GitHub #5.** Contract qualification is reachable; live evidence persistence is not accepted. No approved product Brain authority, owner/principal, ingest rights, same-cluster connection, durable storage or isolated-restart authorization was supplied. These remain `null`, not inferred from the installed personal/operator runtime. No personal records were read, namespace created, evidence ingested, service restarted or model called.

Qualification version: **1.0.1**. Initial worker: `issue-5-engineer`; card `t_muz1j2ww5a6ec7c7`; group 4. Intake base: `3b3beb094d2c3a5a021ead88a5280140bd1f841e`; discovery baseline: `65fe46ef8fde709fa3993cea98b20392b50089d9`. [Frozen readiness](../../.genie/wishes/open-intelligence-observatory/readiness/group-4.json) and [repair supplement](../../.genie/wishes/open-intelligence-observatory/readiness/group-4-repair-1.json) authorize only documentary qualification/repair, not reduced acceptance or runtime mutation.

## Evidence identity and authority

- [Issue #5](https://github.com/namastex888/trending-research/issues/5) remains the complete acceptance contract; the [copied issue](../../.genie/wishes/open-intelligence-observatory/github-roadmap.json) and [Group 4](../../.genie/wishes/open-intelligence-observatory/WISH.md#group-4-5--qualify-brain-evidence-persistence-and-relationship-semantics) preserve it.
- Dependency #2 is accepted at `60975ca9c66efaa8f8284d37897c5e5d5f8a2f68`: [independent design SHIP](../../.genie/wishes/open-intelligence-observatory/verification/group-1-design-review.txt), [separate quality SHIP](../../.genie/wishes/open-intelligence-observatory/verification/group-1-quality-review.txt), and [coordinator-linked evidence](https://github.com/namastex888/trending-research/issues/2#issuecomment-6052666339). That accepts domain contracts, not Brain persistence.
- Installed manifest declares `@khal-os/brain`, version `0.0`, `compiled-customer-artifact`, `linux-x64`, `bun-linux-x64-baseline`, `contractSchemaVersion=1`, source commit `3ed4ce88f1b9ca70373eecd05f4ed292641e3f58`. This is declared artifact provenance, not independent binary-to-source attestation. A release-channel label is not the running version.
- [Native tool descriptors](../../integrations/brain/qualification/native-tools.json) are the exact ten relevant canonical descriptors from the shipped generated snapshot. Their input schema dialect is draft-07. **Not live `tools/list`**, authenticated server identity or permission proof. Generated descriptions calling an operation `silent-ok` confer no authorization here.
- [Qualification evidence](../../integrations/brain/qualification/evidence.json) binds inspected source hashes, actual safe observations, all four unchanged criteria, missing prerequisites and attributed rulings. Historical commands remain historical; the portable repair probe below is a new attributable execution, not recovery of the original author's archived invocation.

Shipped `lib/brain/plugins/hermes_brain/mcp_client.py` digest: `c7077b67661ff7970ffb9f77740281c43c0eb62986add262e1f9bb7b1b1608f1`; `config.py`: `df2bc0f155325ccde9a82ac84f7959ff24ef9234602e6e7fd877849575518c0d`; `mapping.py`: `940aea0ef5ff77cca422cde527cb2d179cb75c4cd42237adf7d28aa681f70ba4`. Primary contract sources are those shipped files, the installed manifest and the accepted local schema, not scout claims of live acceptance. Upstream product source is [khal/brain](https://git.namastex.io/khal/brain); reachability/authentication is not assumed.

### Native-tools snapshot attribution and upstream notice

The adjacent [ten-descriptor snapshot](../../integrations/brain/qualification/native-tools.json) is derived from the installed shipped `snapshot_tools()` descriptors, not authored native schemas and not a live server response. Declared upstream source identity: [khal/brain](https://git.namastex.io/khal/brain), commit `3ed4ce88f1b9ca70373eecd05f4ed292641e3f58`. Read-only `git show` of **that commit**, not the current checkout, verified `LICENSE` (SHA256 `f3bb4f51dbcd27e2acecc608d2627d87f47c0dcfaaa9f50798985fcafdc1a3ba`) and `package.json` (SHA256 `1bfbf356de818cc117c61c4195cca142699f5eef950cce9905fb9f60597efcdf`): package `@khal-os/brain`, source version `0.0.0`, author `Namastex Labs`, licence declaration `MIT`. This source version does not replace installed artifact version `0.0`.

The declared-commit file `plugins/hermes_brain/mcp_client.py` has SHA256 `c7077b67661ff7970ffb9f77740281c43c0eb62986add262e1f9bb7b1b1608f1`, identical to the inspected installed module. The repair probe compares all ten copied descriptors' complete names, descriptions and schemas against that module's actual `snapshot_tools()` output. This establishes correspondence for **this Python module and these descriptor data only**, not the whole compiled runtime/build. Compiled binary-to-source equivalence and an installed-artifact licence/owner attestation remain **null/unverified**; the manifest makes no licence claim.

Redistribution basis recorded here is the observed declared-source MIT grant and the verified descriptor-source correspondence, with its full copyright, permission and disclaimer notice carried below beside the snapshot link. It is not a legal determination about descriptor copyrightability, unrelated package assets or compiled artifact licensing; any broader redistribution requires actual applicable rights/owner confirmation. The repository root `LICENSE` is unchanged and is not substituted for this upstream notice.

```text
MIT License

Copyright (c) 2026 automagik

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Namespace and transport boundary

The shipped client requires a configured `brain_id` matching `^brn_[a-z0-9_]+$`. Missing or malformed authority rejects. `BrainMcpClient.scoped_arguments(arguments, *, tool="")` overwrites a caller-supplied `brain_id` with the configured authority. Product callers must select that authority outside model/source arguments, never silently use nearest project config, an active personal Brain or inherited session.

This is **client-side pinning**, not server RLS. An advertised capability cannot prove cross-authority denial. A real owner must supply the actual product authority, authenticated principal, allowed operations, denied test principal/authority and attributable grant receipt. No proposed `brn_` string in a synthetic smoke is that authority.

Shipped stdio transport uses native `brain-mcp`, newline-delimited JSON-RPC, protocol `2026-07-28`: `initialize` → `notifications/initialized` → `tools/list` → `tools/call`. Real caller shape: `BrainMcpClient.call(tool: str, arguments: Optional[Dict[str, Any]] = None, *, timeout_ms: Optional[int] = None) -> BrainToolResponse`. These calls were **not** made against a product namespace.

`build_child_env` pins the explicit authority, clears foreign inherited session correlation when no session is assigned, filters unrelated secrets and retains required PostgreSQL/libpq routing variables. Retaining the cluster variable in a synthetic dictionary does not establish the actual server cluster or storage. An independently hosted Streamable HTTP MCP endpoint requires HTTPS except loopback and has its own authentication/session handling. A health URL is not an MCP URL; shipped documentation disagrees about serve exposing `/mcp`, so do not guess that route.

## Relevant supported tool contracts

Every future product call must explicitly carry the approved `brain_id`; the raw tools make it optional. Full required/optional fields and constraints are retained in the descriptor artifact, rather than a second handwritten schema.

| Canonical tool | Required inputs | Qualification boundary |
|---|---|---|
| `brain_remember` | `content` | Native core-memory ingest; use `scope="global"`, `veracity="imported"`, `extract=false`, `extract_entities=false` for source records. Metadata is free-form, not an immutable-span guarantee. |
| `memory_recall` | `query` | Cited native recall. Inspect results, citations, confidence and trace together; empty/irrelevant recall cannot certify retrieval. |
| `brain_get` | `memory_id` | Exact memory read; not a document getter or a citation envelope. |
| `brain_update` | `memory_id` | Mutable memory update supports `expected_revision`, `operation_key`, `actor`, `reason`. Do not update accepted canonical source/claim bytes in place. |
| `knowledge_search` | `query` | Document/chunk search with file/heading citations and coverage verdict; not proof of exact application byte selectors. |
| `brain_fact_assert` | `subject`, `predicate`, `object` | `supersede` defaults **true**. Pass **false** explicitly for simultaneous assertions/investors. `source` and `metadata` preserve references, not verified truth. |
| `brain_fact_query` | None | Scoped filters and date-only `as_of`; not a knowledge-time/revision replay query. |
| `brain_fact_end` | `subject`, `predicate` | Omitting `object` can end every matching relationship. Not an automatic correction operation. |
| `brain_graph_link` | `source_id`, `target_id`, `relationship` | Endpoints are Brain KG **documents**, not application entities or transactions. Weight is not financial magnitude or truth probability. |
| `brain_graph_query` | `seed_id` | Document traversal; preserves document provenance only. |

Shipped `mapping.py` expects aligned `results[]` and `citations[]`, `confidence`, `trace_id`, `query`, `total_results`, `latency_ms`. Its `brain-memory://<brain_id>/khs_memory/<memory_id>` URI identifies a memory row, not a source revision/span. Recall confidence must not replace the domain's independent coverage, verification, freshness and independence dimensions. Native fact citations likewise do not on their own select exact source bytes.

## Entity, claim and transaction mapping

This is a **required integration contract**, not a shipped adapter. Its consumers must qualify the unresolved persistence extension before adoption. Authoritative application fields remain [evidence contract 1.0.0](../contracts/evidence.md) / `urn:open-intelligence:evidence:1.0.0`.

| Application record | Required durable representation in approved Brain authority | Query use / prohibited inference |
|---|---|---|
| `Entity` | Preserve canonical record bytes and stable `id`, kind, name and provenance-scoped aliases. | Entity/alias lookup is rebuildable. Similar document names do not establish entity equality. |
| `SourceRevision` | One immutable record per `id`: exact retained UTF-8 text, content digest, source/origin, explicit revision ancestry, rights/disposition and all source clocks. | A replacement document never redirects an old source ID. Erasure obligations can make replay unavailable. |
| `EvidenceSpan` | Preserve canonical `id`, `source_revision_id`, byte `selector.start/end`, kind and quote. | Resolve the exact retained source revision, verify SHA256 and byte-slice/quote equality; a heading or latest file citation is insufficient. |
| `Claim` | Preserve canonical `id`, reporters, entity IDs, spans, proposition, status, event validity, ingestion and explicit `revision_of`. | Opposing reporters remain independent records, not a subject/predicate latest-wins slot. |
| `EconomicRelationship` | Preserve relationship ID, transaction ID, both parties, kind/status/reporting party, nullable money/currency, periods/clocks, spans and explicit ancestry. | All investors and repeated transactions survive. Equity/debt/cloud credits/commitments/revenue remain distinct. |

A durable integration binding must retain `(brain_id, application_record_id, collection, canonical_sha256, native_memory_id)` and the original canonical bytes; this describes required data, **not a supported native schema or an invented callable**. Domain IDs stay globally unique and are not replaced by native row/doc IDs. Native `source`/`metadata` may carry these references after qualification; free-form metadata does not enforce uniqueness, hash agreement, append-only writes or legal retention.

For rebuildable reference facts, `subject` can be the stable claim/transaction ID, `predicate` an explicit relationship such as `reported_claim`/`has_investor`, and `object` a stable claim/entity ID. Every assertion passes `supersede:false` and carries the originating canonical record/span reference. The full relationship remains authoritative in its canonical record: a convenience triple cannot encode or verify money, period, transaction identity, attribution and precision by itself. Unknown event dates must not be projected into a fact-validity date.

**Document edges are never verified economic transactions.** An entity relationship view may admit only a typed `EconomicRelationship` with resolvable source spans and explicit reporting/status fields. A document graph link, arbitrary relationship label, high weight, model-generated extraction or circular funding path cannot certify an entity transaction, cash movement, recognized revenue or wrongdoing.

## Durable authority versus rebuildable projections

Accepted observations, source revisions/spans, claims, economic relationships, source tombstones, exact manifest inputs, assessments and publication history belong to the qualified durable Brain authority. No sidecar SQLite/JSON semantic memory, agent cache or plugin closure becomes a second authority. Qualification JSON files here contain contract/verification receipts, **not accepted economic evidence**.

Entity/alias indexes, document adjacency, claim-to-span indexes, typed economic views, text/vector rankings, lens selections and cutoff query results are rebuildable from explicit retained records and a pinned manifest/method. Cache keys must include authority, manifest/input digest, cutoff and method. Removing/replacing a plugin may discard those projections, never the accepted records or publication ancestry. Group #7 owns actual read-model reconstruction and Cordis replacement/rebuild-equality probes; this slice does not invent a durable service or claim that probe passed.

Required extensions and ownership:

1. **Issue #5 integration gate:** qualify immutable application-ID binding, unequal-byte conflict rejection, exact revision/span retention, idempotent reimport and cited read-back. Existing remember/update metadata is insufficient evidence. If native facilities cannot enforce these, coordinator freezes an actual Brain-owned storage extension with supported APIs before any implementation; no unowned side database.
2. **Issue #5 + #7:** preserve original canonical bytes across languages, exact UTF-8 selectors, rights-aware erasure/tombstone disposition and export/read-back. Native numeric row identity or content deduplication must not collapse distinct application records.
3. **Issue #7 + #13:** qualify rebuild equality, plugin-independent persistence, pinned methods and offline manifest replay. Date-only native fact queries are not the replay source.
4. **Product Brain owner + coordinator:** approve authority/principal/grants, real same-cluster transport, durable backing store and isolated restart. Capability metadata, source inspection and a healthy operator service cannot grant this authority.

## Time semantics and replay limits

Native shipped fact schemas accept empty strings or `YYYY-MM-DD` for `valid_from`, `valid_until`, `as_of`; they do not accept RFC3339 instants or a transaction-time cutoff. The shape regex alone is not calendar validation. Native `supersede:true` is single-valued semantics; concurrent reports/investors require explicit `false`.

Supporting reachable native source `src/lib/brain-memory/triples.ts` (SHA256 `288b6b2d458a2052f1b11870e13fbcb757026a806c53daac06dfe9bcfa4854e9`, not attested to installed bytes) uses half-open date validity, null end as still open, omitted start as database `CURRENT_DATE`, and omitted end date as today for ending a fact. Default supersession closes open facts sharing subject/predicate case-insensitively, irrespective of their objects. Backdated supersession can alter validity history. These are source observations, not exercised live semantics.

Domain null endpoints mean **unknown**, not open infinity. Preserve the five independent clocks and original date wording in canonical evidence. Never convert a source date to invented midnight, use the database default date as the economic event date, infer publication from ingestion, or treat memory `created_at`/`updated_at` as application knowledge-time history. Unknown event dates require leaving the authoritative instant/boundary null and withholding a fact projection that would imply a date.

Native memory revision fields/optimistic revision checks do not establish bitemporal replay. No inspected fact query exposes both valid-time and knowledge-time selection; date-only `as_of` cannot reconstruct what the application knew at an instant. **Native bitemporal replay: unavailable/unqualified.** A domain `known_at_cutoff` manifest can define exact accepted inputs, but replay also needs legally retained bytes, the qualified durable layer and the pinned executable method. It is not exhaustive public historical truth; entity/alias knowledge-history remains limited in v1.

## Required live acceptance protocol — blocked, not executed

Before any live call, the owner must supply an actual approved product `brn_` authority, owner/principal/grants and denied principal, live tool identity/schema digest, same-cluster routing, authorized fixture bytes/rights, durable storage identity, and isolated-restart target/executor/receipt. Paid extraction/embedding/model routes require an attributed budget; otherwise keep them disabled. A synthetic namespace, health receipt or local fixture cannot substitute.

1. Obtain the supported MCP handshake and live `tools/list`; pin its exact server/runtime/schema identity. Verify the selected product authority and server-side denial of unauthorized authority/records using restricted principals. No implicit active/personal authority lookup.
2. Ingest authorized canonical source, span and claim records through `brain_remember`, explicit product authority, `scope:"global"`, `veracity:"imported"`, extraction disabled, approved idempotency/actor/reason. Read each returned `memory_id` through `brain_get`. Require equality of original canonical bytes, domain IDs and source digest; identical reimport must not duplicate, unequal bytes at an existing application ID must reject. Native result IDs/revisions come from real receipts, never fixture guesses.
3. `memory_recall` and `knowledge_search` must return the target with a citation and trace; resolve the cited native row/document to the exact application source revision/span. Independently verify UTF-8 boundaries, quote and digest. Empty results, wrong revision, a heading-only citation, unresolved reference or digest mismatch fail.
4. Ingest both conflicting claims without supersession and both investor references using `brain_fact_assert(..., supersede:false)`, explicit authority and per-record provenance. Retain repeated transactions under distinct IDs. Query with `brain_fact_query`; inspect all original IDs/sources, not merely a count. Append a correction as a new canonical record, not a `brain_update` of accepted evidence. Exercise mutable disposable fixture update with real `expected_revision`/operation key separately; stale revision must reject and original immutable evidence must survive.
5. Restart **only the explicitly isolated authorized target** via its approved executor/protocol (currently null); reconnect and read the same claim, span, source bytes/digest, concurrent claims/investors, revisions and native bindings. Persistence acceptance fails if any reference, record or original byte is lost, redirected or silently replaced. A plugin/client restart is not a storage restart.
6. Record actual date-validity boundary/supersession behavior and time/replay limits, and prove document graph links are not emitted as verified transactions. Preserve all direct receipts and seek independent acceptance plus quality review; do not close #5 based on CI or worker notification.

These are supported call shapes and required observations, not authorization, an executable mock, fake receipts or a fabricated restart command. Exact live argument values/fixtures and restart command require a new readiness freeze when real prerequisites exist.

## Safe local verification

Initial qualification receipts are **historical**, including the mid-wave 42-test aggregate against its recorded shared-file hashes/config `aabd43c46f`; they are not current-checkpoint or repair validation. Historical health reported `selected_brain_readiness:"not_checked"` and was not refreshed in this repair. The following original commands are retained for attribution, **not a repair runbook**; in particular this repair prohibits network/health requests and defers the shared suite to the coordinator.

```sh
brain --version --capabilities
curl --max-time 5 --fail-with-body -sS http://127.0.0.1:3847/healthz
python3 -B tests/test_evidence_contracts.py --smoke tests/fixtures/evidence_contracts.json
python3 -B -m unittest discover -s tests -p test_evidence_contracts.py
python3 -m unittest discover tests && python3 eval.py --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json
```

### Portable zero-write shipped-function probe

Run from the repository root. The exact command is also stored in `evidence.json` under `repair.public_probe.command`; its SHA256 covers UTF-8 command text including the final newline. Default discovery uses the OS account home plus `.brain`, **not** inherited `HOME`, `BRAIN_HOME`, active Brain configuration or personal records. For a different installation, insert an absolute installation-root argument after the final `-` on the first line (before `<<'PY'`); the same module digests remain mandatory. An absent install, digest drift, unexpected read, process/network/write attempt or failed assertion exits nonzero.

Python `-I -B` ignores Python environment configuration and disables bytecode writes. Before importing probe dependencies or shipped modules, the child replaces its Python environment mapping with synthetic values only; it never enumerates or reads inherited secrets. An audit hook denies process/network and filesystem mutation events and restricts file reads to stdlib code, the two shipped module files and the descriptor artifact. Guard rejection checks dispatch audit events only, not actual forbidden operations. Verified module bytes execute directly in a synthetic package, bypassing the real package initializer/provider. No `start`, `call`, MCP handshake, tool invocation, namespace lookup or clock measurement occurs.

```sh
python3 -B -I - <<'PY'
import os, sys
os.environ = {"HOME": "/nonexistent/qualification", "BRAIN_HOME": "/nonexistent/qualification"}
import hashlib, importlib.util, json, pwd, sysconfig, types
from pathlib import Path

if len(sys.argv) > 2:
    raise SystemExit("usage: python3 -B -I - [absolute-install-root]")
root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(pwd.getpwuid(os.getuid()).pw_dir) / ".brain"
if not root.is_absolute():
    raise SystemExit("installation root must be absolute")
lib = root / "lib/brain/plugins/hermes_brain"
expected = {
    "config": "df2bc0f155325ccde9a82ac84f7959ff24ef9234602e6e7fd877849575518c0d",
    "mcp_client": "c7077b67661ff7970ffb9f77740281c43c0eb62986add262e1f9bb7b1b1608f1",
}
artifact_path = Path("integrations/brain/qualification/native-tools.json").resolve()
allowed = {artifact_path, *(lib / (name + ".py") for name in expected)}
allowed = {path.resolve() for path in allowed}
stdlib = Path(sysconfig.get_path("stdlib")).resolve()
write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
mutations = {
    "os.system", "os.fork", "os.forkpty", "os.posix_spawn", "os.kill", "os.killpg",
    "os.putenv", "os.unsetenv", "os.remove", "os.rename", "os.rmdir", "os.mkdir",
    "os.chmod", "os.chown", "os.utime", "os.link", "os.symlink", "os.truncate",
    "shutil.copyfile", "shutil.copymode", "shutil.copystat", "shutil.rmtree",
}
def safety(event, args):
    if event in mutations or event.startswith(("subprocess.", "socket.", "urllib.", "os.exec", "os.spawn")):
        raise PermissionError("probe guard: " + event)
    if event == "open":
        if len(args) != 3 or not isinstance(args[2], int) or args[2] & write_flags:
            raise PermissionError("probe guard: write or unknown open flags")
        path = Path(os.fsdecode(args[0])).resolve() if isinstance(args[0], (str, bytes, os.PathLike)) else None
        if path is None or (path not in allowed and not (path.is_relative_to(stdlib) and path.suffix in {".py", ".pyc", ".so"})):
            raise PermissionError("probe guard: unexpected file read")
sys.addaudithook(safety)
guards = {}
for label, event, args in [
    ("process_rejected", "subprocess.Popen", ()),
    ("network_rejected", "socket.connect", ()),
    ("write_rejected", "open", (str(artifact_path), "w", os.O_WRONLY)),
    ("unknown_open_flags_rejected", "open", (str(artifact_path), "r", None)),
    ("private_file_read_rejected", "open", ("/nonexistent/private-env", "r", os.O_RDONLY)),
    ("filesystem_mutation_rejected", "os.remove", ("/nonexistent/qualification",)),
]:
    try:
        sys.audit(event, *args)
    except PermissionError:
        guards[label] = True
    else:
        raise AssertionError(label)

package = types.ModuleType("_qualification_brain")
package.__path__ = [str(lib)]
sys.modules[package.__name__] = package
modules = {}
for name, digest in expected.items():
    path = lib / (name + ".py")
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != digest:
        raise SystemExit("installed module digest drift: " + name)
    spec = importlib.util.spec_from_file_location(package.__name__ + "." + name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    exec(compile(source, str(path), "exec"), mod.__dict__)
    modules[name] = mod
config, client = modules["config"], modules["mcp_client"]
observed = {}
for label, raw, message in [
    ("missing_authority_rejected", {}, "brain_id is required"),
    ("malformed_authority_rejected", {"brain_id": "not-a-brain"}, "brain_id must look like"),
    ("remote_plain_http_rejected", {"brain_id": "brn_repair_fixture", "endpoint": "http://example.invalid/mcp"}, "must use HTTPS"),
]:
    try:
        config.parse_config(raw)
    except config.BrainConfigError as exc:
        if message not in str(exc):
            raise
        observed[label] = True
    else:
        raise AssertionError(label)
validated = config.parse_config({"brain_id": "brn_repair_fixture", "command": "/nonexistent/qualification/brain-mcp"})
instance = client.BrainMcpClient(validated)
scoped = instance.scoped_arguments({"brain_id": "brn_foreign_fixture", "query": "synthetic"}, tool="memory_recall")
assert scoped["brain_id"] == "brn_repair_fixture"
observed["authority_override_denied_client_side"] = True
child = client.build_child_env("brn_repair_fixture", base={
    "HOME": "/nonexistent/qualification", "BRAIN_HOME": "/nonexistent/qualification",
    "BRAIN_KHORTEX_SESSION": "foreign-synthetic", "PGHOST": "synthetic-cluster.invalid",
    "UNRELATED_SECRET": "synthetic-not-secret",
})
assert "BRAIN_KHORTEX_SESSION" not in child
assert child["PGHOST"] == "synthetic-cluster.invalid"
assert "UNRELATED_SECRET" not in child
observed.update(foreign_session_removed=True, same_cluster_variable_retained=True, unrelated_secret_removed=True)
assert instance._channel is None
observed.update(mcp_started=False, records_read=False)
artifact = json.loads(artifact_path.read_text())
names = {"knowledge_search", "brain_remember", "memory_recall", "brain_get", "brain_update", "brain_fact_assert", "brain_fact_end", "brain_fact_query", "brain_graph_link", "brain_graph_query"}
assert len(artifact["tools"]) == 10 and {tool["name"] for tool in artifact["tools"]} == names
shipped = {tool["name"]: tool for tool in client.snapshot_tools()}
for descriptor in artifact["tools"]:
    assert descriptor == shipped[descriptor["name"]], descriptor["name"]
print(json.dumps({
    "audit_guards": guards, "component_observations": observed,
    "descriptor_provenance": {"exact_shipped_descriptors": 10, "live_tools_list": False},
    "proof_boundary": "shipped pure functions and descriptor provenance only; no RLS, ingest, model, storage or restart proof",
}, indent=2))
PY
```

The new repair receipt records the exact command's exit/output after the complete slice. The independent reviewer's earlier full-component script is independent evidence, not the recovered author command. Neither run qualifies server RLS, real credentials, native live schemas, durable evidence or restart; all live prerequisites remain null.

## Acceptance disposition

| Original criterion | Disposition / required evidence |
|---|---|
| A claim links back to its exact evidence span after restart. | **BLOCKED:** authorized ingest, exact cited read-back and isolated durable restart unavailable; live result null. |
| Conflicting reports and multiple investors survive ingest and update. | **BLOCKED:** shipped `supersede:false` contract and local domain examples are not native ingest/update receipts; live result null. |
| Document graph relationships are not presented as verified entity transactions. | Documented and source-qualified boundary; no application adapter/view emitted here. Product runtime enforcement remains unqualified, not a UI pass. |
| Supported time semantics and any unavailable bitemporal replay are documented. | Shipped date-only shapes and supporting native-source semantics documented; native live behavior unqualified and bitemporal replay explicitly unavailable. |

## Attributed engineering rulings

Every engineering decision is attributed in the [evidence record](../../integrations/brain/qualification/evidence.json), with rationale and cost if wrong. The decisions are: fail closed on missing authority; preserve exact shipped descriptors without calling them live; keep immutable canonical evidence separate from disposable native-memory updates; explicitly disable concurrent-fact supersession; forbid document-edge transaction inference; preserve date precision/nulls and withhold unsupported replay; add only qualification receipts, no competing store or adapter scaffolds.

## Change history

- **1.0.0:** Initial source-qualified Brain persistence/retrieval mapping, durable-versus-rebuildable ownership, explicit concurrency/time/replay limits and safe local qualification. Original live acceptance remains BLOCKED; no deployed or issue-close claim.
- **1.0.1:** Bounded repair 1/2 publishes a pinned, synthetic-only, audited zero-write shipped-function command and carries verified declared-commit upstream MIT notice/provenance for the ten-descriptor snapshot. Historical validation remains historical; original #5 and runtime/release gates remain BLOCKED.
