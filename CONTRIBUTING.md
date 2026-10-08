# Contributing

Thanks for helping separate signal from noise in AI research. This is an open-research project: the code, the method and the data snapshots are public, and every scoring change is argued in a PR with numbers.

## The one rule: never invent numbers

- Every value on the page comes from a named, public source that is fetched or cached by the pipeline.
- Unknown means `null` in JSON and **—** on the page. It lowers confidence. It is never replaced by a guess, an average, an LLM estimate or a "reasonable default".
- Proxies are allowed only when they are labelled (`rate-proxy`, `vendor claim`) and count as weaker evidence (see [METHODOLOGY.md](METHODOLOGY.md#confidence-and-shrinkage)).
- Sampled counts (HYPE) are described as samples, never as platform-wide totals.

PRs that break this rule are closed, however good the ranking looks.

## Setup

```bash
git clone https://github.com/namastex888/trending-research && cd trending-research
pip install -r requirements.txt          # standard library only (installs tzdata on Windows)
python -m unittest discover tests        # unit tests
python eval.py --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json
python -m http.server 8765 -d web        # view the committed snapshot at http://localhost:8765
python run.py                            # full fetch (20-40 min; `gh auth login` raises GitHub limits)
```

After one full run you can iterate offline: `python run.py --rescore` re-scores the cached inputs with your local `scoring.py` / `scoring_config.json` without any network call.

## Propose a weight or threshold change

1. Edit [scoring_config.json](scoring_config.json). Every weight and threshold lives there.
2. Run the tests and `python eval.py`. It needs two feature snapshots in `history/runs/`, so run `python run.py` twice on different days, or pass `--features OLD NEW`.
3. Open a PR with the template and **paste the full `eval.py` output**. Reviewers look at:
   - **stability**: Spearman of the top-100 scores between the last two runs (higher means less churn from noise);
   - **evidence**: the share of top-100 rows with confidence >= 0.5;
   - **HYPE shortlist**: how the research's qualitative hype-vs-evidence cases land, and the label mix.
4. Update [METHODOLOGY.md](METHODOLOGY.md) in the same PR. The page renders that file, so docs and page cannot drift.
5. Bump the minor version (`2.0` -> `2.1`) in both `scoring.py` (`SCORING_VERSION`) and the config `version`. A formula change or new signal bumps the major version.

## Add a data source

1. Open a "Data source request" issue first: what it measures, access and terms, rate limits, biases.
2. In `run.py`, add a `fetch_<source>()` that:
   - caches its last good payload under `cache/` (`cpath()`, `save_json()`), and falls back to it on failure;
   - records its status with `note(name, status, detail)` so failures show on the page;
   - returns `None` for anything it could not observe.
3. Add the raw values to `build_features()`. Features are stored per run in `history/runs/*-features.json.gz`, which is what lets `eval.py` re-score history.
4. Add the signal to `scoring.py` and its weight to `scoring_config.json`. Decide its evidence weight (1 = measured, less for proxies or self-reported claims).
5. Add a unit test in `tests/test_scoring.py` for missing-data behaviour, and document the source and its limits in METHODOLOGY.md ("Data sources and their limits", "Known biases").

Never commit API tokens. GitHub auth comes from `gh auth` at run time.

## Add projects or seed lists

- **Papers / GitHub**: the candidate set comes from the queries at the top of `run.py`: `ARXIV_QUERIES`, `HF_SEARCH`, `GH_QUERIES`, and the subject tagger `TAG_RX`. Add a query or tag pattern, run `python run.py`, and say in the PR what it adds (new candidates, false positives you checked).
- **HYPE**: projects come from a social-research dossier (`hype/hype_research.json`, not committed, because it holds raw post excerpts). Suggest a project with the "Project suggestion" issue and public links. It is added in the next research pass.

## Code style

- Python standard library only, small functions, no hidden state. Scoring stays in `scoring.py` as pure functions.
- Keep `web/index.html` a single static file with no build step.
- Don't commit `cache/`, `history/`, `hype/`, logs or local paths (`.gitignore` covers them).

## Licences

Code contributions are under the MIT licence. Data snapshots (`web/*.json`) are CC BY 4.0. By contributing you agree to license your contribution the same way.
