#!/usr/bin/env python3
"""Evaluate discovery fixtures: stability and coverage are not accuracy measurements.

python3 eval.py --features OLD NEW --hype HYPE [--compare-v2] [--issue11-smoke]
Legacy v1/v2 are explicit historical methods; current consumers use method 3.0.
"""
import argparse, glob, gzip, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scoring
import hype_build


def load_any(path):
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'rt') as f:
        return json.load(f)


def fmt(v, nd=1):
    if v is None:
        return '—'
    return f'{v:.{nd}f}' if isinstance(v, float) else str(v)


def table(head, rows):
    return '\n'.join(['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|'] +
                     ['| ' + ' | '.join(fmt(c) for c in row) + ' |' for row in rows])


def stability(old, new, n):
    top = [r for r in new if r['score'] is not None][:n]
    old_s = {r['id']: r['score'] for r in old if r['score'] is not None}
    old_top = {r['id'] for r in [r for r in old if r['score'] is not None][:n]}
    pairs = [(old_s[r['id']], r['score']) for r in top if r['id'] in old_s]
    rho = scoring.spearman([p[0] for p in pairs], [p[1] for p in pairs])
    overlap = len({r['id'] for r in top} & old_top) / len(top) if top else None
    return rho, len(pairs), overlap, len(top)


def coverage_share(rows, n, threshold, legacy=False):
    top = [r for r in rows if r['score'] is not None][:n]
    key = 'conf' if legacy else 'coverage'
    return sum(r[key] >= threshold for r in top) / len(top) if top else None


def current_inputs(items):
    """Admit historical fixture observations explicitly, not as a production compatibility wire."""
    out = {}
    for pid, item in items.items():
        if 'evidence_in' in item:
            evidence = item['evidence_in']
        else:
            old = item.get('real_in') or {}
            evidence = {k: old.get(k) for k in ('gh_trust', 'paper', 'discussion')}
            if evidence['gh_trust']:
                evidence['gh_trust'] = dict(evidence['gh_trust'])
                evidence['gh_trust']['coverage'] = evidence['gh_trust'].pop('conf', None)
            evidence['usage'] = [dict(old['usage'], period=dict(start=None, end=None), scope=None)] if old.get('usage') else []
        out[pid] = dict(win=item['win'], age=item.get('age_at_cutoff'), evidence_in=evidence)
    return out


def historical_inputs(items):
    """Historical evaluation alone reconstructs the old largest-sourced-value selection."""
    out = {}
    for pid, item in items.items():
        if 'real_in' in item:
            old = item['real_in']
        else:
            evidence = item.get('evidence_in') or {}
            old = {k: evidence.get(k) for k in ('gh_trust', 'paper', 'discussion')}
            if old['gh_trust']:
                old['gh_trust'] = dict(old['gh_trust'])
                old['gh_trust']['conf'] = old['gh_trust'].pop('coverage', None)
            observed = [m for m in evidence.get('usage') or [] if scoring.isnum(m.get('value')) and m['value'] > 0]
            old['usage'] = max(observed, key=lambda m: (not m.get('vendor'), m['value']), default=None)
        out[pid] = dict(win=item['win'], age=item.get('age_at_cutoff'), real_in=old)
    return out


