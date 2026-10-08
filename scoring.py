#!/usr/bin/env python3
"""scoring.py: the one shared scoring module (algorithm v2).

Used by run.py (Papers + GitHub tabs), hype_build.py (HYPE tab) and eval.py.
Pure functions, Python standard library only. Every weight and threshold lives in
scoring_config.json; METHODOLOGY.md explains each formula.

Pipeline for every score (papers, repo trust, Hype, Real):
  1. normalise each present signal against a fixed run-wide reference:
       u = min(1, log1p(v) / log1p(P95 of positive reference values)), 0 -> 0, ratios stay 0..1
  2. raw = 100 * sum(w_k * u_k) / sum(w_k)   over PRESENT signals only
  3. confidence c = sum(w_k * e_k over present) / sum(w_k over all)   (e_k = evidence quality 0..1)
  4. anti-noise multipliers (star/activity mismatch cap, solo repo, persistence, single-source attention)
  5. shrink toward the empirical-Bayes prior: score = prior + c * (raw - prior)
Missing values are never filled in: no signal at all -> score None (shown as '—').

score_run(features, version='1.0') reproduces the legacy v1 algorithm for eval.py.
"""
import bisect, hashlib, json, math, os

SCORING_VERSION = '2.0'
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, 'scoring_config.json')
PLATFORMS = ['X', 'Reddit', 'LinkedIn', 'HN', 'YouTube', 'Discord', 'Telegram']


def load_config(path=None):
    with open(path or CONFIG_PATH) as f:
        cfg = json.load(f)
    if str(cfg.get('version')) != SCORING_VERSION:
        raise ValueError(f"scoring_config.json version {cfg.get('version')} != scoring.py {SCORING_VERSION}")
    return cfg


def config_sha(path=None):
    with open(path or CONFIG_PATH, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


# ---------------------------------------------------------------- small helpers
def isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def clamp01(v):
    return max(0.0, min(1.0, float(v)))


def quantile(sorted_vals, q):
    """Nearest-rank quantile of an already sorted list."""
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, math.ceil(q * len(sorted_vals)) - 1))
    return sorted_vals[i]


def median(vals):
    v = sorted(x for x in vals if isnum(x))
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


class Ref:
    """Fixed reference distribution for one signal: the positive values of the whole tracked
    population in this run (not just one window's candidates), so a small window or one
    outlier cannot rescale everybody else."""

    def __init__(self, values, ncfg=None):
        ncfg = ncfg or {}
        self.method = ncfg.get('method', 'log_p95')
        self.pos = sorted(float(v) for v in values if isnum(v) and v > 0)
        if len(self.pos) >= ncfg.get('min_reference', 5):
            self.cap = quantile(self.pos, ncfg.get('winsor_quantile', 0.95))
        else:
            self.cap = self.pos[-1] if self.pos else None
        self.scale = math.log1p(self.cap) if self.cap else 0.0

    def unit(self, v):
        if not isnum(v):
            return None
        if v <= 0:
            return 0.0
        if self.method == 'percentile':
            if not self.pos:
                return 1.0
            lt = bisect.bisect_left(self.pos, v)
            eq = bisect.bisect_right(self.pos, v) - lt
            return clamp01(max(lt + 0.5 * eq, 0.5) / len(self.pos))
        if self.scale <= 0:
            return 1.0
        return min(1.0, math.log1p(v) / self.scale)


def combine(units, weights, evidence=None):
    """Weighted mean of present units (0..1) -> (raw 0..100 | None, confidence 0..1)."""
    num = den = ev = 0.0
    total = sum(w for w in weights.values() if w > 0)
    for k, w in weights.items():
        u = units.get(k)
        if u is None or w <= 0:
            continue
        num += w * u
        den += w
        ev += w * clamp01((evidence or {}).get(k, 1.0))
    if den == 0:
        return None, 0.0
    return 100.0 * num / den, (ev / total if total else 0.0)


