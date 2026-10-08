# Methodology

Current discovery method **3.0**; historical **2.0** remains executable with its frozen configuration. Code: [scoring.py](scoring.py); parameters: [scoring_config.json](scoring_config.json). The page renders `web/METHODOLOGY.md`, an identical copy.

## Overview

The tracker ranks three things:

- **Papers**: arXiv / Hugging Face papers on AI agents, harnesses and context layers, JEPA, JEV (decision models), world and action models, and a few non-LLM paradigms.
- **GitHub**: repositories ranked by a multi-signal *activity discovery index*. The historical name “trust index” does not establish trustworthy code.
- **HYPE**: sampled **Attention** and **Discovery** proxies for open and closed projects, with separate sourced usage families. Neither score measures technical capability, economic validation or truth.

Scores are 0-100 discovery proxies. They share weighted-signal and coverage stages, but the final shrinkage differs:

```
1. normalise each present signal:   u = min(1, log1p(v) / log1p(P95_ref))      (0 stays 0)
2. raw score:                       raw = 100 * sum(w_k * u_k) / sum(w_k)       over PRESENT signals
3. evidence coverage:               c = sum(w_k * e_k over present) / sum(w_k over all signals)
4. anti-noise multipliers:          raw = raw * m_1 * m_2 * ...                 (see Anti-noise rules)
5. GitHub/Papers:                   score = prior + c * (raw - prior)
                                   prior = median raw score of the reference population
   HYPE Attention/Discovery:       score = 50 + c * (pct - 50)
                                   pct = mid-rank percentile of raw, not raw itself
```

HYPE Attention ranks raw scores among the window's sampled-post candidates; HYPE Discovery ranks within the available-proxy cohort. Both shrink the percentile toward a fixed neutral prior of 50, not a reference median. The detailed sections below define the signals, references and heuristics.

**Missing stays missing**: `null`, displayed as —. No signal means no score. An unobserved closed-product user/customer metric is not zero or evidence of low value; observed zero remains a distinct measured value.

## Data sources and their limits

| Source | What we take | Limits |
|---|---|---|
| arXiv API | papers matching keyword queries per subject | keyword recall only; the API rate-limits (HTTP 429), in which case the last cached result is reused and the failure is shown under "Data sources" |
| Hugging Face papers API | upvotes, linked GitHub repo, repo stars, lab | upvotes exist only for papers posted to HF; cached 6-72 h by paper age |
| Hacker News (Algolia) | stories and comments that contain the exact arXiv id | HN only; Reddit's JSON API is blocked without auth, X/LinkedIn have no free API |
| GitHub REST API | repo search, issues / PRs / commits in a 30-day lookback (Search API), contributor counts | Search API quota limits how many repos get activity data per run (100 with auth, 30 without); the stargazer-timestamp endpoint returned HTTP 404 in our runs, so star growth comes from our own snapshots |
| Social research dossier (HYPE only) | sampled posts, unique authors, platforms, sourced usage figures, skeptic signals | a purposive public-source sample, not exhaustive listening. HN is about 2,019 of 2,163 sampled posts. No growth series, so acceleration can't be measured. Not committed to the repo |

Every source failure falls back to the last good cached payload and is reported in `data.json["sources"]`.

## Normalization

Version 1 divided by the window maximum. The v2 discovery normalization remains in v3 for compatible proxy signals:

```
P95_ref = 95th percentile of the positive values of that signal across ALL tracked items in this run
u(v)    = 0                               if v = 0
        = min(1, log1p(v) / log1p(P95_ref))   otherwise
```

- The reference does not depend on the window. GitHub uses each repo's 30-day values, papers use all tracked papers. A 1-day window with 8 candidates is scored on the same scale as the full list.
- Values above the P95 are winsorized to 1, so one viral item only caps itself.
- A PR fraction is used only with an observed, compatible created-and-merged cohort, never a clipped ratio of unrelated events.
- If fewer than `min_reference` (5) positive values exist, the maximum is used.
- `normalization.method = "percentile"` switches to rank-based percentiles (mid-rank among the positive reference values) for anyone who wants to test it in `eval.py`.

