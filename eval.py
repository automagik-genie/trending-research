#!/usr/bin/env python3
"""eval.py: how does the current scoring behave? Paste its output into every weight/method PR.

  python eval.py                                   # last two feature snapshots in history/runs/ + web/hype.json
  python eval.py --features OLD NEW [--hype web/hype.json] [--shortlist hype/hype_summary.json]
  python eval.py --features tests/fixtures/features_a.json tests/fixtures/features_b.json \
                 --hype tests/fixtures/hype_small.json       # tiny fixture (CI smoke test)

Reports, for the legacy v1 algorithm and for the current scoring.py + scoring_config.json:
  1. stability: Spearman correlation between the scores of the newer run's top-100 and the same items'
     scores in the older run, plus top-100 overlap (per tab and window);
  2. evidence: share of top-100 rows whose confidence >= eval.confidence_threshold;
  3. HYPE: where the research's qualitative hype-vs-evidence shortlist lands under v1 vs v2, the label
     mix, the top 5 by Hype and the largest gaps.
Nothing is estimated or filled in: when an input is missing the line says so.
"""
import argparse, glob, gzip, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scoring


def load_any(path):
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'rt') as f:
        return json.load(f)


def fmt(v, nd=1):
    if v is None:
        return '—'
    return f'{v:.{nd}f}' if isinstance(v, float) else str(v)


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|']
    out += ['| ' + ' | '.join(fmt(c) if not isinstance(c, str) else c for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def stability(old, new, n):
    top = [r for r in new if r['score'] is not None][:n]
    old_s = {r['id']: r['score'] for r in old if r['score'] is not None}
    old_top = {r['id'] for r in [r for r in old if r['score'] is not None][:n]}
    pairs = [(old_s[r['id']], r['score']) for r in top if r['id'] in old_s]
    rho = scoring.spearman([p[0] for p in pairs], [p[1] for p in pairs])
    overlap = len({r['id'] for r in top} & old_top) / max(1, len(top)) if top else None
    return rho, len(pairs), overlap, len(top)


def conf_share(rows, n, thr):
    top = [r for r in rows if r['score'] is not None][:n]
    return (sum(1 for r in top if (r.get('conf') or 0) >= thr) / len(top)) if top else None, len(top)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--features', nargs=2, metavar=('OLD', 'NEW'))
    ap.add_argument('--hype', default=os.path.join(HERE, 'web', 'hype.json'))
    ap.add_argument('--shortlist', default=os.path.join(HERE, 'hype', 'hype_summary.json'))
    ap.add_argument('--config', default=None)
    a = ap.parse_args(argv)
    cfg = scoring.load_config(a.config)
    ev = cfg['eval']
    N, thr = ev['top_n'], ev['confidence_threshold']
    print(f'# eval.py: scoring v{scoring.SCORING_VERSION} (config {scoring.config_sha(a.config)}) vs legacy v1\n')

    paths = a.features or sorted(glob.glob(os.path.join(HERE, 'history', 'runs', '*-features.json.gz')))[-2:]
    if len(paths) < 2:
        print('## 1-2. Papers / GitHub: n/a: need two feature snapshots (run `python run.py` twice, or pass --features OLD NEW)\n')
    else:
        F_old, F_new = load_any(paths[0]), load_any(paths[1])
        print(f'Feature snapshots: OLD {os.path.basename(paths[0])} (as of {F_old["asof"]}), '
              f'NEW {os.path.basename(paths[1])} (as of {F_new["asof"]})\n')
        S = {v: (scoring.score_run(F_old, cfg, v), scoring.score_run(F_new, cfg, v)) for v in ('1.0', scoring.SCORING_VERSION)}
        print(f'## 1. Stability between the two runs (Spearman of top-{N} scores; overlap = share of the new top-{N} also in the old top-{N})\n')
        rows = []
        for tab in ('papers', 'repos'):
            for w in ev['windows']:
                line = [tab, w]
                for v in ('1.0', scoring.SCORING_VERSION):
                    rho, n, ov, nt = stability(S[v][0][tab].get(w, []), S[v][1][tab].get(w, []), N)
                    line += [fmt(rho, 3), f'{n}/{nt}', fmt(ov, 2)]
                rows.append(line)
        print(table(['tab', 'window', 'v1 rho', 'v1 n', 'v1 overlap', 'v2 rho', 'v2 n', 'v2 overlap'], rows))
        print(f'\n## 2. Evidence: share of the NEW top-{N} with confidence >= {thr}\n')
        print('(v1 confidence = share of signals present; v2 = evidence-weighted share, so rate proxies and vendor claims count less)\n')
        rows = []
        for tab in ('papers', 'repos'):
            for w in ev['windows']:
                s1, n1 = conf_share(S['1.0'][1][tab].get(w, []), N, thr)
                s2, n2 = conf_share(S[scoring.SCORING_VERSION][1][tab].get(w, []), N, thr)
                top2 = [r for r in S[scoring.SCORING_VERSION][1][tab].get(w, []) if r['score'] is not None][:N]
                proxy = sum(1 for r in top2 if r.get('kind') == 'rate-proxy')
                flags = sum(1 for r in top2 if r.get('flags'))
                rows.append([tab, w, fmt(s1, 2), fmt(s2, 2), f'{proxy}/{len(top2)}', f'{flags}/{len(top2)}'])
        print(table(['tab', 'window', 'v1 share', 'v2 share', 'v2 rate-proxy rows', 'v2 anti-noise flagged'], rows))
        print()

    # ---- HYPE
    if not os.path.exists(a.hype):
        print(f'## 3. HYPE: n/a ({a.hype} not found)')
        return 0
    H = load_any(a.hype)
    P = {pid: dict(win=it['win'], age=it.get('age_at_cutoff'), real_in=it.get('real_in') or {}) for pid, it in H['items'].items()}
    wins = [w for w in ('overall', '30d', '7d') if any((p['win'] or {}).get(w) for p in P.values())]
    real1, hy1 = scoring.hype_v1(P, wins)
    real2, _ = scoring.real_scores(P, cfg)
    hy2 = {w: scoring.hype_window(P, w, real2, cfg)[0] for w in wins}
    names = {it['name'].lower(): pid for pid, it in H['items'].items()}
    short = []
    if os.path.exists(a.shortlist):
        short = [(g.get('position'), g['name']) for g in (load_any(a.shortlist).get('five_qualitative_hype_vs_evidence_gaps') or [])]
        src = os.path.basename(a.shortlist)
    if not short:
        short = sorted((it['qual_gap']['pos'], it['name']) for it in H['items'].values() if it.get('qual_gap'))
        src = 'qual_gap fields in ' + os.path.basename(a.hype)
    print(f'## 3. HYPE: research shortlist (five_qualitative_hype_vs_evidence_gaps, from {src}) under v1 vs v2\n')
    print(f'v2 labels need both confidences >= {cfg["gap"]["min_confidence"]}; otherwise "insufficient". Gap rank = position when all rows of the window are sorted by gap (1 = most hype-leaning).\n')
    for w in wins:
        r1 = {r['id']: r for r in hy1[w]}
        r2 = {r['id']: r for r in hy2[w]}
        g1 = {r['id']: k for k, r in enumerate(sorted([r for r in hy1[w] if r['gap'] is not None], key=lambda r: -r['gap']), 1)}
        g2 = {r['id']: k for k, r in enumerate(sorted([r for r in hy2[w] if r['gap'] is not None], key=lambda r: -r['gap']), 1)}
        rows = []
        for pos, name in short:
            pid = names.get(name.lower())
            a1, a2 = r1.get(pid) or {}, r2.get(pid) or {}
            if not pid or (not a1 and not a2):
                rows.append([str(pos), name] + ['not in window'] + [''] * 9); continue
            rows.append([str(pos), name, fmt(a1.get('score')), fmt((real1.get(pid) or {}).get('score')), fmt(a1.get('gap')),
                         a1.get('label') or '—', f'{g1.get(pid, "—")}/{len(g1)}',
                         fmt(a2.get('score')), f"{fmt(real2[pid]['score'])} ({fmt(real2[pid]['conf'], 2)})", fmt(a2.get('gap')),
                         a2.get('label') or '—', f'{g2.get(pid, "—")}/{len(g2)}'])
        print(f'### window {w}\n')
        print(table(['#', 'project', 'v1 Hype', 'v1 Real', 'v1 Gap', 'v1 label', 'v1 gap rank',
                     'v2 Hype', 'v2 Real (conf)', 'v2 Gap', 'v2 label', 'v2 gap rank'], rows))
        mix1, mix2 = {}, {}
        for r in hy1[w]: mix1[r['label'] or 'no Real'] = mix1.get(r['label'] or 'no Real', 0) + 1
        for r in hy2[w]: mix2[r['label']] = mix2.get(r['label'], 0) + 1
        print(f'\nlabel mix ({len(hy2[w])} rows): v1 {dict(sorted(mix1.items()))} · v2 {dict(sorted(mix2.items()))}')
        hi1 = max((real1[r["id"]]["score"] or 0, r['id']) for r in hy1[w] if real1[r['id']]['conf'] <= 0.25) if any(real1[r['id']]['conf'] <= 0.25 and real1[r['id']]['score'] is not None for r in hy1[w]) else None
        if hi1:
            print(f'max Real among rows with v1 confidence <= 25%: v1 {hi1[0]} ({H["items"][hi1[1]]["name"]}) -> v2 {real2[hi1[1]]["score"]} (conf {real2[hi1[1]]["conf"]})')
        sh2 = sum(1 for r in hy2[w] if r['conf'] >= thr and (real2[r['id']]['conf'] or 0) >= thr)
        print(f'rows with both v2 confidences >= {thr}: {sh2}/{len(hy2[w])}')
        top = hy2[w][:5]
        print(f'top 5 by v2 Hype: ' + '; '.join(f"{H['items'][r['id']]['name']} {r['score']} (conf {r['conf']}, gap {fmt(r['gap'])}, {r['label']})" for r in top))
        gaps = sorted([r for r in hy2[w] if r['gap'] is not None], key=lambda r: -r['gap'])
        lab = [r for r in gaps if r['label'] != 'insufficient']
        print('largest v2 gaps (any label): ' + '; '.join(f"{H['items'][r['id']]['name']} {r['gap']:+} ({r['label']})" for r in gaps[:5]))
        print('largest v2 gaps (labelled): ' + ('; '.join(f"{H['items'][r['id']]['name']} {r['gap']:+} ({r['label']})" for r in lab[:5]) or 'none'))
        print('most negative v2 gaps (labelled): ' + ('; '.join(f"{H['items'][r['id']]['name']} {r['gap']:+} ({r['label']})" for r in lab[::-1][:3]) or 'none'))
        print()
    print('HYPE stability across runs: n/a: the research dossier is a single snapshot (no repeated measurements yet).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