def shrink(raw, conf, prior):
    """Bayesian linear shrinkage: missing evidence pulls the score toward the prior."""
    if raw is None:
        return None
    if prior is None:
        return raw
    return prior + clamp01(conf) * (raw - prior)


def resolve_prior(cfg, raws):
    p = cfg['shrinkage'].get('prior', 'median')
    return median(raws) if p == 'median' else float(p)


def r1(v):
    return None if v is None else round(v, 1)


def momentum_evidence(kind, mw, sh):
    """Evidence weight of a rate: 1 when measured over the full horizon (or since release for young items),
    rate_proxy_evidence for a pure per-day-since-release proxy, linear in between for blended rates."""
    if kind in ('rate-proxy', 'blended'):
        p = sh['rate_proxy_evidence']
        return p + (1 - p) * clamp01(mw or 0.0)
    return 1.0


def percentiles(raws):
    """{id: raw} -> {id: mid-rank percentile 0..100} (ties share the average rank)."""
    vals = sorted(v for v in raws.values() if v is not None)
    n = len(vals)
    out = {}
    for k, v in raws.items():
        if v is None or not n:
            out[k] = None
            continue
        lt = bisect.bisect_left(vals, v)
        eq = bisect.bisect_right(vals, v) - lt
        out[k] = 100.0 * (lt + 0.5 * eq) / n
    return out


# ---------------------------------------------------------------- GitHub repos (trust index)
ACTIVITY_KEYS = ('issues', 'prs', 'commits')


def _repo_values(rf, wname, days, cfg):
    w = (rf.get('win') or {}).get(wname) or {}
    a = rf.get('act') or {}
    act_on = days is None or days >= cfg['momentum']['activity_min_window_days']
    vals = {'stars': w.get('stars_rate'), 'contribs': rf.get('contributors'), 'contrib_growth': w.get('contrib_rate'),
            'issues': a.get('issues') if act_on else None, 'prs': a.get('prs') if act_on else None,
            'merge': a.get('merge') if act_on else None, 'commits': a.get('commits') if act_on else None}
    return vals, w


def repo_refs(R, cfg):
    n = cfg['normalization']
    w30 = [((rf.get('win') or {}).get('30d') or {}) for rf in R.values()]
    acts = [rf.get('act') or {} for rf in R.values()]
    return {'stars': Ref([w.get('stars_rate') for w in w30], n),
            'contrib_growth': Ref([w.get('contrib_rate') for w in w30], n),
            'contribs': Ref([rf.get('contributors') for rf in R.values()], n),
            'issues': Ref([a.get('issues') for a in acts], n), 'prs': Ref([a.get('prs') for a in acts], n),
            'commits': Ref([a.get('commits') for a in acts], n)}


def repo_raw(rf, wname, days, refs, cfg):
    """-> dict(raw, conf, flags, kind) or None when no signal is present."""
    c, sh = cfg['repos'], cfg['shrinkage']
    vals, w = _repo_values(rf, wname, days, cfg)
    u = {k: (None if v is None else clamp01(v)) if k == 'merge' else refs[k].unit(v) for k, v in vals.items()}
    ev, flags = {}, []
    if u['stars'] is not None:
        ev['stars'] = momentum_evidence(w.get('stars_kind'), w.get('stars_mw'), sh)
    # anti-noise 1: a star spike needs matching issue / PR / commit activity (star-farming pattern)
    acts = [u[k] for k in ACTIVITY_KEYS if u.get(k) is not None]
    if u['stars'] is not None and acts:
        cap = max(acts) + c['star_activity_max_gap']
        if u['stars'] > cap:
            u['stars'] = cap
            flags.append('stars>activity')
    raw, conf = combine(u, c['weights'], ev)
    if raw is None:
        return None
    mult = 1.0
    # anti-noise 2: stars but no outside contributors
    n = rf.get('contributors')
    if isnum(n) and n <= 1 and (u['stars'] or 0) >= c['solo_min_star_unit']:
        mult *= 1 - c['solo_penalty']
        flags.append('solo')
    # anti-noise 3: persistence across horizons (exact stargazer counts only)
    hr = [(rf.get('h') or {}).get(str(h)) for h in c['persistence_horizons']]
    hr = [x for x in hr if isnum(x)]
    if len(hr) >= 2 and max(hr) > 0:
        s = min(hr) / max(hr)
        mult *= 1 - c['persistence_weight'] * (1 - s)
        if s < c['spike_flag_below']:
            flags.append('spike')
    return dict(raw=raw * mult, conf=conf, flags=flags, kind=w.get('stars_kind'))