## Evidence coverage and shrinkage

**Evidence coverage** is weighted signal completeness with heuristic discounts. It is not verification, global sampling coverage, confidence in truth or calibrated accuracy:

```
c = sum(w_k * e_k for present signals) / sum(w_k for all signals)
e_k = 1    measured value
e_k = 0.5  rate proxy (per-day-since-release average used because no earlier snapshot exists)
e_k = 0.5  stars-only evidence for a paper's linked repo (no activity data)
e_k = c_repo  linked repository evidence coverage
Usage vendor claims are displayed separately, not discounted into a composite user magnitude.
```

**GitHub/Papers shrinkage** is a heuristic toward the reference median raw score. It has no validated Bayesian probability interpretation:

```
score = prior + c * (raw - prior)
prior = median raw score of the reference population in this run
        (all repos at 30d for GitHub, all tracked papers for Papers)
```

A GitHub/Papers row with 25% coverage moves a quarter of the way from the reference prior to its raw value. For prior 30 and raw 95 this is `30 + 0.25 * 65 = 46.3`. HYPE instead moves from fixed prior 50 toward its percentile, as defined in the Attention and Discovery sections. Tooltips expose raw value, coverage and prior separately from unqualified dimensions.

Every current row also exposes `verification: null`, `freshness: {assessed_at: null, newest_evidence_at: null}` and `independence: {origin_ids: [], rationale: null}`. These are unqualified, not negative findings. Counts, a platform-observed figure, a vendor label, cached generation time or multiple websites cannot establish independent replication, source clocks or common-origin independence. These discovery projections are not `Assessment.confidence` records: that contract requires admitted-evidence cohort counts and provenance qualification, which this pipeline has not acquired.

## Papers score

```
signals (weight):  upvotes   HF upvote momentum            0.40
                   code      linked-repo activity / 100     0.35   (evidence = repo coverage)
                   mentions  HN mention momentum            0.25
```

- **Upvote / mention momentum** = real delta between two of our snapshots (see Momentum). Without an earlier snapshot it is `value / max(age_days, 1)`: labelled *since-release* when the paper is younger than 7 days (that average is its whole life), otherwise *rate-proxy* (half evidence, `~` on the page).
- **Code**: the linked repo's activity discovery index. Without tracked activity, linked-repo star momentum is half-weight evidence; otherwise missing. Code availability/popularity is not functional correctness or capability.
- **Few-votes rule**: upvote evidence is multiplied by `n / (n + 10)`, where n is the paper's upvote count (`papers.upvote_evidence_k`). A paper one day old with 6 votes can have the highest upvote rate in the corpus. That is a small sample, so it counts as 0.38 of a signal and the score is shrunk toward the prior. Papers under 10 votes are flagged `few-votes`. Without this rule, fresh papers tied at the top of the upvote scale and reshuffled on every run.
- **Single-post rule**: if a paper's HN attention is exactly one post or comment, the mentions signal is multiplied by 0.5.
- Windows filter papers by release date. The score itself does not depend on the window.

## Repo trust index

```
signals (weight):  stars           star growth / day                      0.25
                   issues          (issues opened + closed) / 30 days     0.15
                   prs             PRs opened / 30 days                   0.10
                   merge           merged among PRs created in cohort     0.10
                   commits         commits / 30 days                      0.15
                   contribs        contributor count (level)              0.10
                   contrib_growth  contributors gained / day              0.15
```

- Activity (issues, PRs, merge rate, commits) is a 30-day lookback and is used only in windows of 15 days or more (`activity_min_window_days`). Short windows don't pretend a 30-day average is a 1-day count.
- **PR cohort repair**: denominator = PRs with `created:>since`; numerator = those same PRs satisfying `is:merged`. The separate `merged:>since` count is event volume and can include older PRs. Ten created, four of them merged, and twenty merge events gives **4/10 = 0.4**, not 20/10 clipped to 1. Empty, unavailable or invalid intersection counts give `null`. Legacy caches/fixtures without the intersection cannot reconstruct it, so current scoring omits that signal. Search calls are not atomic; inconsistent counts remain missing, not repaired by guessing.
- **Star growth**, in order of preference: the repo was born inside the window (all its stars are in-window growth), or exact stargazer timestamps when GitHub serves them, or a real delta between our snapshots. As a last resort, `stars / age`, marked *rate-proxy* at half evidence.
- Lifetime star totals are never a signal.
- `cache/repo_trust.json` retains the historical filename but current fields are `trust` (activity discovery index) and `coverage`. Papers and HYPE consume this named activity proxy, not a code-safety verdict. Old caches lacking current coverage do not enter the current HYPE producer.
- Windows: a repo is a candidate when it was created or pushed inside the window.

