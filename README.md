# AI research trend tracker

Live ranking of AI research **papers** and **GitHub repos** focused on agents, harness/context, JEPA, and world/action models.

## The page

Open `web/index.html` (it loads `web/data.json`, and `web/hype.json` lazily for HYPE). The UI has three top-level tabs:

- **Papers** — arXiv papers scored by Hugging Face upvotes, linked-repo activity, and Hacker News mentions
- **GitHub** — repos scored by a multi-signal trust/momentum index (not lifetime star totals)
- **HYPE** — what is going on in AI overall (open + closed source): early viral projects, and hype vs. real substance

Time **windows** (`1d`, `7d`, `30d`, `90d`, `180d`, `1y`, `overall`) filter papers by release date and repos by create/push activity in that window. Paradigm buttons re-rank within a tag (agents, harness, JEPA, world, …). Rank arrows compare to the previous run.

## Trust index (one paragraph)

Scores are **0–100 momentum**, not raw popularity: each present signal is log-scaled within the window (`z = log1p(rate) / max(log1p(rate))`), missing signals count as 0 and lower confidence, then `score = 100 × Σ(w·z) / max(raw in window)`. **Repos** weight star *growth*/day (~25–35%), issue activity/day, PR volume/day + merge rate, commit frequency/day, and contributor count + contributor growth/day (activity lookback ≈ 30d). **Papers** weight HF upvotes/day (40%), linked-repo trust score when available else measured star growth (35%), and HN mentions/day (25%).

## HYPE tab

Built by `hype_build.py` from a social-research dossier (`hype/hype_research.json`, X / Reddit / LinkedIn / HN / YouTube / Telegram / Discord; not committed). `run.py` calls it automatically when that file exists, so dropping in a new dossier updates the tab; `python3 hype_build.py` rebuilds HYPE alone. Output is the compact `web/hype.json` (~0.55 MB, only the fields the table and cards need). HYPE ranks go into the same history DB as the other tabs (tab `hype`), so arrows compare to the previous HYPE run.

- **Hype (0–100), a sampled attention proxy**: mention velocity 35% (sampled posts / effective days in window), acceleration 25%, unique voices 20%, cross-platform spread 20%. Each component is log-scaled against the window max (`z = log1p(v)/max log1p(v)`, spread = n / max n). The score is `100 · Σ(w·z) / Σ(w of present components)`, and **confidence** is the share of the 4 components present. *Acceleration can't be computed from this data* (no growth series; the HN sample is the first 100 hits by date), so its weight is spread over the other three and confidence tops out at 75%.
- **Real (0–100), substance, the same for every window**: GitHub trust index 30% (the GitHub tab's score for the same repo), paper traction 20% (Hugging Face upvotes for the linked arXiv paper), real usage 30% (largest sourced downloads/users figure; vendor claims count half), developer discussion 20% (comments on the sampled HN stories). Missing components are dropped and the weights renormalised; confidence = present / 4.
- **Gap = Hype − Real**: ≥ +15 likely hype (red), ≤ −15 underrated sleeper (blue), otherwise earned (green). A dashed badge means Real rests on fewer than 2 signals.
- **Windows**: 1d / 7d / 30d / 90d are the windows the research measured. *overall* is the 12-month lookback. 180d and 1y are disabled because the research has no such windows.
- **Coverage caveats**: this is a purposive, public-source sample, not exhaustive social listening. Platform-wide counts, author censuses, peak dates, true viral origin, follower counts and growth series are all null in the source, and the page shows them as —. Downloads count repeat operations, not unique users. Coordination is never inferred: the card only shows measured signals and disclosed sponsorship with evidence links.

## Run locally

```bash
python3 run.py         # writes web/data.json (+ web/hype.json if hype/hype_research.json exists; cache/ and history/ are gitignored)
python3 hype_build.py  # rebuild only the HYPE tab
```

Serve `web/` with any static file server to view the dashboard. Sources are public APIs (arXiv, Hugging Face, HN Algolia, GitHub); optional `gh` auth raises GitHub rate limits.
