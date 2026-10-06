# AI research trend tracker

Live ranking of AI research **papers** and **GitHub repos** focused on agents, harness/context, JEPA, and world/action models.

## The page

Open `web/index.html` (it loads `web/data.json`). The UI has two top-level tabs:

- **Papers** — arXiv papers scored by Hugging Face upvotes, linked-repo activity, and Hacker News mentions
- **GitHub** — repos scored by a multi-signal trust/momentum index (not lifetime star totals)

Time **windows** (`1d`, `7d`, `30d`, `90d`, `180d`, `1y`, `overall`) filter papers by release date and repos by create/push activity in that window. Paradigm buttons re-rank within a tag (agents, harness, JEPA, world, …). Rank arrows compare to the previous run.

## Trust index (one paragraph)

Scores are **0–100 momentum**, not raw popularity: each present signal is log-scaled within the window (`z = log1p(rate) / max(log1p(rate))`), missing signals count as 0 and lower confidence, then `score = 100 × Σ(w·z) / max(raw in window)`. **Repos** weight star *growth*/day (~25–35%), issue activity/day, PR volume/day + merge rate, commit frequency/day, and contributor count + contributor growth/day (activity lookback ≈ 30d). **Papers** weight HF upvotes/day (40%), linked-repo trust score when available else measured star growth (35%), and HN mentions/day (25%).

## Run locally

```bash
python3 run.py   # writes web/data.json (+ local cache/ and history/, gitignored)
```

Serve `web/` with any static file server to view the dashboard. Sources are public APIs (arXiv, Hugging Face, HN Algolia, GitHub); optional `gh` auth raises GitHub rate limits.