## Momentum

When at least two snapshots of an item exist (history DB: `paper_snap`, `repo_snap`), growth is a **real delta**:

```
rate = max(0, value_now - value_then) / span_days
then = the earlier snapshot closest to (now - horizon), at least min_snapshot_span_days (0.5) old
horizon = the window length for repos (90 for "overall"), 7 days for papers
```

This applies to stars and contributors (repos) and to upvotes, HN mentions and linked-repo stars (papers).

A delta over a span much shorter than the horizon is mostly noise. So when our snapshots cover only part of the horizon, the rate is **blended** with the per-day-since-release rate in proportion to the coverage:

```
w    = min(1, span_days / horizon)
rate = w * delta_rate + (1 - w) * since_release_rate        (kind: "blended")
evidence = 0.5 + 0.5 * w                                     (0.5 = rate_proxy_evidence)
```

Without earlier history, use the per-day-since-release rate, marked **rate-proxy** (half evidence). Young papers use their whole-life rate as *since-release*. History length is specific to the archived run; generation time is not proof that every source measurement is fresh.

## Anti-noise rules

| Rule | Applies to | Effect |
|---|---|---|
| Star spike without matching activity (star-farming pattern) | repos | the star unit is capped at `max(issues, PRs, commits units) + 0.4`; flag `stars>activity` |
| Stars but no outside contributors | repos with star unit >= 0.5 and <= 1 contributor | raw x 0.8; flag `solo` |
| Persistence over one-off spikes | repos with exact star counts for at least 2 of the 7/30/90-day horizons | `s = min(rate_h) / max(rate_h)`, raw x (1 - 0.15 * (1 - s)); flag `spike` if s < 0.25 |
| Single-post attention | papers whose HN attention is one post | mentions unit x 0.5; flag `single-post` |
| Single-platform attention | HYPE | Hype raw x 0.8; flag `single-platform` |
| A handful of authors | HYPE rows with <= 3 unique voices | Hype raw x 0.8; flag `few-voices` |

Flags appear next to the item on the page. Persistence needs exact per-horizon counts. Snapshot deltas give the same rate for every horizon, so they are not treated as evidence of persistence.

## Movement arrows

- Ranks are compared **only among items present in both runs** of the same tab, window and view. An item entering the list does not push everyone else down an arrow.
- An item not in the previous list shows **new**. If fewer than 50% of the rows overlap with the previous run (`min_overlap`), every row shows *new* with the reason in its tooltip.
- **Hysteresis**: an arrow appears only if the rank among common items moved by at least 2 **and** the score moved by at least 1.0 point. Otherwise the row shows `=`.
- When the scoring version changes, movement resets (`·`), because scores from two algorithms are not comparable.

## HYPE: Attention score

Per window (1d / 7d / 30d / 90d as measured by the research; *overall* = the 12-month lookback):

```
velocity      sampled posts in window / effective days    0.35   effective days = max(1, min(window, days since first seen))
acceleration  growth of velocity                           0.25   MISSING: the research has no growth series
voices        sampled unique authors in window             0.20
spread        (platforms with posts - 1) / (4 - 1), cap 1  0.20   fixed scale: one platform = 0, four or more = 1
```

Velocity and voices use the window candidate reference. Platform/voice penalties are heuristics, not proof of coordination. Attention is a percentile among projects with sampled posts:

```
pct   = mid-rank percentile of the raw score among the window's candidates (0..100)
Attention = 50 + c * (pct - 50)       (50 is the fixed neutral prior)
```

