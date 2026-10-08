# Methodology

Scoring version **2.0**. The code is [scoring.py](scoring.py) and every weight and threshold is in [scoring_config.json](scoring_config.json). The page's Methodology tab renders this same file, so the repo and the page always say the same thing.

## Overview

The tracker ranks three things:

- **Papers**: arXiv / Hugging Face papers on AI agents, harnesses and context layers, JEPA, JEV (decision models), world and action models, and a few non-LLM paradigms.
- **GitHub**: repositories on the same subjects, ranked by a *trust index* (sustained, multi-signal activity), never by star totals.
- **HYPE**: what the wider AI world is talking about (open and closed source), comparing **Hype** (sampled attention) with **Real** (evidence of substance).

Every score is 0-100 and goes through the same five steps:

```
1. normalise each present signal:   u = min(1, log1p(v) / log1p(P95_ref))      (0 stays 0)
2. raw score:                       raw = 100 * sum(w_k * u_k) / sum(w_k)       over PRESENT signals
3. confidence:                      c = sum(w_k * e_k over present) / sum(w_k over all signals)
4. anti-noise multipliers:          raw = raw * m_1 * m_2 * ...                 (see Anti-noise rules)
5. shrink toward the prior:         score = prior + c * (raw - prior)
```

The rule that never changes: **numbers are never invented**. A missing value stays missing, shows as —, and lowers confidence. An item with no signal at all has no score.

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

Version 1 divided each signal by the window maximum, so one outlier squashed everyone else and a small window inflated its few items. Version 2 compares every value with a **fixed run-wide reference**:

```
P95_ref = 95th percentile of the positive values of that signal across ALL tracked items in this run
u(v)    = 0                               if v = 0
        = min(1, log1p(v) / log1p(P95_ref))   otherwise
```

- The reference does not depend on the window. GitHub uses each repo's 30-day values, papers use all tracked papers. A 1-day window with 8 candidates is scored on the same scale as the full list.
- Values above the P95 are winsorized to 1, so one viral item only caps itself.
- Ratios such as the PR merge rate are already 0..1 and are used as they are.
- If fewer than `min_reference` (5) positive values exist, the maximum is used.
- `normalization.method = "percentile"` switches to rank-based percentiles (mid-rank among the positive reference values) for anyone who wants to test it in `eval.py`.

## Confidence and shrinkage

**Confidence** is the evidence-weighted share of signals that are present:

```
c = sum(w_k * e_k for present signals) / sum(w_k for all signals)
e_k = 1    measured value
e_k = 0.5  rate proxy (per-day-since-release average used because no earlier snapshot exists)
e_k = 0.5  vendor claim (usage figures that come only from the vendor)
e_k = 0.5  stars-only evidence for a paper's linked repo (no activity data)
e_k = c_repo  a linked repo's own trust confidence (paper code signal, HYPE GitHub trust)
```

**Shrinkage** is empirical-Bayes linear shrinkage toward a neutral prior, in proportion to missing evidence:

```
score = prior + c * (raw - prior)
prior = median raw score of the reference population in this run
        (all repos at 30d for GitHub, all tracked papers for Papers,
         HYPE: Hype and Real are percentiles, so their prior is 50; see below)
```

So a row with 25% confidence moves at most a quarter of the way from the median toward its raw value. It cannot post an extreme score. With a median of 30, a raw 95 at 25% confidence becomes `30 + 0.25 * 65 = 46.3`. The page shows raw, confidence and prior in each score's tooltip.

## Papers score

```
signals (weight):  upvotes   HF upvote momentum            0.40
                   code      linked-repo trust / 100        0.35   (evidence = the repo's confidence)
                   mentions  HN mention momentum            0.25
```

- **Upvote / mention momentum** = real delta between two of our snapshots (see Momentum). Without an earlier snapshot it is `value / max(age_days, 1)`: labelled *since-release* when the paper is younger than 7 days (that average is its whole life), otherwise *rate-proxy* (half evidence, `~` on the page).
- **Code**: the linked repo's v2 trust index when the repo is tracked. If not, the measured star growth of the linked repo from HF snapshots, at half evidence. Otherwise missing.
- **Few-votes rule**: upvote evidence is multiplied by `n / (n + 10)`, where n is the paper's upvote count (`papers.upvote_evidence_k`). A paper one day old with 6 votes can have the highest upvote rate in the corpus. That is a small sample, so it counts as 0.38 of a signal and the score is shrunk toward the prior. Papers under 10 votes are flagged `few-votes`. Without this rule, fresh papers tied at the top of the upvote scale and reshuffled on every run.
- **Single-post rule**: if a paper's HN attention is exactly one post or comment, the mentions signal is multiplied by 0.5.
- Windows filter papers by release date. The score itself does not depend on the window.

## Repo trust index

```
signals (weight):  stars           star growth / day                      0.25
                   issues          (issues opened + closed) / 30 days     0.15
                   prs             PRs opened / 30 days                   0.10
                   merge           PRs merged / PRs opened (0..1)         0.10
                   commits         commits / 30 days                      0.15
                   contribs        contributor count (level)              0.10
                   contrib_growth  contributors gained / day              0.15
```

- Activity (issues, PRs, merge rate, commits) is a 30-day lookback and is used only in windows of 15 days or more (`activity_min_window_days`). Short windows don't pretend a 30-day average is a 1-day count.
- **Star growth**, in order of preference: the repo was born inside the window (all its stars are in-window growth), or exact stargazer timestamps when GitHub serves them, or a real delta between our snapshots. As a last resort, `stars / age`, marked *rate-proxy* at half evidence.
- Lifetime star totals are never a signal.
- The 30-day trust index of every repo is saved to `cache/repo_trust.json`. The Papers score (code signal) and HYPE Real (GitHub trust) use it.
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

