# Evidence, claims and temporal contracts

Contract version: **1.0.0**. Authoritative wire format: [JSON Schema 2020-12](../../schemas/evidence.schema.json), ID `urn:open-intelligence:evidence:1.0.0`. [Synthetic examples](../../tests/fixtures/evidence_contracts.json) and [stdlib invariant verifier](../../tests/test_evidence_contracts.py) accompany the format. This is a domain contract, not a deployed storage, collector, editorial service or replay engine.

Source text, URLs, quotes and statements are **untrusted evidence**, never executable instructions. Their presence does not authorize tools, model calls, collection, retention, editorial approval or publication. Real access, licences, principals, budgets and runtime integrations remain unknown until independently qualified. Every example identity, date, statement, origin and transaction is explicitly synthetic; none is a factual finding. Financial amounts, actual measurements and approval receipts remain `null`.

## Identity and wire rules

- Bundle fields: `contract_version`, `fixture_notice`, `entities`, `source_revisions`, `evidence_spans`, `observations`, `claims`, `evidence_links`, `economic_relationships`, `assessments`, `publication_revisions`, `replay_manifests`, `scenes`. Collections are arrays; no party-pair or topic-keyed maps that silently discard competing records. `fixture_notice` is explanatory text for synthetic examples, otherwise `null`.
- Every record has a nonempty opaque `id`, globally unique across collections. Source, transaction and publication grouping IDs are separate opaque identifiers, not record references. IDs survive plugin/agent replacement and are not derived from names, aliases, amounts, dates or current URLs.
- Closed records require every declared field. Unknown nullable values are explicit `null`; omitted fields are invalid. Null means **unknown**, not zero, false, an inferred date, unlimited duration or permission. No string `"unknown"` in numeric fields; no NaN, Infinity or booleans masquerading as numbers.
- Reference fields target exactly the named collection. Lists have unique IDs. Each referenced record must exist. Empty evidence/subject/assessment lists cannot certify a claim, observation, relationship, assessment, publication or Scene.
- All timestamps are calendar-valid RFC3339 UTC instants ending in `Z`, with optional fractional seconds. Fractions compare at their full precision. Date-only upstream data cannot be made precise by inventing midnight: leave the instant/boundary `null` and preserve the original wording in evidence.
- Periods and event validity are `{start, end}`, half-open `[start,end)`. Known endpoints require `start < end`; `null` endpoints remain unknown, not open infinity. A measurement period and the period during which an event holds are independent.
- Enums are wire values, not translated labels. Unknown relationship status is the explicit `unknown` enum; it does not replace nullable amounts or times. Consumer versions must reject unsupported contract versions rather than silently reinterpret records.

## Named records

The schema gives exact field names, types, required/null rules and enums. These are their ownership and interpretation boundaries:

| Contract | Fields and meaning |
|---|---|
| `Entity` | `id`, `kind` (`organization`, `person`, `product`, `project`), `name`, `aliases`. Each alias has `value`, `scheme`, nullable `source_revision_id`; alias equality is scoped by scheme/provenance and is not proof that two entities are identical. |
| `SourceRevision` | `id`, `source_id`, nullable `revision_of`, `change_kind`, nullable `uri`, `content_sha256`, `content_text`, `media_type`, `source_published_at`, `observed_at`, required `ingested_at`, `origin_id`, `retention_status`, nullable `reason`. Publication clock is the source-reported clock; origin groups identify common upstream origin, not URL count. |
| `EvidenceSpan` | `id`, `source_revision_id`, `selector`, `quote`. Selector `{kind: "utf8_text", start, end}` uses offsets into exact UTF-8 **bytes**, not UTF-16 or character indexes. Both boundaries must delimit complete code points. |
| `Observation` | `id`, `entity_id`, `metric`, nullable numeric `value`, `unit`, `scope`, `period`, `event_validity`, nullable `observed_at`, `ingested_at`, `evidence_span_ids`, nullable `revision_of`. An unknown operating margin is still an attributable observation, not a zero margin. |
| `Claim` | `id`, `entity_ids`, `proposition`, nullable `asserted_by_entity_id`, `evidence_span_ids`, `event_validity`, `ingested_at`, nullable `revision_of`, `status` (`asserted`, `retracted`). Claims record assertions, not model-certified truth. |
| `EvidenceLink` | `id`, `from_claim_id`, `to_claim_id`, `relation` (`supports`, `contradicts`), `evidence_span_ids`, nullable `attributed_to_entity_id`, `ingested_at`. A directed, evidence-backed judgment with shared subject, no self-link. It neither edits its endpoints nor turns a relationship into an objective truth score. |
| `EconomicRelationship` | `id`, `transaction_id`, `kind`, `from_entity_id`, `to_entity_id`, nullable `amount`, `currency`, `period`, `reporting_party_entity_id`, `status`, `evidence_span_ids`, `event_validity`, `ingested_at`, nullable `revision_of`. Direction is provider/payer/investor to recipient. |
| `Assessment` | `id`, `claim_ids`, `conclusion`, `confidence`, `evidence_cutoff`, `method_version`, `computed_at`, nullable `attributed_to_entity_id`, `revision_of`. Interpretation of explicit claims under a pinned method; attribution being null does not authorize public interpretation. |
| `PublicationRevision` | `id`, `publication_id`, nullable `revision_of`, `assessment_ids`, `replay_manifest_id`, `status`, nullable `editorial_actor_entity_id`, `approved_at`, `published_at`. State is attached to one immutable revision, not a mutable global approved flag. |
| `ReplayManifest` | `id`, `evidence_cutoff`, `method_version`, `input_records`, `computed_at`, `history_mode: "known_at_cutoff"`. Inputs are `{collection, id, sha256}` from the seven evidence collections only, never an unspecified latest source or current network response. |
| `Scene` | `id`, nullable `publication_revision_id`, `assessment_ids`, `entity_ids`, `evidence_cutoff`, `method_version`. Shared selection/context for future UI and assistant consumers. No session credentials or approval authority. |

`unit` and `scope` are required nonempty descriptors, not implied by a display label. Consumers must compare only compatible metrics, units, scopes and measurement periods; a conversion creates a separately attributed observation with its own method, never edits the original. Currency is an explicitly reported three-uppercase-letter code or `null`; the pattern alone is not ISO registry validation. Amount with unknown currency is invalid. Signed amounts remain possible for reported adjustments; no automatic currency conversion, annualization or aggregation is implied.

## Five independent time dimensions

| Clock | Where | What it can establish |
|---|---|---|
| Source publication | `SourceRevision.source_published_at` | When a source says this revision was published; can be unknown or backdated. Not system knowledge time. |
| Event validity | `event_validity.start/end` on observations, claims, relationships | When a reported event/assertion applies. Not when evidence became available. |
| Observation | `SourceRevision.observed_at`, `Observation.observed_at` | When acquisition or measurement occurred; unknown when no receipt exists. |
| Ingestion | `ingested_at` on source revisions, observations, claims, links, relationships | When this immutable record entered accepted evidence. Required for knowledge-cutoff eligibility. |
| Computation | `Assessment.computed_at`, `ReplayManifest.computed_at` | When this specific method/input revision was evaluated. Not an event or publication date. |

An observation cannot occur after its own ingestion. A dependent record cannot cite evidence ingested after that dependent record; spans inherit the source revision ingestion clock. Source-reported publication clocks are not assumed consistent with acquisition clocks. Revisions cannot precede their prior record ingestion; equal ingestion instants still require an acyclic explicit chain. Computation cannot precede its evidence cutoff. Editorial approval/publication have their own clocks, not substitutes for these five.

### Truthful historical views

`known_at_cutoff` means **what this accepted system knew by the evidence cutoff**, under the stated method, from the exact retained manifest inputs. It is not everything publicly knowable on that date, the true state of the world, a live network reconstruction or a model of omitted sources. A backdated source first ingested later is excluded. A later correction may describe earlier events without becoming eligible for an earlier knowledge view.

