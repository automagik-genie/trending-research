# Open model and harness research

This repository is an open research workspace for evaluating AI models and the harnesses that run autonomous tasks. The current case is the open intelligence observatory in cumulative [PR #22](https://github.com/namastex888/trending-research/pull/22). The 2026-10-14 product checkpoint and 2026-10-15 measured research checkpoint below are unfinished-goal handoffs, not releases. The comparison unit is a defined task and its accepted result, with model, harness, elapsed time, token use, and cost recorded for that same unit. A long conversation or a trace count alone does not establish which setup is more efficient.

## Product state at the checkpoint

The [roadmap](https://github.com/namastex888/trending-research/issues/1) has 20 child issues, five milestones, 80 original acceptance criteria, and 41 dependencies. Six issues (#2, #3, #5, #6, #8, #11) have historical local acceptance with separate quality evidence; 14 remain unaccepted, and no milestone exit has been accepted. PR #22 is cumulative work in progress, not a completed observatory. The [checkpoint](../.genie/wishes/open-intelligence-observatory/checkpoints/2026-10-14/CONTINUE.md) records the scope and limits of those acceptances.

## Phoenix readback, 2026-10-14

The configured Codex trace exporter points to the host-local privacy ingress. The installed relay routes filtered native Codex traces to the `sofia-codex` project on the configured Phoenix server. A read-only query of that server's PostgreSQL store at 22:22:51 UTC found 39 traces across 23 pseudonymous project sessions with trace starts in **2026-10-10 18:19 UTC to 2026-10-14 22:19 UTC**. The first matching stored trace started at 2026-10-10 23:19 UTC. These are project totals, not totals for this research task or proof of continuous coverage over 100 hours. An open trace can receive spans after its start, so counts for active sessions can change after the query.

Two active Codex workers in this task were matched from their native session UUIDs through the documented pseudonymization algorithm to stored Phoenix sessions. The telemetry research worker had one trace with 32 distinct LLM spans, from 22:16:27 to 22:18:55 UTC. The stored request model was `gpt-6-sol`; the spans recorded 2,009,039 input tokens, including 1,933,696 cache-read input tokens, and 9,264 output tokens. The README worker had one trace with 24 distinct LLM spans, from 22:16:28 to 22:18:45 UTC, recording the same model, 1,336,999 input tokens including 1,276,800 cache-read input tokens, and 8,170 output tokens. These are sums of per-span usage fields with span start at or before 22:19 UTC, as stored at 22:22:51 UTC; they are not total project or coordinator usage. Both workers were active, so final counts may be higher.

The coordinator runs in OMP/pi. Its local session envelope began on 2026-10-08 and records `gpt-6.1-sol` as its local model; the filename date is not measured active work time. An exact lookup of that native session ID found no Phoenix project session in any configured project. The active OMP config, installed extensions, and process environment exposed no Phoenix or OpenTelemetry exporter setting; the documented native relay covers Codex and Claude Code. This bounds the finding, but an undocumented exporter or different correlation scheme cannot be ruled out from these checks alone. Therefore the stored Codex worker spans cannot be treated as telemetry for the whole coordinator session. Provider-billed cost, complete coordinator token use, active worker time, full 100-hour coverage, and comparable quality outcomes remain unverified. Missing counters mean **unknown**, not zero.

The dated **local OMP session-file observation**, separate from Phoenix, counted 595 distinct structured assistant records in that same fixed 100-hour diagnostic window. It recorded 4,381,784 noncached input tokens, 76,316,544 cache-read tokens, 474,046 output tokens, and a `usage.cost.total` sum of 21.13568240 in the harness's local estimate field. Those entries run from 2026-10-10 23:19:55 to 2026-10-14 22:18:33 UTC. This is a file-recorded coordinator estimate, not an invoice or a whole-task total; worker costs and any unrecorded requests are outside it. The first and last entries do not measure active hours. Unlike the Phoenix fields above, OMP's local `input` field excludes its separate `cacheRead` field. The next dated update reconciles these same records and distinguishes complete LLM records from an unknown-usage error.

## Historical Codex readback method (authorized access)

On the authorized Phoenix host, inspect only the configured `sofia-codex` project and time-bounded `project_sessions`, `traces`, and `spans` tables in a `BEGIN READ ONLY` transaction with a statement timeout. Filter on an exact pseudonymous session ID derived by the installed `sofia/native/v1` algorithm from a native Codex UUID; verify the project and timestamp bounds before aggregating. Count distinct trace and span IDs, then sum `llm_token_count_prompt`, `llm_token_count_completion`, and `attributes.gen_ai.usage.cache_read.input_tokens` once per distinct LLM span. Keep input, output, and cache-read semantics separate; do not add the cache subset to input again. Check `attributes.gen_ai.request.model` per span. A server row is evidence of persistence; a configured exporter, local ingress response, or process log alone is not.

For a broader comparison, first establish exact experiment start and end times, native session-to-dispatch mappings, complete server pagination, and independently evaluated task outcomes. Record model request latency only from spans that actually enclose the provider request; the stored `handle_responses` spans here are too short to represent full model latency. Measure wall-clock and parallel worker time from their own lifecycle records. Preserve prompt and tool content outside public research notes, and never publish credentials or raw trace exports.

## Measured OMP checkpoint and human maintenance hold, 2026-10-15

The negative OMP finding above describes the **2026-10-14 readback**, not an instrumented history that existed then. Subsequent bounded backfill and live delivery have been demonstrated in **private observability infrastructure**. This public repository contains sanitized methodology and aggregate measurements, not deployable instrumentation source, raw telemetry or full public reproduction materials.

**Current disposition: the new bridge is stopped/disabled under an explicit human maintenance hold.** Automatic capture stopped around **19:35 UTC on October 15**; Phoenix is not a current-activity view. Production rollback/restore, same-ledger restart and same-epoch suffix resumption remain unverified. Historical persistence is not continuous current delivery; the full observatory goal remains unfinished.

### Admission, cohorts and actual stored confirmation

The adopted LIVE admission watermark is **2026-10-15T12:12:54.234Z**, distinct from the actual first bridge activation at **13:40:48 UTC**. HISTORY is the frozen byte-bounded current-parent prefix, defined by its admitted IDs and provenance—not all sessions or a simple timestamp-before-watermark query. The verified HISTORY and frozen LIVE cohorts have no ID overlap.

LIVE covers the existing parent's eligible suffix and genuinely new safe own-UID session envelopes/entries satisfying admission rules. **312 pre-watermark nonparent baseline sessions remain excluded/unknown, even if resumed later.** No all-OMP/all-worker-history coverage is claimed.

| Frozen cohort | Complete LLM records | Unknown error records | Total stored and confirmed |
|---|---:|---:|---:|
| Current-parent HISTORY prefix | 2,046 | 1 | 2,047 |
| LIVE frozen at 2026-10-15T19:35:05.557493Z | 382 | 0 | 382 |
| Combined distinct records | 2,428 | 1 | 2,429 |

The frozen LIVE cohort comprises **272 parent and 110 automatically discovered documentation-worker entries**. Original parent entry timestamps run from **12:13:16.444 to 19:32:56.671 UTC** on October 15; the worker entries run from **13:50:08.083 to 19:23:48.324 UTC**. At independent source cutoffs, at least four later complete entries (three parent and one worker) remained outside admission and eligible for catch-up. They were not exported during maintenance; subsequent growth is unknown.

For all 2,429 records, actual full typed Phoenix readbacks matched independently computed source projections, including identities, original clocks, usage/caches, cost/premium presence, SDK timing and provenance. The ledger records confirmed state and retired payload bodies with confirmation tombstones. The separately authorized historical replay at **20:49:56.986–20:50:00.982 UTC** attempted **zero new submissions**; bounded read-only queries found unchanged identities, accounting and typed rows, with no missing, mismatched, duplicate, unexpected or extra records. Both original independent reviewers accepted the scoped history, replay and fixed-window measurements—not production rollback/restore or the full goal.

**Collector ACK is transport acceptance, not full stored-field confirmation.** A durable pending outbox retains work but does not prove storage either. An earlier checkpoint had 77 confirmed records and later ACK-only additions; those dated states are not the final 2,429-record proof. The separate older full-retained local snapshot is also not this cohort or the fixed diagnostic window.

### Genuine new-session discovery during downtime

The documentation worker's observed session envelope began at **2026-10-15T13:50:00.681Z**, after admission and during the intentional bridge-only maintenance stop that began at **13:48:10 UTC**. It was not one of the baseline sessions. After later activation at **19:09:40.109893–19:09:44.740915 UTC**, the watcher automatically discovered its useful documentation activity without manual registration, resealing or export. The first entry at **13:50:08.083 UTC** and all 110 admitted worker entries belong to the fully confirmed frozen LIVE cohort. A fresh terminal or requested model alone would not prove session birth, discovery or persistence.

The **110 confirmed worker rows** record runtime `omp`, SDK/request model `gpt-6.1-sol`, provider `openai-codex` and API `openai-codex-responses`; the harness-version field is absent on all 110. These are observed source/stored metadata, not an inference from a requested model or installed package, and do not attest provider-returned model weights/version.

### Reconciliation of the original fixed 100-hour counter

The window remains **2026-10-10T18:19:00Z–2026-10-14T22:19:00Z**, inclusive by original assistant-entry timestamp and unique first-seen entry ID. It is not now-minus-100h, a proven goal-activation interval or 100 hours of active compute/coding. The selected entries run from **2026-10-10T23:19:55.471Z to 2026-10-14T22:18:33.644Z**.

All original **595 structured SDK records** match confirmed stored records: **594 complete LLM records plus one unknown-usage error CHAIN**, not 595 successful model requests. The error's original local counter structurally reported zero usage/cost, but exported provider/model/token/cost fields are absent; neither observation proves zero billing. Typed stored sums for the 594 complete records exactly reconcile the original dated local sums, with no timestamp/ID/window change:

| Measure | Reconciled recorded value |
|---|---:|
| Uncached input tokens | 4,381,784 |
| Cache-read input tokens | 76,316,544 |
| Cache-write input tokens | 0 |
| Prompt tokens, caches included once | 80,698,328 |
| Output tokens | 474,046 |
| Total tokens | 81,172,374 |
| SDK-local estimated cost, USD | 21.13568240 |

Cache reads are **94.5701675504% of recorded prompt tokens**, a token mix—not measured compute savings. Reasoning is present on **487 of 595 records** and absent on 108; its recorded 191,508-token sum is an output subset, never an extra addition. Premium-request metadata is numeric zero on 594 complete records and absent on the error, not proof of zero premium billing.

Ten auxiliary compactions fall inside the fixed window; their tokens and cost are unknown. The 40 current coded auxiliary diagnostics have a different scope: 35 historical parent compactions and five LIVE, not 40 window LLM requests. The USD sum is an **SDK-local catalog estimate**, not an invoice/provider-billed amount, repriced spend, all-worker total or whole-harness spend; unknown compaction/error costs remain unknown, not free.

### Recorded identity and SDK timing

The **594 reconciled complete fixed-window LLM records** carry SDK/request-model label `gpt-6.1-sol` and the recorded provider/API tuple `openai-codex` / `openai-codex-responses`. These fields do not attest provider-returned model weights/version; the stored response-model label was absent on the original 77-row LIVE checkpoint, with no wider presence-count claim here. The historical producing OMP version remains **unknown**; installed OMP `18.8.4` and bridge version do not establish it. Dated native Codex observations record request model `gpt-6-sol`, not an inferred `gpt-6.1-sol`. Native Claude usage/cost fields are absent; a database sum of zero does not mean free.

| SDK timing over 594 complete fixed-window LLM records | Mean, seconds | Median, seconds | p95, seconds |
|---|---:|---:|---:|
| Recorded request duration | 25.715753 | 14.887527 | 87.047454 |
| Recorded time to first token | 4.072549 | 2.954333 | 8.596157 |

Both timing fields are present on all 594 complete records; quantiles use nearest rank. The error additionally has recorded duration but no TTFT. These are SDK request measurements that can include setup/retries, **not provider compute, harness overhead or active/productive hours**. All 595 reconstructed spans have equal start/end timestamps: zero reconstructed span duration is not model latency. Human/transport waits and maintenance wall time are not autonomous coding or compute time.

### Operational limits and exact continuation

The bridge was intentionally stopped/disabled at **19:35:03.560759–19:35:05.165084 UTC** for bounded maintenance and remains held. Two diagnosed defects matter to continuation: a mutable compose-path bind could retain old kernel configuration while a copy reported newer host bytes, and a one-shot history scan could miss records without correctly continuing pagination. A human authorized one bounded proper source repair and independent review; isolated source acceptance is not production reversal verification. Loaded configuration requires actual process-start, kernel mountinfo and process-namespace hash proofs—not the helper's copy-derived result alone. Do not infer safe unattended/emergency rollback from the unchanged earlier helper or scoped storage results.

The human declined a proposed maintenance risk: a minute scheduler with a **120-second one-shot grace** could miss/retire runs during a **15-minute lock**, and allowed metadata could not prove that all writers outside the mutex were quiet. **No reservation was acquired and production rollback was not attempted.** There is no automatic retry/resume or authorization to expand source/locking scope. A successor needs new explicit current-state operator approval before any runtime effect; same-ledger restart, suffix catch-up and actual rollback/restore/native continuity across them remain unverified.

Native transport continued through the accepted frozen-cohort, historical import and replay windows without additional observed rejection. An earlier rejection increment from 26 to 27 had unknown cause and affected span loss; an earlier transient ingest backlog recovered without an established cause. Empty queues or a later zero rejection delta do not prove zero lifetime loss.

Continue with the existing [CONTINUE.md](../.genie/wishes/open-intelligence-observatory/checkpoints/2026-10-14/CONTINUE.md), unchanged issue order, prospective/parked reviews, budgets and native/paid/runtime gates, plus this newer maintenance hold. Do not replay historical grants. The six historical issue acceptances are not attributed to this exact window or the parent alone. Complete accepted-outcome attribution, whole-goal spend/active work and fair model/harness ranking remain unavailable; no cost per accepted issue or efficiency score follows from these cohorts.