# ---------------------------------------------------------------- papers
def paper_refs(Pp, R, cfg):
    n = cfg['normalization']
    return {'upvotes': Ref([p.get('up_rate') for p in Pp.values()], n),
            'mentions': Ref([p.get('ment_rate') for p in Pp.values()], n),
            'repo_stars': Ref([((rf.get('win') or {}).get('30d') or {}).get('stars_rate') for rf in R.values()], n)}


def paper_raw(pf, refs, trust, cfg):
    c, sh = cfg['papers'], cfg['shrinkage']
    u, ev, flags = {}, {}, []
    u['upvotes'] = refs['upvotes'].unit(pf.get('up_rate'))
    if u['upvotes'] is not None:
        ev['upvotes'] = momentum_evidence(pf.get('up_kind'), pf.get('up_mw'), sh)
        k = c.get('upvote_evidence_k', 0)
        if k and isnum(pf.get('upvotes')):            # a handful of early votes is a small sample: n / (n + k)
            ev['upvotes'] *= pf['upvotes'] / (pf['upvotes'] + k)
            if pf['upvotes'] < k:
                flags.append('few-votes')
    t = trust.get(pf.get('repo')) if pf.get('repo') else None
    if t and t[0] is not None:
        u['code'], ev['code'] = t[0] / 100.0, t[1]
    elif isnum(pf.get('repo_star_rate')):
        u['code'], ev['code'] = refs['repo_stars'].unit(pf['repo_star_rate']), sh['stars_only_evidence']
    else:
        u['code'] = None
    u['mentions'] = refs['mentions'].unit(pf.get('ment_rate'))
    if u['mentions'] is not None:
        ev['mentions'] = momentum_evidence(pf.get('ment_kind'), pf.get('ment_mw'), sh)
    if u['mentions'] and pf.get('mentions') == 1:          # one HN post/comment is a single voice
        u['mentions'] *= c['single_post_factor']
        flags.append('single-post')
    raw, conf = combine(u, c['weights'], ev)
    if raw is None:
        return None
    return dict(raw=raw, conf=conf, flags=flags, kind=pf.get('up_kind'))