Entity identity itself has no ingestion clock in v1. An entity/alias snapshot is admitted only by explicit manifest membership and hash; this contract cannot reconstruct when every alias was first known. Do not build a historical identity query from the current alias table. The same limit applies to unknown event boundaries and source dates: display their uncertainty, do not impute them.

The manifest explicitly selects its evidence set; it does **not** claim exhaustive coverage. It must include the transitive provenance/reference closure of selected records, including prior revisions and entity alias source references. Every selected nonentity input has ingestion time at or before the cutoff; every digest must match. Each bound publication assessment must be represented by its claims in the manifest and have identical cutoff, method and computation time. Scene selections must remain within that publication assessment/entity set and retain cutoff/method identity.

Exact replay also needs the executable method identified by `method_version`, qualified storage and legally retained original content. The method string pins identity; it is not proof the executable exists. The contracts qualify input identity only. Missing content, storage/runtime qualification or method implementation makes exact replay **unavailable**, not a success with empty results. No deployment or Brain restart durability is proved here.

## Immutable provenance and changes

1. Ingest is append-only. Reusing an existing ID with unequal canonical bytes is an identity conflict, never an upsert. Reimporting identical bytes is idempotent; accepted evidence is owned by durable storage, not agent/plugin memory. This issue specifies that boundary; later storage integration must enforce it.
2. A `SourceRevision` is one immutable captured revision. Its `source_id` groups the logical source, while `revision_of` references the exact prior record. `original` requires null prior; `revision`, `correction` and `deletion` require a prior and reason. Chains are acyclic and remain within source and origin identity. Forks remain visible; no automatic latest-wins merge.
3. `content_sha256` hashes exact raw UTF-8 bytes of retained `content_text`, with no normalization. This text representation is `text/plain; charset=utf-8`. Other acquired media need a separately qualified immutable original and text-extraction contract; v1 does not fabricate PDF/browser selectors. A hash-only retained external payload has no verifiable text span in this verifier.
4. Evidence spans address one exact source revision and verify quote equality against its byte slice. Correcting a source creates new revision/spans and, if appropriate, new claims/observations; old spans never redirect to current source content. Links preserve their original evidence.
5. Claims from different reporters can contradict without either having `revision_of`. A revision is an explicit same-author/same-subject correction, never inferred from topical similarity. Retraction appends a `retracted` claim referencing the prior claim; it does not remove its assertion/history.
6. Observation revisions preserve entity, metric, unit and scope. Relationship revisions preserve transaction, kind and both parties. Publication revisions preserve publication identity. Assessment revisions preserve ancestry but may explicitly change inputs or method; a new computation is not a mutation of an old assessment. No revision silently changes another record's evidence.
7. A deletion appends a source tombstone (`change_kind: "deletion"`, no content, `retention_status: "unavailable"` or `"redacted"`, reason). Original accepted records remain referenced when retention is permitted; a removed live URL does not erase a licensed capture. This is not authority to retain prohibited content.
8. If legal/privacy authority requires erasure of retained bytes or quoted spans, preserve only permitted identity/digest/tombstone metadata in the authorized storage layer, record the disposition, and mark exact replay unavailable. A bundle with missing source text cannot certify its old spans; the verifier deliberately fails closed. Removal authority and redaction storage mechanics require later qualification; immutable provenance is not an exemption from deletion obligations.

Source URLs, grouping IDs and aliases do not themselves prove independence, retention rights or identity merges. Do not copy text into logs or agent memory as a persistence substitute. Switching plugins/agents can discard rebuildable projections, not accepted observations, source records, manifests or publication revisions.

### Hash identity

Record digests use UTF-8 bytes of JSON serialized with sorted keys, compact separators, `ensure_ascii=False` and finite JSON numbers (the stdlib verifier uses `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`). Arrays retain order and strings are not normalized. Source-content hashing is different: exact raw content bytes, not the surrounding record JSON.

