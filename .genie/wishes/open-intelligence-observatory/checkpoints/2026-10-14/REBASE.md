# PR22 rebase onto the refreshed upstream

## Identity and scope

- Previous feature/PR head: `c620c1d15a554395bc7bad4d36bc4220e599899f`.
- Exact upstream baseline: `2c7afe577b79ccbaff6e4ff1b2162ce4bb7b3c0a` (2026-10-14 daily refresh).
- Completed 16-commit replay head before this note: `feb26a75955f90e5498ce4eaad3bbd86b37419aa`; upstream is its ancestor.
- Only conflicts: `web/data.json` and `web/hype.json`, while replaying `bb73b063957f2b6ccf0b0311e1770730faa8e2c0` as `5fd3139`. No additional conflict or source repair. Before this note, the complete tree difference from the old feature head names only those two JSON files.
- Same draft PR22 against `main`; publication awaits independent review and Parent grant. The only eligible history-rewrite lease is the exact previous feature head above. This note does not claim remote publication, CI, mergeability, deployment, runtime, source approval or roadmap completion.

## Both intents and resolution

Upstream refreshed the original discovered paper/repository observations and GitHub/paper inputs to the published HYPE dossier. Feature history corrected the meaning of discovery proxies, coverage, PR cohorts, adoption units and unqualified evidence dimensions. Composition applies the existing feature semantic projection to the exact pinned upstream JSON bytes, not a wholesale side selection or a regeneration from old cache.

The offline transformation was first replayed against the immutable parent of `bb73b06`; both resulting objects matched that commit's generated artifacts exactly. The same transformation was then applied to the two pinned upstream artifacts. No collector, provider, SDK or production generator ran; no absent cache/history/dossier input was invented.

`data.json` retains every upstream item and all 7,988 published ranking rows, with original scores, raw values, priors, movement, source statuses and clocks. Numeric method remains historical **2.0**, config `64d6540755`. Row confidence becomes coverage; verification/freshness/independence remain separately unqualified. The old mismatched PR event ratio remains `historical_merge_event_ratio`; current `merge_rate` and created-and-merged intersection remain null. A fabricated v3 numeric replay would require missing immutable inputs.

`hype.json` retains all 82 upstream dossier identities and original compact observations, social/source URLs, windows, usage records and refreshed GitHub/paper inputs. Existing `scoring.discovery_scores` and `scoring.hype_window` recompute method **3.0**, config `e2e3fe2870`, using exact available-proxy cohorts. Usage families remain outside the composite; absent period/scope stays null rather than inferred from URLs. GitHub activity inputs remain explicitly historical method 2.0, not corrected cohort measurements. Movement resets across the semantic cutover. The source generation clock is retained, not relabeled as a fresh research or projection-computation receipt.

## Actual data identity and checks

| Artifact | Resolved SHA256 | Exact upstream input SHA256 |
|---|---|---|
| `web/data.json` | `63f3b612517a9601354ddeb613daf34f9162d3c85fb78e0fef5d568264db17f2` | `cd47f70db7c50213b96f07bcf894c9d61bcdd1b4eb11cf50b8f4b950f7b0f728` |
| `web/hype.json` | `b1158a0b1a6612937c9c244bf1aeb597627eace61afc20f475cc62c8930e4ffe` | `75624b2e2c061fca0771d6a94f5471e284240e3ac2c17e508f2e99a8c3183f07` |

Generation clocks: data `2026-10-14T10:02:36Z`, HYPE `2026-10-14T10:24:49Z`; research generation remains `2026-10-07T04:18:35.578659Z`, cutoff `2026-10-07T03:43:21Z`. Published items: 927 papers/870 repositories; upstream tracked population remains 4,730/1,707.

- Root aggregate `python3 -m unittest discover tests && python3 eval.py --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json`: **exit 0, 45 tests OK and evaluation**.
- `python3 eval.py --issue11-smoke --features tests/fixtures/features_a.json tests/fixtures/features_b.json --hype tests/fixtures/hype_small.json --compare-v2`: **exit 0**.
- Throwaway offline real-data smoke: **pass**. JSON parses/round-trips, every archive row reverses exactly to upstream, every original HYPE observation is unchanged, all 82 discovery records match scorer recomputation. Negative controls reject the old branch clock and upstream-v2 HYPE's missing discovery shape.
- Actual localhost static browser consumer: **pass**. Papers displays Oct14 generation and Coverage; GitHub 30d displays `yetone/magpie`, score 93.1, 12,339 gained, PR `553 / — (368 events)`. HYPE Claude Code displays 52,946,380 download operations, unknown compatible cohort and discussion-only cohort of 57; DeepSeek Harness displays refreshed historical activity 44.3 with 91% coverage and its three-proxy cohort. Screenshot observed; browser errors empty. Preview serves only `web/`; no external collection or deployment.
- `genie wish lint --dir <worktree>` executed once after replay: **exit 1, three findings**, not the earlier recorded single finding. All three preserved historical DESIGN snapshots lack Execution Strategy tables: checkpoint artifacts `oi4-native-extension-repair3-before-DESIGN-621ea.md`, `oi4-native-extension-repair2-before-DESIGN-4e895.md`, and verification `group-3-native-extension-round1-before-design-repair1-full-DESIGN-originald689.md`. Their bytes are unchanged from c620; none was suppressed, fixed or reclassified as a new product defect. The earlier count remains historical evidence, not a fresh lint claim.

## Preserved work and remaining gates

All existing source/tests/WISH/checkpoint artifacts remain byte-identical to the previous feature tree outside the two intentional JSON changes. Six private untracked originals were not opened, hashed, staged, stashed, deleted or published. WISH's 80 criteria, 41 edges and historical artifact references remain intact. Six historical local acceptances remain historical; all twenty-issue roadmap work is still unfinished and no paused source candidate was applied.

Independent reviewer receives the exact final candidate SHA and concise full integration report before any push. Parent owns review acceptance, publication grant, and remote PR/baseline metadata. No feature, paid, native, release, merge or main-push grant follows from this rebase.