# ---------------------------------------------------------------- whole run (papers + repos)
def score_run(F, cfg=None, version=SCORING_VERSION):
    """F = features written by run.py (history/runs/*-features.json.gz).
    Returns {'trust': {repo: (score, conf)}, 'repos': {win: [rows]}, 'papers': {win: [rows]}, 'priors': {...}}
    Rows are sorted best-first; rows without any evidence come last with score None."""
    if str(version).startswith('1'):
        return score_run_v1(F)
    cfg = cfg or load_config()
    R, Pp = F['repos'], F['papers']
    rrefs = repo_refs(R, cfg)
    base = {fn: repo_raw(rf, '30d', 30, rrefs, cfg) for fn, rf in R.items()}
    prior_r = resolve_prior(cfg, [x['raw'] for x in base.values() if x])
    trust = {fn: ((r1(shrink(x['raw'], x['conf'], prior_r)), round(x['conf'], 2)) if x else (None, 0.0))
             for fn, x in base.items()}
    out = {'trust': trust, 'repos': {}, 'papers': {}, 'priors': {'repos': r1(prior_r)}}
    for wname, days in F['windows']:
        rows = []
        for fn, rf in R.items():
            if wname not in rf.get('cands', ()):
                continue
            x = repo_raw(rf, wname, days, rrefs, cfg)
            w = (rf.get('win') or {}).get(wname) or {}
            row = dict(id=fn, score=None, conf=0.0, raw=None, flags=[], kind=w.get('stars_kind'),
                       gained=w.get('gained'), gspan=w.get('gspan'), stars=rf.get('stars'))
            if x:
                row.update(score=r1(shrink(x['raw'], x['conf'], prior_r)), conf=round(x['conf'], 2),
                           raw=r1(x['raw']), flags=x['flags'])
            rows.append(row)
        rows.sort(key=lambda r: (r['score'] is None, -(r['score'] or 0), -(r['gained'] if isnum(r['gained']) else -1),
                                 -(r['stars'] or 0), r['id']))
        out['repos'][wname] = rows
    prefs = paper_refs(Pp, R, cfg)
    pbase = {pid: paper_raw(pf, prefs, trust, cfg) for pid, pf in Pp.items()}
    prior_p = resolve_prior(cfg, [x['raw'] for x in pbase.values() if x])
    out['priors']['papers'] = r1(prior_p)
    for wname, _ in F['windows']:
        rows = []
        for pid, pf in Pp.items():
            if wname not in pf.get('cands', ()):
                continue
            x = pbase[pid]
            row = dict(id=pid, score=None, conf=0.0, raw=None, flags=[], kind=pf.get('up_kind'), age=pf.get('age'))
            if x:
                row.update(score=r1(shrink(x['raw'], x['conf'], prior_p)), conf=round(x['conf'], 2),
                           raw=r1(x['raw']), flags=x['flags'])
            rows.append(row)
        rows.sort(key=lambda r: (r['score'] is None, -(r['score'] or 0), r['age'] if isnum(r['age']) else 1e9, r['id']))
        out['papers'][wname] = rows
    return out


# ---------------------------------------------------------------- legacy v1 (for eval.py only)
V1_TRUST = [('stars', .25), ('issues', .15), ('prs', .10), ('merge', .10), ('commits', .15), ('contribs', .10), ('contrib_growth', .15)]
V1_PAPER = [('up', .40), ('code', .35), ('ment', .25)]


def v1_norm(rates, signals, ratio_keys=()):
    """v1: z = log1p(rate)/max in the window; missing -> 0; score = 100 * raw / max raw."""
    mx = {}
    for k, _ in signals:
        mx[k] = 1.0 if k in ratio_keys else max((math.log1p(r[k]) for r in rates if isnum(r.get(k)) and r[k] > 0), default=0)
    raws, confs = [], []
    for r in rates:
        raw, present = 0.0, 0
        for k, w in signals:
            v = r.get(k)
            if not isnum(v):
                continue
            present += 1
            if k in ratio_keys:
                raw += w * clamp01(v)
            elif v > 0 and mx[k] > 0:
                raw += w * math.log1p(v) / mx[k]
        confs.append(round(present / len(signals), 2))
        raws.append(raw)
    m = max(raws, default=0)
    return [round(100 * x / m, 1) if m > 0 else 0.0 for x in raws], confs


def _v1_repo_rates(rf, wname, days):
    w = (rf.get('win') or {}).get(wname) or {}
    a = rf.get('act') or {}
    on = days is None or days >= 15
    return {'stars': w.get('stars_rate_v1'), 'issues': a.get('issues') if on else None, 'prs': a.get('prs') if on else None,
            'merge': a.get('merge') if on else None, 'commits': a.get('commits') if on else None,
            'contribs': rf.get('contributors'), 'contrib_growth': w.get('contrib_rate')}