Acceleration is unobserved, so attention coverage is at most 0.75. This is a **sampled attention proxy**, not a platform-wide count, user population or validation measure.

## HYPE: Discovery score

Window-independent discovery components:

```
gh_trust    linked GitHub activity index / 100       0.30   evidence = linked repo coverage
paper       HF upvotes                              0.20   paper attention, not capability
discussion  sampled HN comments                     0.20   discussion attention, not technical/economic validation
```

Weights total 0.70: coverage uses that denominator; the raw weighted mean uses present weights. Usage has no composite weight. The percentile reference cohort is the exact set of observed component families (`gh_trust`, `paper`, `discussion`), not the entire heterogeneous open/closed population. Zero discussion is observed, not missing. A singleton cohort has midpoint percentile 50, not proven middling quality. Cohort membership and size appear on each card.

```
pct = mid-rank percentile within the available-proxy cohort
Discovery = 50 + coverage * (pct - 50)
```

### Usage metric families

Every sourced recognized usage record is retained, including observed zero and explicitly unknown values. No “largest downloads/users” selection:

| Family | Types | What it does not establish |
|---|---|---|
| `download_operations` | npm/PyPI/HF/checkpoint/package/app download operations | Unique users, active installations or customers; CI/repeats/updates can count |
| `users` | extension users, reported users, claimed monthly active users | Interchangeable user definitions, paying customers or economic outcomes |
| `business_customers` | business clients | Individual users, downloads or recognized revenue |
| `creators` | creator counts | Compatible general users or customers |

Normalization requires an exact cohort tuple `(family, type, unit, period.start, period.end, scope)`, with every element observed. Even within one family, different platforms/types, periods or scopes are not pooled. Unknown cohort metadata means `normalized: null`; values and source URLs remain visible. Normalized units stay attached to their named cohort; they are not comparable across cohorts and never enter the discovery composite. No source-origin independence, licences or period dates are inferred from URLs. An empty list means unobserved usage, not zero adoption.

## Attention-discovery gap

```
gap = Attention - Discovery
label = attention_ahead   if gap >= +15
        evidence_ahead    if gap <= -15
        similar           otherwise
        insufficient      if gap missing or either coverage < 0.5
```

This subtracts relative positions in **different proxy reference populations**, not comparable absolute magnitudes. It is a discovery heuristic, not “likely hype”, “earned”, “underrated”, technical validity or economic value. Coverage thresholds are not accuracy thresholds. Cards show research analyst observations separately; those are not independent acceptance receipts.

## Known biases

- **HN dominance**: Papers mentions and most HYPE posts come from Hacker News, which over-represents developer tools and under-represents research-only and non-English work.
- **HF selection**: only papers posted to HF have upvotes; absent upvotes are missing, not poor research.
- **Candidate search**: keyword/topic matching, source indexing and created/pushed-window filtering exclude relevant work with different vocabulary, languages or activity patterns. These are purposive discovered cohorts, not representative populations.
- **Enrichment selection**: quota-limited activity fetches favor repos ordered as promising; 100 authenticated or 30 unauthenticated enrichment targets are not random samples. Coverage and shrinkage cannot remove this selection bias. Query counts and reference populations change rankings; no unvalidated accuracy claim follows.
- **Young history**: snapshot deltas cover the time between our runs, not the full window, until enough runs accumulate. Rate proxies favour papers and repos that peaked early.
- **Shrinkage toward the reference prior** can under-rank genuinely strong but sparsely observed work. Closed/open observability is unequal; do not read missingness as weak capability or business value.
- **Research sample (HYPE)**: purposive and public-only. Follower counts, peak dates and true viral origins are mostly unknown and shown as —.

## Versioning