This is a pinned Python reference serialization, **not** a claim of RFC8785/JCS portability. Other-language producers must reproduce these bytes or preserve the original canonical bytes. Number formatting, Unicode normalization and object duplicate keys are integration risks; duplicate JSON keys and nonfinite constants are rejected on input by `load_bundle`. Runtime identity and cross-language golden-vector acceptance belong to dependent integration qualification. Do not hash a reserialized payload with a different method and claim the same manifest.

## Economic relationship types

| `kind` | Records | Never implies |
|---|---|---|
| `equity` | An investor contribution/ownership financing relationship | Recognized revenue or the only investor |
| `debt` | Borrowing/lending financing | Equity or revenue |
| `cloud_credit` | In-kind/service credit from provider to recipient | Cash received, realized spend or booked revenue |
| `commitment` | A future/promised obligation | Completed transfer or revenue recognition |
| `recognized_revenue` | Revenue explicitly recognized by a reporting party for a period | A financing round, credit or unsigned commitment |

Each edge is independently evidenced. `status` is one of `announced`, `committed`, `completed`, `recognized`, `cancelled`, `unknown`; type and status are separate. Only `recognized_revenue` can have `recognized` status; a recognized record requires a known reporting party and complete period. Recognized-revenue type with `unknown` status can encode an unqualified statement, not recognition proof. Other money measurements remain nullable and require source qualification; no amount or currency is inferred from transaction type.

`transaction_id` identifies an event, not a party pair. One event can have multiple investors and several typed components. A later event between the same parties gets a new transaction ID and an independent relationship ID. A correction to the same event/party/type gets a new relationship ID and explicit `revision_of`; it cannot supersede another investor or a repeated later transaction. Multiple sources describing one event may be retained as competing records until an attributed reconciliation; deduplication must never destroy originals.

## Confidence is dimensional, not probability

`Assessment.confidence` keeps four distinct dimensions; there is no single confidence score or probability-of-truth field:

- `coverage: {numerator, denominator, scope}` counts admitted evidence against an explicitly defined cohort. Both counts are null when unmeasured; otherwise integers with `0 <= numerator <= denominator` and denominator greater than zero. Zero-of-known-cohort is distinct from unknown. A fraction may describe cohort coverage, never global completeness or truth probability.
- `verification` is `unverified`, `source_checked`, `independently_replicated` or `disputed`. These labels record qualification, not calibrated correctness. A self-reported source check is not an independent replication receipt.
- `freshness: {assessed_at, newest_evidence_at}` keeps explicit clocks or null. Known values cannot lie after computation, newest evidence cannot lie after cutoff, and known newest evidence cannot follow the freshness assessment. Age is computed only against a stated clock; unknown timestamps remain unknown.
- `independence: {origin_ids, rationale}` groups actual upstream origins represented in claim provenance; it is not a count of websites or article copies. The verifier rejects invented origins, but cannot establish that declared real origin groups are independent. Empty groups/null rationale mean unqualified, not proven independence.

The synthetic fixture leaves coverage/freshness unknown and labels the assessment disputed. Its two illustrative origin IDs are not measurements of real source independence. Admission policy, replication receipts and origin attribution require later qualified sources; passing a structural verifier cannot confer them.

## Publication and review boundary

A draft has null approval/publication times. `published`, `corrected` and `retracted` revisions require an identified editorial actor and nonnull approval/publication times ordered after computation; correction/retraction also requires a prior publication revision. These fields **describe receipts**, they do not authorize transition. Production must verify the principal and receipt independently. No synthetic example claims that this authority exists: `publication:example:1` is a draft, with actor and approval/publication times null.

An independent reviewer must evaluate this exact four-file artifact digest, all four issue criteria and the integration risks below. Self-authored tests are not that review. The coordinator stores the attributed review receipt in the wish; issue closure remains gated on that independent design and quality acceptance. This document does not invent a review verdict or mark the issue complete.