def score_run_v1(F):
    R, Pp = F['repos'], F['papers']
    fns = list(R)
    rates = [_v1_repo_rates(R[fn], '30d', 30) for fn in fns]
    sc, cf = v1_norm(rates, V1_TRUST, ratio_keys={'merge'})
    trust = {}
    for fn, s, c, rt in zip(fns, sc, cf, rates):
        trust[fn] = (s if any(isnum(v) for v in rt.values()) else None, c)
    out = {'trust': trust, 'repos': {}, 'papers': {}, 'priors': {}}
    for wname, days in F['windows']:
        cand = [fn for fn in fns if wname in R[fn].get('cands', ())]
        rates = [_v1_repo_rates(R[fn], wname, days if days is not None else 90) for fn in cand]
        sc, cf = v1_norm(rates, V1_TRUST, ratio_keys={'merge'})
        rows = [dict(id=fn, score=s, conf=c, gained=((R[fn].get('win') or {}).get(wname) or {}).get('gained_v1'),
                     stars=R[fn].get('stars')) for fn, s, c in zip(cand, sc, cf)]
        rows.sort(key=lambda r: (-r['score'], -(r['gained'] if isnum(r['gained']) else -1), -(r['stars'] or 0), r['id']))
        out['repos'][wname] = rows
    for wname, _ in F['windows']:
        cand = [pid for pid in Pp if wname in Pp[pid].get('cands', ())]
        rates = []
        for pid in cand:
            pf = Pp[pid]
            t = trust.get(pf.get('repo'), (None, 0))[0] if pf.get('repo') else None
            sg = ((R.get(pf.get('repo')) or {}).get('win') or {}).get('30d', {}).get('stars_rate_v1') if pf.get('repo') else None
            rates.append({'up': pf.get('up_rate_v1'), 'code': t if t is not None else sg, 'ment': pf.get('ment_rate_v1')})
        sc, cf = v1_norm(rates, V1_PAPER)
        rows = [dict(id=pid, score=s, conf=c, age=Pp[pid].get('age')) for pid, s, c in zip(cand, sc, cf)]
        rows.sort(key=lambda r: (-r['score'], r['age'] if isnum(r['age']) else 1e9, r['id']))
        out['papers'][wname] = rows
    return out


# ---------------------------------------------------------------- HYPE (Hype vs Real)
def gap_label(gap, hype_conf, real_conf, cfg):
    g = cfg['gap']
    if gap is None or hype_conf is None or real_conf is None or hype_conf < g['min_confidence'] or real_conf < g['min_confidence']:
        return 'insufficient'
    return 'hype' if gap >= g['hype'] else ('sleeper' if gap <= g['sleeper'] else 'earned')


def real_scores(P, cfg):
    """P[pid]['real_in'] = {gh_trust: {v, conf}, paper: {v}, usage: {value, vendor}, discussion: {v}} (any may be None)."""
    n, sh = cfg['normalization'], cfg['shrinkage']
    ri = {pid: p.get('real_in') or {} for pid, p in P.items()}
    refs = {'paper': Ref([(r.get('paper') or {}).get('v') for r in ri.values()], n),
            'usage': Ref([(r.get('usage') or {}).get('value') for r in ri.values()], n),
            'discussion': Ref([(r.get('discussion') or {}).get('v') for r in ri.values()], n)}
    tmp = {}
    for pid, r in ri.items():
        u, ev = {'gh_trust': None}, {}
        t = r.get('gh_trust')
        if t and isnum(t.get('v')):
            u['gh_trust'], ev['gh_trust'] = clamp01(t['v'] / 100), (t.get('conf') if isnum(t.get('conf')) else 0.5)
        u['paper'] = refs['paper'].unit((r.get('paper') or {}).get('v'))
        us = r.get('usage')
        u['usage'] = refs['usage'].unit(us.get('value')) if us else None
        if us and us.get('vendor'):
            ev['usage'] = sh['vendor_claim_evidence']
        u['discussion'] = refs['discussion'].unit((r.get('discussion') or {}).get('v'))
        raw, conf = combine(u, cfg['real']['weights'], ev)
        tmp[pid] = (raw, conf, u)
    # common scale with Hype: percentile among the researched projects, so both priors are 50 (the median)
    pct = percentiles({pid: x[0] for pid, x in tmp.items()})
    prior = 50.0
    out = {}
    for pid, (raw, conf, u) in tmp.items():
        out[pid] = dict(score=r1(shrink(pct[pid], conf, prior)) if raw is not None else None, conf=round(conf, 2),
                        raw=r1(raw), pct=r1(pct[pid]), z={k: None if v is None else round(v, 3) for k, v in u.items()})
    return out, prior