- Current version is `3.0` in code/config; formula and cohort semantics changed, so the major version increments. Minor changes adjust weights/thresholds without changing measurements.
- `score_run(features, version='2.0')` uses the complete frozen `legacy_v2` configuration, not mutable current parameters. `legacy_v2_real_scores` and `legacy_v2_hype_window` preserve historical arithmetic and labels for explicit evaluation only. V2 was a discovery method: its “Real”, “trust”, “confidence” and pooled usage labels did not establish capability, truth or compatible adoption magnitude.
- `score_run(features, version='1.0')` remains historical evaluation. Unsupported versions fail rather than silently running current formulas.
- `web/data.json` is an explicitly **archived v2.0 numeric artifact**. Its full input manifest and created-and-merged PR intersections are unavailable here. Scores, raw values, prior, original generation clocks and `config_sha` remain unchanged; renamed coverage and separate unknown dimensions clarify meaning. The old PR ratio is labeled historical, while the current cohort ratio is missing. No fabricated v3 rescore or serving/deployment receipt is implied.
- `web/hype.json` is an offline method-3.0 projection of preserved published observations. Its upstream GitHub proxy, where present, is historical v2 activity, explicitly identified; no corrected cohort, new source freshness or source approval is invented.
- Normal full runs retain feature snapshots. `python3 run.py --rescore` requires the actual cache/history inputs; publication views cannot recreate a complete immutable feature manifest.
- The page reads `web/METHODOLOGY.md`; keep it identical to this file. There is no current upstream CI workflow proving that equality.

## How to propose changes

1. Edit `scoring_config.json` (weights, thresholds) or `scoring.py` (formulas), and update this file in the same PR.
2. Run `python3 -m unittest discover tests` and `python3 eval.py --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json --compare-v2`.
3. Report stability, cohort completeness, before/after missingness and changed descriptive labels; these do not validate accuracy.
4. Explain the measurement correction, compatible cohort and missingness policy. “My favourite project moves up” is not a reason.

See [CONTRIBUTING.md](CONTRIBUTING.md) for data sources, seed lists and the never-invent-numbers rule.

## Issue 11 change record and attributed rulings

Before repair, the actual v2 code selected one million download operations over one hundred business customers and normalized downloads/users/customers into units 1.000/0.500/0.334. Actual `run.build_features` emitted merge 2.0 for ten opened/twenty merge events despite a known four-member intersection, and 0.0 for an empty PR denominator. Current code retains separate source records, leaves unknown cohorts unnormalized, uses the intersection fraction and keeps empty/unknown cohorts missing. Boundary fixtures are explicitly synthetic; the committed feature/HYPE fixtures are preserved subsets, not accuracy ground truth.

Observed committed HYPE fixture comparison (`hype_small.json`, SHA256 `4eb7b06dcffaf937d88150254e031e19e378f702b910b2d403a54bf77bc72e7f`):

| Project | Historical v2 score | Current discovery | Current usage treatment |
|---|---|---|---|
| Claude Code | 72.0 | 60.5 | 52,946,380 npm operations retained; period/scope cohort unknown, normalized missing; excluded from composite |
| Higgsfield | 61.2 | 48.5 | 32,000,000 reported users retained as vendor claim; unknown compatible cohort; excluded from composite |
| Gemini app | 59.6 | 62.0 | Usage remains unobserved; score is discussion discovery only, not a customer/capability finding |
| Reflection Beam | 40.4 | 37.2 | Usage remains unobserved; observed zero sampled discussion stays zero |

Scores change because usage is excluded, coverage denominator becomes 0.70 and percentiles use available-proxy cohorts. These are explained method effects, not evidence that rankings became more accurate. `eval.py --compare-v2` prints every fixture row; HYPE temporal stability remains unmeasured. Full-run feature fixtures lack PR intersections, so current repo coverage excludes their merge signal while explicit v2 replay preserves historical results.