## Exercise the examples

Run from the repository root; Python 3.14.4 at `/usr/bin/python3` was the qualified local runtime. No packages, model calls or network are needed.

```sh
python3 tests/test_evidence_contracts.py --smoke tests/fixtures/evidence_contracts.json
python3 -m unittest discover -s tests -p test_evidence_contracts.py
python3 -m unittest discover tests && python3 eval.py --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json
```

The direct smoke validates the bundle and independently exercises these expected example observations:

| Criterion | Expected direct observation |
|---|---|
| Contradiction without overwrite | `claim:sustainable:1` and `claim:unsustainable:1` both asserted, neither a revision of the other; `link:contradiction:1` connects them with exact spans and attribution. |
| Simultaneous investors/repeated transactions | `transaction:one` retains both `entity:investor-a` and `entity:investor-b`; `transaction:two` retains investor A independently, with no relationship supersession. Five economic types remain separate. |
| Revision trace and replay identity | `source:a:2` corrects `source:a:1`; old source, claim and span survive. Manifest includes both opposing claims at cutoff `2020-02-03T00:00:00Z`, method `fixture-method/1`, and excludes the later source/span/claim. |
| Independent review | Coordinator attaches separate attributed design/quality receipts to the exact artifact hashes; direct smoke cannot certify this criterion. |

Smoke prints the actual claim IDs, transaction/party groups, revision chain, cutoff, method and fixture SHA256, and exits nonzero on disagreement. It is an executable example, not tests alone or a deployed acceptance claim. Permanent tests include in-memory negative controls with specific expected rejection messages: overwritten identity, missing spans, cross-party/cross-event supersession, revision cycles, altered content, split UTF-8 spans, future evidence, omitted dependencies, changed hashes/method/cutoff, invalid cohorts, invented recognition/approval and Scene drift. A deletion test proves old retained evidence stays inspectable while unavailable new content cannot certify a span. No throwaway file or fake integration is required.

The stdlib `validate_bundle(bundle) -> None` and `load_bundle(path) -> dict` support these checks. They are **contract-specific invariant validation**, not an implementation of JSON Schema 2020-12. The schema declares wire constraints; an independent downstream schema validator must enforce full schema semantics (including optional format assertions). The verifier enforces identity, referential integrity, chronology, revision identity, exact available text spans, record hashes, replay closure, financial classification, dimensional confidence and publication/Scene binding. Neither validates real source truth, currency registries, licences, real approval identity or runtime durability.

## Unresolved integration risks

| Owner gate | Risk / required evidence |
|---|---|
| Source panel / #3 | Real entity identity, upstream origin independence, source rights, retention and acquisition clocks are unqualified. Synthetic fixture dates/text cannot become real observations. |
| DSH/Cordis / #4 | Assistant tools must treat all quoted text as untrusted and preserve Scene cutoff/method across cancellation, reconnect and tenant boundaries. No SDK/session selection exists here. |
| Brain / #5 | Immutable ID conflicts, append-only storage, exact span byte retention, explicit no-supersession semantics and restart durability need real authorized ingest/read-back proof. Date-only valid-time APIs cannot silently meet the UTC precision contract. |
| Read model / #7 | Durable evidence versus rebuildable projections, licensed erased-content disposition, alias-history limits and cross-language record hashing must be qualified against actual adapter/storage behavior. |
| Replay / #13 | Immutable retained inputs plus an available pinned executable method and enforceable offline execution are needed; strings and local fixture hashes alone cannot prove runtime replay. |
| Publication / #12 | Editorial identity, approval receipt, serving revision and newcomer/recovery/deployment observations remain null/unavailable until authorized. Local gate success is not release evidence. |

## Local verification receipt

Executed on the implementation artifact by **contracts-engineer**, using the qualified local Python runtime, after the complete four-file slice:

| Check | Actual result |
|---|---|
| Direct smoke command above | Exit 0; all three example scenarios observed, later correction excluded, fixture SHA256 `48b857151ad0899a130b9f9cc7096bc96fcd59c865883fb887048d93593885b5`. |
| Focused unittest command above | Exit 0; 17 tests, no failures, including specific in-memory rejection controls. |
| Frozen aggregate command above | Exit 0; 36 tests, no failures; full feature/HYPE fixture evaluation completed. Unchanged `tests/test_scoring.py:213` emitted an unclosed-file `ResourceWarning`; not suppressed or repaired outside ownership. |
| Additional read-only schema syntax/reference probe | Exit 0; JSON parsed, dialect is 2020-12, all 101 local `$ref` values resolve. No complete schema-engine conformance claim. |

The first focused run had one failure: the deletion negative control redirected an already-cited span and hit the earlier provenance-clock guard instead of the intended unavailable-content guard. The control was corrected to append a separate tombstone span; final smoke/focused/aggregate ran after that correction. This was a test-control repair, not a weakened guard or a production exception. The aggregate ran once on the completed corrected slice; no mid-flight gate, dependency install or external service was used. The schema probe parsed the schema and recursively collected `$ref` values, checking each targets an existing `$defs` entry; it did not interpret schema keywords.

Independent design/quality review is still a separate coordinator gate. Real source rights, durable storage/agent replacement, pinned method execution, editorial approval and deployed acceptance are **not proved** by this receipt. No throwaway scaffold was created or retained.

## Attributed engineering rulings

Plan identity: `open-intelligence-observatory`, issue #2 / Group 1, task `t_muz1j2dm37330b70`, worker **contracts-engineer**. Frozen planning base `1fe2a85853441690c89ef3e91731ed859afd7bcf`; original code baseline `65fe46ef8fde709fa3993cea98b20392b50089d9`.

- **Ruling — contracts-engineer:** Use one closed versioned JSON bundle with eleven named domain contracts and globally unique record IDs; keeps Python and future UI/assistant consumers on one wire authority. Cost if wrong: a versioned contract migration, not a silent compatibility shim.
- **Ruling — contracts-engineer:** Separate record IDs from source/transaction/publication grouping IDs and allow competing append-only records; preserves contradictory claims, concurrent investors and repeated events. Cost if wrong: attributed reconciliation must handle duplicates, never destroy raw evidence.
- **Ruling — contracts-engineer:** Keep all five clocks separate, explicit null boundaries and manifest-based known-at-cutoff history; prevents backdating and reconstructed knowledge from appearing factual. Cost if wrong: limited historical coverage, made visible rather than guessed.
- **Ruling — contracts-engineer:** Select UTF-8 byte spans for retained plain text, exact raw content hashes and pinned Python record serialization; locally verifiable without dependencies. Cost if wrong: new qualified media selectors or canonicalization version, with golden-vector review before cross-language adoption.
- **Ruling — contracts-engineer:** Keep financial kinds/status/currency/reporting-period separate and all unmeasured values null; prevents investment, credit or commitment becoming recognized revenue. Cost if wrong: additional financial classification requires attributed schema revision, not inferred conversions.
- **Ruling — contracts-engineer:** Model confidence as cohort coverage, verification, freshness and origin independence, with no aggregate probability; avoids false precision from missingness. Cost if wrong: consumers must explain four dimensions rather than display one truth score.
- **Ruling — contracts-engineer:** Use a domain-specific stdlib invariant verifier and behavioral negative controls, not a general schema engine or new dependency; exercises the evidence boundary inside current repository validation. Cost if wrong: downstream full schema enforcement remains an explicit integration obligation.
- **Ruling — contracts-engineer:** Leave examples synthetic, publication draft and real authority unknown; separate reviewer provides independent acceptance and storage/assistant/release gates remain unproved. Cost if wrong: dependent production work blocks rather than consuming fabricated receipts.

## Change record

- **1.0.0:** Initial evidence/claim/temporal and typed-economics wire contracts, illustrative competing/revision examples, direct smoke and invariant failure controls. No ranking behavior or existing scoring consumer is changed.