def hype_window(P, w, real, cfg):
    """Hype score for one window. P[pid]['win'][w] = {mentions, voices, platforms, days}, P[pid]['age']."""
    c, n = cfg['hype'], cfg['normalization']
    cand = [pid for pid in P if (P[pid].get('win') or {}).get(w) and P[pid]['win'][w].get('mentions', 0) > 0]
    vel = {}
    for pid in cand:
        m = P[pid]['win'][w]
        age = P[pid].get('age')
        eff = max(1.0, min(m['days'], age if isnum(age) and age > 0 else m['days']))
        vel[pid] = m['mentions'] / eff
    rv, ro = Ref(vel.values(), n), Ref([P[pid]['win'][w]['voices'] for pid in cand], n)
    full = max(2, c['platforms_for_full_spread'])
    tmp = {}
    for pid in cand:
        m = P[pid]['win'][w]
        npl = len(m.get('platforms') or [])
        u = dict(velocity=rv.unit(vel[pid]), acceleration=m.get('acceleration'), voices=ro.unit(m['voices']),
                 spread=clamp01((npl - 1) / (full - 1)) if npl else 0.0)
        raw, conf = combine(u, c['weights'])
        flags, mult = [], 1.0
        if npl <= 1:
            mult *= 1 - c['single_platform_penalty']; flags.append('single-platform')
        if (m['voices'] or 0) <= c['few_voices']:
            mult *= 1 - c['few_voices_penalty']; flags.append('few-voices')
        tmp[pid] = (raw * mult, conf, u, flags)
    pct = percentiles({pid: x[0] for pid, x in tmp.items()})      # same percentile scale as Real
    prior = 50.0
    rows = []
    for pid, (raw, conf, u, flags) in tmp.items():
        sc = r1(shrink(pct[pid], conf, prior))
        rl = real.get(pid) or {}
        gap = r1(sc - rl['score']) if rl.get('score') is not None else None
        rows.append(dict(id=pid, score=sc, conf=round(conf, 2), raw=r1(raw), pct=r1(pct[pid]), vel=round(vel[pid], 3), gap=gap,
                         label=gap_label(gap, conf, rl.get('conf'), cfg), flags=flags,
                         z={k: None if v is None else round(v, 3) for k, v in u.items()}))
    rows.sort(key=lambda r: (-r['score'], -P[r['id']]['win'][w]['mentions'], r['id']))
    return rows, prior


# ---- legacy v1 HYPE (eval.py only)
def _lognorm(vals):
    mx = max((math.log1p(v) for v in vals if isnum(v) and v > 0), default=0)
    return [None if not isnum(v) else (math.log1p(v) / mx if v > 0 and mx > 0 else 0.0) for v in vals]


def _v1_combine(zs, weights):
    num = den = 0.0; present = 0
    for k, w in weights.items():
        z = zs.get(k)
        if z is None:
            continue
        num += w * z; den += w; present += 1
    return (round(100 * num / den, 1) if den else None), round(present / len(weights), 2)