With no earlier snapshot at all, the row falls back to the per-day-since-release rate and is marked **rate-proxy** (`~`, half evidence). Papers younger than the horizon use their rate since release at full evidence (*since-release*). Snapshot deltas are only as old as our history (about 1.4 days between the first runs and the latest full run today), so most rates are still blended. As runs accumulate, `w` reaches 1 and the rates become true window deltas.

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

## HYPE: Hype score

Per window (1d / 7d / 30d / 90d as measured by the research; *overall* = the 12-month lookback):

```
velocity      sampled posts in window / effective days    0.35   effective days = max(1, min(window, days since first seen))
acceleration  growth of velocity                           0.25   MISSING: the research has no growth series
voices        sampled unique authors in window             0.20
spread        (platforms with posts - 1) / (4 - 1), cap 1  0.20   fixed scale: one platform = 0, four or more = 1
```

Velocity and voices use the log/P95 normalization against the window's candidates. Single-platform and few-voices penalties multiply the raw score. Then, so that Hype and Real can be subtracted, **both are put on the same percentile scale**:

```
pct   = mid-rank percentile of the raw score among the window's candidates (0..100)
Hype  = 50 + c * (pct - 50)          (50 = the median by construction = the prior)
```

Acceleration is always missing today, so Hype confidence is at most 0.75, and every Hype score is pulled at least a quarter of the way toward 50. Hype is a **sampled attention proxy**, not a platform-wide count.

## HYPE: Real score

Window-independent evidence of substance:

```
gh_trust    the GitHub trust index of the project's repo / 100    0.30   evidence = that repo's trust confidence
paper       HF upvotes of the linked arXiv paper                  0.20
usage       largest sourced downloads / users figure              0.30   vendor-only claims = half evidence
discussion  comments on the sampled HN stories                    0.20
```

```
pct   = mid-rank percentile of the raw Real score among all researched projects with any Real signal
Real  = 50 + c * (pct - 50)
```

Version 1 halved the *value* of vendor claims. Version 2 halves their *evidence* instead: a claim of 100M users is weaker evidence, not evidence of fewer users. In version 1, many rows had Real from HN discussion alone at "25% confidence" (for example Gemini app, Real 94.8). They now have confidence 0.20, so their Real stays within 10 points of 50.

## Hype vs Real gap

```
gap = Hype_shrunk - Real_shrunk
label = "likely hype"          if gap >= +15
        "underrated sleeper"   if gap <= -15
        "earned"               otherwise
        ...but only when Hype confidence >= 0.5 AND Real confidence >= 0.5;
        else "insufficient evidence" (grey badge with "?")
```

Because Hype and Real are both percentiles shrunk toward 50, the gap reads as "attention percentile minus substance percentile", and a project with little evidence on either side drifts toward a gap of 0 instead of a spurious one. A large gap built on thin evidence is not a finding, so it stays unlabelled. The research team's qualitative shortlist (`five_qualitative_hype_vs_evidence_gaps`) is shown on each project card, and `eval.py` reports where it lands under v1 and v2.

## Known biases

- **HN dominance**: Papers mentions and most HYPE posts come from Hacker News, which over-represents developer tools and under-represents research-only and non-English work.
- **HF selection**: only papers someone posted to Hugging Face have upvotes. Papers without them rely on code and HN, at lower confidence.
- **Search recall**: keyword and topic queries miss items that use other words. JEV / decision-model work is sparse and easy to miss.
- **Activity budget**: the Search API quota limits activity data to the most promising ~100 repos per run. The rest score on fewer signals, at lower confidence (shrunk, not zeroed).
- **Young history**: snapshot deltas cover the time between our runs, not the full window, until enough runs accumulate. Rate proxies favour papers and repos that peaked early.
- **Shrinkage toward the median** pulls thin-evidence items toward the middle in both directions, so a genuinely great item with little data can be under-ranked until evidence arrives. That is the intended trade-off.
- **Research sample (HYPE)**: purposive and public-only. Follower counts, peak dates and true viral origins are mostly unknown and shown as —.

## Versioning

- `SCORING_VERSION` in `scoring.py` (currently 2.0) must equal `version` in `scoring_config.json`. Both are stamped into `web/data.json`, `web/hype.json` and every history run, together with a short hash of the config file (`config_sha`).
- Bump the minor version (2.1) for weight or threshold changes, and the major version (3.0) for new signals or formula changes.
- Every full run stores its inputs in `history/runs/<stamp>-features.json.gz`, so any run can be re-scored under any version (`eval.py`, `scoring.score_run(features, version='1.0')`).
- `python run.py --rescore` re-scores the last full run's cached inputs with the current code and config, without network calls.
- The page reads `web/METHODOLOGY.md`, a copy of this file that `run.py` refreshes on every run. Keep them identical (the CI workflow checks this): edit the root file and copy it (`cp METHODOLOGY.md web/`).

## How to propose changes

1. Edit `scoring_config.json` (weights, thresholds) or `scoring.py` (formulas), and update this file in the same PR.
2. Run `python -m unittest discover tests` and `python eval.py`.
3. Paste the full `eval.py` output into the PR. Reviewers look at stability (Spearman of the top 100 between runs), the share of top rows with confidence >= 0.5, and how the HYPE shortlist moves.
4. Explain why the change separates signal from noise better. "My favourite project moves up" is not a reason.

See [CONTRIBUTING.md](CONTRIBUTING.md) for data sources, seed lists and the never-invent-numbers rule.