def issue11_smoke(cfg):
    signals = [dict(type=t, value=v, unit=u, source_url='https://example.test/' + t)
               for t, v, u in [('npm_downloads', 1000000, 'operations'),
                               ('reported_users', 1000, 'users'), ('business_clients', 100, 'customers'),
                               ('app_downloads', 0, 'operations')]]
    metrics = hype_build.usage_signals(signals)
    P = {'mixed': dict(evidence_in=dict(usage=metrics)), 'closed': dict(evidence_in={})}
    rows, _ = scoring.discovery_scores(P, cfg)
    assert [m['value'] for m in rows['mixed']['metrics']] == [1000000, 1000, 100, 0]
    assert all(m['normalized'] is None for m in rows['mixed']['metrics'])
    assert rows['closed']['score'] is None and rows['closed']['usage_missingness'] == 'unobserved'
    assert rows['closed']['metrics'] == []
    assert scoring.pr_cohort_ratio(dict(prs_opened=10, prs_merged=20, prs_merged_in_opened_cohort=4)) == .4
    assert scoring.pr_cohort_ratio(dict(prs_opened=10, prs_merged=20)) is None
    assert scoring.pr_cohort_ratio(dict(prs_opened=0, prs_merged_in_opened_cohort=0)) is None
    assert all(r['verification'] is None and r['freshness']['assessed_at'] is None and
               r['independence']['origin_ids'] == [] for r in rows.values())
    print('Issue #11 direct smoke: source metrics retained; incompatible/unknown cohorts unnormalized; '
          'closed usage unobserved; PR intersection 4/10=.4, unknown/empty cohort missing; dimensions unqualified.')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--features', nargs=2, metavar=('OLD', 'NEW'))
    ap.add_argument('--hype', default=os.path.join(HERE, 'web', 'hype.json'))
    ap.add_argument('--shortlist', default=os.path.join(HERE, 'hype', 'hype_summary.json'))
    ap.add_argument('--config', default=None)
    ap.add_argument('--compare-v2', action='store_true')
    ap.add_argument('--issue11-smoke', action='store_true')
    a = ap.parse_args(argv)
    cfg = scoring.load_config(a.config)
    N, threshold = cfg['eval']['top_n'], cfg['eval']['coverage_threshold']
    versions = ('1.0', '2.0', scoring.SCORING_VERSION)
    print(f'# Discovery evaluation: current {scoring.SCORING_VERSION}, config {scoring.config_sha(a.config)}')
    print('Stability, completeness and relative gaps are descriptive; no validated accuracy or truth probability.\n')
    if a.issue11_smoke:
        issue11_smoke(cfg)
    paths = a.features or sorted(glob.glob(os.path.join(HERE, 'history', 'runs', '*-features.json.gz')))[-2:]
    if len(paths) < 2:
        print('Papers/GitHub: unavailable, need two immutable feature snapshots.')
    else:
        old, new = (load_any(p) for p in paths)
        print(f'Feature cutoffs: {old["asof"]} → {new["asof"]}')
        results = {v: (scoring.score_run(old, cfg, v), scoring.score_run(new, cfg, v)) for v in versions}
        rows = []
        for tab in ('papers', 'repos'):
            for w in cfg['eval']['windows']:
                for version in versions:
                    before, after = (r[tab].get(w, []) for r in results[version])
                    rho, pairs, overlap, count = stability(before, after, N)
                    rows.append([tab, w, version, fmt(rho, 3), f'{pairs}/{count}', fmt(overlap, 2),
                                 fmt(coverage_share(after, N, threshold, version == '1.0'), 2)])
        print(table(['tab', 'window', 'method', 'Spearman', 'pairs/top', 'overlap', f'coverage ≥ {threshold}'], rows))
        print('Old feature merge ratios lack the created-and-merged intersection: current method excludes that signal; v2 preserves it.')
    H = load_any(a.hype)  # A missing requested artifact is a failure, never an empty success.
    current = current_inputs(H['items'])
    historical = historical_inputs(H['items'])
    discovery, _ = scoring.discovery_scores(current, cfg)
    legacy_cfg = cfg['legacy_v2']
    real2, _ = scoring.legacy_v2_real_scores(historical, legacy_cfg)
    wins = [w for w in ('overall', '30d', '7d') if any(p['win'].get(w) for p in current.values())]
    _, v1 = scoring.hype_v1(historical, wins)
    if a.compare_v2:
        rows = []
        for pid in sorted(current):
            old, new = real2[pid], discovery[pid]
            rows.append([H['items'][pid]['name'], old['score'], fmt(old['conf'], 2), new['score'], fmt(new['coverage'], 2),
                         ','.join(new['cohort']) or 'missing', new['usage_missingness'],
                         ','.join(sorted({m['metric_family'] or 'unknown' for m in new['metrics']})) or '—'])
        print('\n## Before/after: historical pooled Real → current discovery (not accuracy)')
        print(table(['project', 'v2 score', 'v2 completeness', 'current score', 'coverage', 'proxy cohort', 'usage', 'families'], rows))
    for w in wins:
        rows, _ = scoring.hype_window(current, w, discovery, cfg)
        old_rows, _ = scoring.legacy_v2_hype_window(historical, w, real2, legacy_cfg)
        print(f'\n## HYPE {w}: {len(rows)} current, {len(old_rows)} historical v2, {len(v1[w])} historical v1')
        mix = {label: sum(r['label'] == label for r in rows) for label in sorted({r['label'] for r in rows})}
        print('Current descriptive label mix:', mix)
        print(table(['project', 'attention', 'coverage', 'discovery', 'gap', 'label'],
                    [[H['items'][r['id']]['name'], r['score'], fmt(r['coverage'], 2), discovery[r['id']]['score'], r['gap'], r['label']]
                     for r in rows[:5]]))
        shortlist = [(it['qual_gap']['pos'], pid) for pid, it in H['items'].items() if it.get('qual_gap')]
        if os.path.exists(a.shortlist):
            names = {it['name'].lower(): pid for pid, it in H['items'].items()}
            shortlist = [(s.get('position'), names[s['name'].lower()]) for s in
                         load_any(a.shortlist).get('five_qualitative_hype_vs_evidence_gaps') or []
                         if s.get('name', '').lower() in names]
        if shortlist:
            by_id = {r['id']: r for r in rows}
            print(table(['shortlist', 'project', 'gap', 'label'],
                        [[pos, H['items'][pid]['name'], by_id.get(pid, {}).get('gap'), by_id.get(pid, {}).get('label')]
                         for pos, pid in sorted(shortlist)]))
    print('\nHYPE temporal stability: unavailable (single dossier snapshot). Capability, business validation, verification and independence: unqualified.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