def hype_v1(P, windows):
    RW = {'gh_trust': .30, 'paper': .20, 'usage': .30, 'discussion': .20}
    HW = {'velocity': .35, 'acceleration': .25, 'voices': .20, 'spread': .20}
    ids = list(P)
    ri = [P[i].get('real_in') or {} for i in ids]
    zt = [None if not r.get('gh_trust') or not isnum(r['gh_trust'].get('v1', r['gh_trust'].get('v'))) else
          clamp01(r['gh_trust'].get('v1', r['gh_trust'].get('v')) / 100) for r in ri]
    zp = _lognorm([(r.get('paper') or {}).get('v') for r in ri])
    zu = _lognorm([(r.get('usage') or {}).get('value') for r in ri])
    zu = [None if z is None else z * (0.5 if r['usage'].get('vendor') else 1) for z, r in zip(zu, ri)]
    zd = _lognorm([(r.get('discussion') or {}).get('v') for r in ri])
    real = {}
    for k, i in enumerate(ids):
        sc, cf = _v1_combine(dict(gh_trust=zt[k], paper=zp[k], usage=zu[k], discussion=zd[k]), RW)
        real[i] = dict(score=sc if cf > 0 else None, conf=cf)
    out = {}
    for w in windows:
        cand = [i for i in ids if (P[i].get('win') or {}).get(w) and P[i]['win'][w].get('mentions', 0) > 0]
        vel, voi, spr = [], [], []
        for i in cand:
            m = P[i]['win'][w]; age = P[i].get('age')
            eff = max(1.0, min(m['days'], age if isnum(age) and age > 0 else m['days']))
            vel.append(m['mentions'] / eff); voi.append(m['voices']); spr.append(len(m.get('platforms') or []))
        zv, zo = _lognorm(vel), _lognorm(voi)
        mx = max(spr, default=0) or 1
        rows = []
        for k, i in enumerate(cand):
            sc, cf = _v1_combine(dict(velocity=zv[k], acceleration=None, voices=zo[k], spread=spr[k] / mx), HW)
            rs = real[i]['score']
            gap = round(sc - rs, 1) if rs is not None else None
            lab = None if gap is None else ('hype' if gap >= 15 else 'sleeper' if gap <= -15 else 'earned')
            rows.append(dict(id=i, score=sc, conf=cf, gap=gap, label=lab))
        rows.sort(key=lambda r: (-r['score'], -P[r['id']]['win'][w]['mentions'], r['id']))
        out[w] = rows
    return real, out


# ---------------------------------------------------------------- movement (rank arrows)
def movement(cur, prev, cfg, comparable=True):
    """cur: [(id, score)] in rank order; prev: {id: (rank, score)} from the previous run of the same view.
    Ranks are compared only among items present in both lists; small changes are held as '=' (hysteresis).
    Returns one dict per row: {'s': 'up'|'down'|'same'|'new'|'reset', 'd': int, 'why': str}."""
    m = cfg['movement']
    if not prev:
        return [{'s': 'new', 'why': 'no previous run'} for _ in cur]
    if not comparable:
        return [{'s': 'reset', 'why': 'scoring version changed since the previous run'} for _ in cur]
    common = [i for i, _ in cur if i in prev]
    overlap = len(common) / max(1, min(len(cur), len(prev)))
    if overlap < m['min_overlap']:
        why = f'candidate set changed a lot ({round(100 * overlap)}% overlap with the previous run)'
        return [{'s': 'new', 'why': why} for _ in cur]
    cur_pos = {i: k for k, i in enumerate(common)}
    prev_pos = {i: k for k, i in enumerate(sorted(common, key=lambda i: prev[i][0]))}
    out = []
    for i, sc in cur:
        if i not in prev:
            out.append({'s': 'new', 'why': 'not in the previous top list'})
            continue
        d = prev_pos[i] - cur_pos[i]
        ps = prev[i][1]
        ds = sc - ps if isnum(sc) and isnum(ps) else None
        if abs(d) < m['min_rank_change'] or (ds is not None and abs(ds) < m['min_score_change']):
            out.append({'s': 'same', 'd': d})
        else:
            out.append({'s': 'up' if d > 0 else 'down', 'd': abs(d)})
    return out


# ---------------------------------------------------------------- evaluation helpers
def spearman(xs, ys):
    """Spearman rank correlation with average ranks for ties; None if < 3 pairs or no variance."""
    pairs = [(x, y) for x, y in zip(xs, ys) if isnum(x) and isnum(y)]
    if len(pairs) < 3:
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return rk
    a, b = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return None if va == 0 or vb == 0 else cov / math.sqrt(va * vb)