- **Ruling — issue-11-engineer:** Increment to method 3.0 and freeze complete executable v2 parameters — preserves honest historical discovery replay without relabeling old outputs — cost if wrong: historical code/config remains maintained for explicit evaluation.
- **Ruling — issue-11-engineer:** Exclude usage from the composite and retain every recognized source metric with exact cohort metadata — operations/users/customers have no common magnitude — cost if wrong: fewer composite ranking signals and unnormalized records when metadata is missing.
- **Ruling — issue-11-engineer:** Use available-proxy cohorts and descriptive attention/discovery labels — discussion/upvotes/activity cannot establish capability or business validity — cost if wrong: small cohorts provide limited ranking resolution.
- **Ruling — issue-11-engineer:** Expose weighted completeness as coverage, with verification/freshness/independence unqualified — counts cannot fabricate provenance qualification — cost if wrong: consumers must inspect separate dimensions.
- **Ruling — issue-11-engineer:** Measure the merged subset of the created-PR cohort; omit unobserved/empty/invalid cohorts rather than clipping events — fixes mismatched denominators — cost if wrong: one additional public Search query per enriched repo and less historical coverage.
- **Ruling — issue-11-engineer:** Preserve `web/data.json` numeric v2 archive rather than reconstruct missing inputs; coordinator explicitly accepted this disposition — honest artifact identity beats fake current scores — cost if wrong: a complete corrected current GitHub projection awaits actual full-run inputs, not invented intersection counts.
- **Ruling — issue-11-engineer:** Move runtime directory creation to `main`, leaving imports side-effect free for in-memory extraction fixtures — actual query/feature boundaries can be exercised without cache/history mutation — cost if wrong: consumers previously relying on import-created directories must use the existing runtime entrypoint.
- **Ruling — issue-11-engineer:** Partial/missing Search totals stay unobserved and fresh legacy caches without a cohort intersection are requalified — otherwise an incomplete response can invent zero activity — cost if wrong: additional permitted reads on the next authorized collector run, never reads during this offline qualification.
- **Ruling — issue-11-engineer:** Display coverage to two decimal places in evaluation and use a version-neutral Methodology header — avoids rounding 0.75 to 0.8 or presenting current docs as the archived method — cost if wrong: slightly wider evaluation tables.

### Implementation qualification receipt

The implementation worker exercised these local commands against the completed source/config slice, after bounded fixture-close and display-precision repairs:

| Evidence | Observed result |
|---|---|
| `python3 -m unittest discover -s tests -p test_scoring.py` | Exit 0; 26 tests; zero failures, errors or warnings |
| `python3 eval.py --issue11-smoke --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json --compare-v2` | Exit 0; direct family/missingness/PR/dimensional checks plus all 25 before/after fixture rows |
| `python3 -m unittest discover tests && python3 eval.py --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json` | Exit 0; 43 tests and full evaluation; zero failures, errors or warnings |
| Permanent PR extraction regression against captured original `run.py` | Fails at intended assertion: `2.0 != 0.4`; passes in current focused/full suite |
| Explicit v2 execution against captured original `scoring.py` and original config | Exact equality of both complete feature fixtures, trust tuples and historical HYPE fields across overall/30d/7d |
| Historical numeric artifact preservation | All 7,706 paper/repo view rows preserve original numeric scores, raw values, rank/movement; method/config/prior/generation clocks unchanged |
| Actual browser at 1280px and 390px | Current HYPE rows/cards show source units, unobserved usage, missing period/scope cohorts and separate unqualified dimensions; archived GitHub and rendered Methodology inspected; no JavaScript errors observed |

`PYTHONDONTWRITEBYTECODE=1` was ambient for Python gates, not a replacement command. Initial SQLite context-manager fixtures passed but emitted ResourceWarnings; using explicit connection close removed the leak before final qualification. The original PR regression was exercised with a synthetic date-aware public-API response fixture at the actual Search/extraction boundary, not query-string source inspection or a live collection claim.

Browser screenshots were captured through the existing managed Chromium tool after the Orca screenshot command returned an unusable 1×1 image; that image was not treated as visual proof. At 390px the existing wide table/card requires horizontal scrolling; the right-hand units/dimensions were inspected after scrolling. No responsive redesign, accessibility audit, source verification, capability accuracy, live collection, editorial approval or deployment is claimed. Full immutable inputs for a corrected current GitHub rescore remain unavailable under the explicitly accepted historical-archive disposition.

Independent acceptance/design and separate quality review are coordinator gates, not this implementer's verdict. Local evidence does not establish deployed acceptance or authorize issue closure. No new repository paths, paid/model calls, source acquisition, shared-service restart, Git state mutation, commit, forge mutation or deployment were performed by this worker.

