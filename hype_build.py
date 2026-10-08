#!/usr/bin/env python3
"""HYPE tab builder: hype/hype_research.json -> web/hype.json (compact) + rank history.

Run standalone:  python3 /workspace/trending/hype_build.py [--no-history]
run.py calls build(con=..., run_id=...) automatically when hype/hype_research.json exists,
so dropping in a new research file updates the tab on the next run.

NEVER INVENTS NUMBERS. Unknown -> null (rendered '—'). All social counts are the research
agent's *sampled* observations (purposive, not exhaustive, no global counts).

HYPE score (0-100) = attention velocity, a SAMPLED PROXY. Each component z is 0..1:
  mention velocity   .35  sampled posts in window / effective days (min(window, days since first seen))
  acceleration       .25  needs a growth series -> MISSING in this dataset (no repeated snapshots;
                          HN sample is "first 100 hits by date", so a recent/older ratio would be biased)
  unique voices      .20  sampled unique authors in window (summed over platforms)
  cross-platform     .20  platforms with >=1 sampled post in window
  Rates/counts are log-scaled vs the max in the window: z = log1p(v)/max log1p(v); spread = n/max n.
  hype = 100 * sum(w*z over PRESENT components) / sum(w of present)  (weights renormalised)
  hype_confidence = present components / 4.

REAL score (0-100) = substance, window-independent:
  GitHub trust index  .30  the GitHub tab's trust score for the same repo (run.py repo_trust map,
                           else data.json GitHub rows 30d -> overall); repo not tracked -> missing
  paper traction      .20  Hugging Face paper upvotes for the linked arXiv id (pipeline caches,
                           else HF API); non-arXiv / not on HF -> missing
  real usage          .30  largest sourced download/user count in real_traction_signals
                           (platform observations preferred; vendor claims count at half weight)
  developer discussion .20 comments on the sampled HN stories (research's HN sample)
  Same log scaling within the HYPE set; weights renormalised over present ones; confidence = present/4.

GAP = hype - real (per window). >= +15 likely hype, <= -15 underrated sleeper, else earned.
"""
import os, sys, re, json, math, time, sqlite3, glob, urllib.request, urllib.error
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
WEB, HIST, CACHE = (os.path.join(BASE, d) for d in ('web', 'history', 'cache'))
RESEARCH = os.path.join(BASE, 'hype', 'hype_research.json')
SUMMARY = os.path.join(BASE, 'hype', 'hype_summary.json')
OUT = os.path.join(WEB, 'hype.json')
TZ = ZoneInfo('America/Sao_Paulo')
UA = 'felipe-ai-trend-tracker/1.0 (personal research dashboard)'

PLATFORMS = ['X', 'Reddit', 'LinkedIn', 'HN', 'YouTube', 'Discord', 'Telegram']
RES_WINDOWS = [('1d', 1), ('7d', 7), ('30d', 30), ('90d', 90)]      # windows the research measured
ALL_WINDOWS = ['1d', '7d', '30d', '90d', '180d', '1y', 'overall']
HYPE_W = [('velocity', .35), ('acceleration', .25), ('voices', .20), ('spread', .20)]
REAL_W = [('gh_trust', .30), ('paper', .20), ('usage', .30), ('discussion', .20)]
GAP_HYPE, GAP_SLEEPER = 15, -15
TOPN = 100
USAGE_TYPES = {'npm_downloads', 'pypi_downloads', 'hf_model_downloads', 'representative_checkpoint_downloads',
               'extension_users', 'package_downloads', 'downloads', 'app_downloads',
               'claimed_monthly_active_users', 'reported_users', 'creators', 'business_clients'}
VENDOR_DISCOUNT = 0.5

def P(s):
    if not s: return None
    try:
        x = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        try: x = datetime.fromisoformat(str(s)[:10])
        except ValueError: return None
    return x if x.tzinfo else x.replace(tzinfo=timezone.utc)

def load(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def save(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f: json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]
def cut(s, n): s = ' '.join(str(s or '').split()); return s if len(s) <= n else s[:n - 1] + '…'
def is_url(u): return isinstance(u, str) and u.startswith('http')
def urls(lst, n=8): return [u for u in (lst or []) if is_url(u)][:n]
def arxiv_id(u):
    m = re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})', u or '')
    return m.group(1) if m else None
def repo_name(u):
    m = re.search(r'github\.com/([^/\s]+/[^/\s#?]+)', u or '')
    return m.group(1).removesuffix('.git').lower() if m else None

# ---------------------------------------------------------------- joins with the other tabs
def gh_trust_map(repo_trust=None):
    """full_name(lower) -> (trust 0..100, confidence, source). Prefers run.py's all-repo map."""
    rt = repo_trust or (load(os.path.join(CACHE, 'repo_trust.json'), None) or {}).get('repos')
    if rt:
        return {k.lower(): (v['trust'], v.get('confidence'), 'GitHub tab trust index (30d)')
                for k, v in rt.items() if v.get('trust') is not None and v.get('confidence')}
    # Fallback: scores shown on the GitHub tab (any view; same score within a window). A row whose
    # confidence is 0 had no trust signal at all, so it is treated as missing, not as a measured 0.
    D = load(os.path.join(WEB, 'data.json'), {})
    out = {}
    for w in ('30d', 'overall', '90d', '7d', '180d', '1y', '1d'):
        for view in ((D.get('repos') or {}).get(w) or {}).values():
            for r in view.get('rows', []):
                if r.get('confidence'):
                    out.setdefault(r['id'].lower(), (r['score'], r['confidence'], f'GitHub tab score ({w})'))
    return out

def hf_upvotes(ids):
    """arXiv id -> (upvotes|None, source_url). Uses the pipeline's HF caches, then the HF API (cached 24h)."""
    known = {}
    for f in glob.glob(os.path.join(CACHE, 'hf_month_*.json')) + glob.glob(os.path.join(CACHE, 'hf_search_*.json')):
        for it in (load(f, {}) or {}).get('items', []):
            if it.get('id') and it.get('upvotes') is not None: known[it['id']] = it['upvotes']
    for pid, c in (load(os.path.join(CACHE, 'hf_papers.json'), {}) or {}).items():
        if c.get('data') and c['data'].get('upvotes') is not None: known[pid] = c['data']['upvotes']
    own_p = os.path.join(CACHE, 'hype_hf_papers.json')
    own = load(own_p, {})
    out, fetched = {}, 0
    for pid in ids:
        src = f'https://huggingface.co/papers/{pid}'
        if pid in known: out[pid] = (known[pid], src); continue
        c = own.get(pid)
        if not c or time.time() - c['ts'] > 24 * 3600:
            try:
                req = urllib.request.Request(f'https://huggingface.co/api/papers/{pid}', headers={'User-Agent': UA})
                with urllib.request.urlopen(req, timeout=20) as r: d = json.loads(r.read())
                c = {'ts': time.time(), 'upvotes': d.get('upvotes')}
            except urllib.error.HTTPError as e:
                c = {'ts': time.time(), 'upvotes': None, 'note': f'HTTP {e.code}'} if e.code == 404 else c
            except Exception:
                pass
            if c: own[pid] = c; fetched += 1
        out[pid] = ((c or {}).get('upvotes'), src)
    if fetched and os.path.isdir(CACHE): save(own_p, own)
    return out

# ---------------------------------------------------------------- scoring helpers
def lognorm(vals):
    mx = max((math.log1p(v) for v in vals if v is not None and v > 0), default=0)
    return [None if v is None else (math.log1p(v) / mx if v > 0 and mx > 0 else 0.0) for v in vals]

def combine(zs, weights):
    num = den = 0.0; present = 0
    for (k, w) in weights:
        z = zs.get(k)
        if z is None: continue
        num += w * z; den += w; present += 1
    return (round(100 * num / den, 1) if den else None), round(present / len(weights), 2)

def gap_label(g):
    if g is None: return None
    return 'hype' if g >= GAP_HYPE else ('sleeper' if g <= GAP_SLEEPER else 'earned')

# ---------------------------------------------------------------- compact per-project record
def likes_of(p):
    cm = (p.get('component_measurements') or {}).get('likes') or {}
    if cm.get('value') is not None: return cm['value']
    return (p.get('engagement') or {}).get('likes')

def top_posts(posts, n=6):
    def key(p):
        e = p.get('engagement') or {}
        return -(likes_of(p) or e.get('score') or p.get('reactions') or e.get('views') or 0)
    out = []
    for p in sorted(posts, key=key)[:n]:
        e = p.get('engagement') or {}
        out.append(dict(pl=p.get('platform'), au=p.get('author'), d=(p.get('date_utc') or '')[:10],
                        likes=likes_of(p), score=e.get('score'), cm=e.get('comments'), rp=e.get('replies'),
                        views=e.get('views'), url=p.get('url') if is_url(p.get('url')) else p.get('source_url'),
                        t=cut(p.get('title') or p.get('content_excerpt') or p.get('text_excerpt') or p.get('context'), 180)))
    return out

def usage_signal(sigs):
    best = None
    for s in sigs:
        if s.get('type') not in USAGE_TYPES: continue
        v = s.get('value')
        if isinstance(v, dict): v = v.get('last_month')
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0: continue
        if not is_url(s.get('source_url')): continue
        vendor = s.get('verification') == 'vendor_claim'
        rank = (0 if vendor else 1, v)
        if best is None or rank > best[0]:
            best = (rank, dict(value=v, unit=s.get('unit'), type=s.get('type'), vendor=vendor, url=s['source_url']))
    return best[1] if best else None

def project(it, cutoff):
    L = it.get('links') or {}
    tl = it.get('timeline') or {}
    fs = tl.get('first_seen') or {}
    vo = it.get('viral_origin') or {}
    cand = vo.get('candidate_earliest_observed') or {}
    co = it.get('coordination_signals') or {}
    gh = it.get('github_snapshot') or {}
    hn = it.get('hn_sampling') or {}
    rk = it.get('ranking') or {}
    qg = rk.get('qualitative_hype_gap') or {}
    rn = it.get('ranking_notes') or {}
    disclosed = 'disclos' in (co.get('assessment') or '').lower() or any(
        re.search(r'#ad\b|sponsored|paid partnership', (e.get('evidence_excerpt') or '') + ' ' + (e.get('observation') or ''), re.I)
        and not re.search(r'not evidence|not proof|payment not established', e.get('observation') or '', re.I)
        for e in co.get('evidence') or [])
    return dict(
        name=it['name'], aliases=[a for a in (it.get('aliases') or [])[:6] if isinstance(a, str)],
        links={k: L.get(k) for k in ('site', 'x_handle', 'repo', 'paper', 'hf', 'github_org') if is_url(L.get(k))},
        category=it.get('category'), ptags=(it.get('paradigm_tags') or [])[:6], seed=bool(it.get('seed')),
        summary=it.get('exec_summary'), summary_urls=urls(it.get('exec_summary_source_urls'), 8),
        first_seen=fs.get('date_utc'), first_seen_url=fs.get('source_url'), first_seen_meaning=fs.get('meaning'),
        peak=tl.get('peak_date_utc'), peak_reason=tl.get('peak_reason'),
        status=(tl.get('current_status') or {}).get('text'), status_urls=urls((tl.get('current_status') or {}).get('source_urls'), 6),
        viral=dict(platform=vo.get('platform'), post=vo.get('post_url'), account=vo.get('account'),
                   followers=vo.get('follower_count'), reason=vo.get('reason'),
                   cand_platform=cand.get('platform'), cand_post=cand.get('post_url'), cand_account=cand.get('account')),
        coord=dict(assessment=co.get('assessment'), limitations=co.get('limitations'), disclosed=disclosed,
                   evidence=[dict(t=cut(e.get('evidence_excerpt') or e.get('observation'), 300), url=e.get('source_url'),
                                  d=(e.get('date_utc') or '')[:10]) for e in co.get('evidence') or []]),
        traction=[dict(type=s.get('type'), value=s.get('value'), unit=s.get('unit'), ver=s.get('verification'),
                       asof=(s.get('as_of_utc') or s.get('period_end_utc') or '')[:10] or None, url=s.get('source_url'),
                       notes=cut(s.get('notes'), 220)) for s in it.get('real_traction_signals') or []],
        skeptic=[dict(claim=cut(s.get('claim'), 400), by=cut(s.get('attribution'), 160), d=(s.get('date_utc') or '')[:10] or None,
                      url=s.get('source_url') or (urls(s.get('source_urls'), 1) or [None])[0]) for s in it.get('skeptic_signals') or []],
        posts=top_posts(it.get('observed_social_posts') or []),
        gh=dict(stars=gh.get('stars'), forks=gh.get('forks'), created=(gh.get('repo_created_at_utc') or '')[:10] or None,
                pushed=(gh.get('last_pushed_at_utc') or '')[:10] or None, observed=(gh.get('observed_at_utc') or '')[:10] or None,
                url=gh.get('source_url')) if gh.get('stars') is not None else None,
        hn=dict(returned=hn.get('returned_hits'), reported=hn.get('reported_search_hits'),
                accepted=hn.get('accepted_exact_phrase_stories'), url=hn.get('api_url'), capped=(hn.get('returned_hits') or 0) >= 100),
        proxy=dict(rank=rk.get('momentum_proxy_rank'), score=rk.get('momentum_proxy_score')) if rk.get('momentum_proxy_score') is not None else None,
        qual_gap=dict(pos=qg.get('position'), text=qg.get('assessment'), urls=urls(qg.get('source_urls'), 4)) if qg else None,
        notes=dict(momentum=rn.get('momentum_evidence'), traction=rn.get('traction_evidence'), gap=rn.get('hype_gap_evidence'),
                   confidence=rn.get('confidence')),
    )

# ---------------------------------------------------------------- history
def db_connect():
    os.makedirs(HIST, exist_ok=True)
    con = sqlite3.connect(os.path.join(HIST, 'trending.db'))
    con.executescript('''
    CREATE TABLE IF NOT EXISTS runs(run_id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, ts_local TEXT, seconds REAL, sources TEXT);
    CREATE TABLE IF NOT EXISTS ranks(run_id INT, tab TEXT, win TEXT, item_id TEXT, rank INT, score REAL);
    CREATE INDEX IF NOT EXISTS i_ranks ON ranks(tab, win, run_id);''')
    return con

def prev_hype(con, before=None):
    q = "SELECT MAX(run_id) FROM ranks WHERE tab='hype'" + (' AND run_id < ?' if before else '')
    r = con.execute(q, (before,) if before else ()).fetchone()[0]
    if r is None: return {}, None
    out = {}
    for tab, win, item, rank in con.execute("SELECT tab, win, item_id, rank FROM ranks WHERE run_id=? AND (tab='hype' OR tab LIKE 'hype|%')", (r,)):
        out.setdefault((tab, win), {})[item] = rank
    ts = con.execute('SELECT ts_local FROM runs WHERE run_id=?', (r,)).fetchone()
    return out, ts[0] if ts else None

# ---------------------------------------------------------------- main build
def build(con=None, run_id=None, repo_trust=None, tagger=None, tags=None, record=True, log=print):
    t0 = time.time()
    research = load(RESEARCH, None)
    if not isinstance(research, list) or not research:
        raise RuntimeError(f'{RESEARCH} missing or not a list of projects')
    summ = load(SUMMARY, {}) or {}
    if tagger is None or tags is None:
        sys.path.insert(0, BASE)
        from run import tag_for as tagger, TAGS as tags   # same paradigm buckets as the other tabs
    cutoff = P(summ.get('content_cutoff_utc') or ((research[0].get('research_scope') or {}).get('cutoff_utc'))) or datetime.now(timezone.utc)
    lookback = P(summ.get('lookback_start_utc') or (research[0].get('research_scope') or {}).get('lookback_start_utc'))
    look_days = max(1, round((cutoff - lookback).total_seconds() / 86400)) if lookback else 365

    items, ids = {}, []
    trust = gh_trust_map(repo_trust)
    papers = {}
    for it in research:
        pid = arxiv_id((it.get('links') or {}).get('paper'))
        if pid: papers[pid] = None
    ups = hf_upvotes(list(papers))
    used_slugs = set()
    raw_real = []
    for it in research:
        pid = slug(it['name'])
        while pid in used_slugs: pid += '-x'
        used_slugs.add(pid); ids.append(pid)
        rec = project(it, cutoff)
        text = ' '.join([it['name'], it.get('category') or '', ' '.join(it.get('paradigm_tags') or [])])
        rec['tag'] = tagger(text, it.get('exec_summary') or '') or 'other'
        fs = P(rec['first_seen'])
        rec['age_at_cutoff'] = round((cutoff - fs).total_seconds() / 86400, 1) if fs else None
        # ---- per-window sampled metrics (research windows) + overall from the post list
        M = it.get('metrics') or {}
        win = {}
        for w, days in RES_WINDOWS:
            per = {}
            have = False
            for pl in PLATFORMS:
                s = ((M.get(pl) or {}).get(w) or {}).get('sample')
                if s is None: continue
                have = True
                per[pl] = (s.get('observed_post_count') or 0, s.get('observed_unique_authors') or 0)
            if not have: win[w] = None; continue
            win[w] = dict(mentions=sum(v[0] for v in per.values()), voices=sum(v[1] for v in per.values()),
                          platforms=[pl for pl, v in per.items() if v[0] > 0], days=days)
        posts = it.get('observed_social_posts') or []
        dated = [p for p in posts if P(p.get('date_utc'))]
        win['overall'] = dict(mentions=len(posts), voices=len({(p.get('platform'), p.get('author')) for p in posts if p.get('author')}),
                              platforms=sorted({p.get('platform') for p in posts if p.get('platform')} & set(PLATFORMS + ['GitHub'])),
                              days=look_days)
        rec['win'] = win
        # ---- real-score raw inputs
        rn = repo_name((it.get('links') or {}).get('repo'))
        t = trust.get(rn) if rn else None
        pa = arxiv_id((it.get('links') or {}).get('paper'))
        up = ups.get(pa, (None, None)) if pa else (None, None)
        us = usage_signal(it.get('real_traction_signals') or [])
        hn = it.get('hn_sampling') or {}
        hn_ok = bool(hn) and hn.get('error') is None
        hn_c = sum(((p.get('engagement') or {}).get('comments') or 0) for p in posts if p.get('platform') == 'HN') if hn_ok else None
        hn_n = sum(1 for p in posts if p.get('platform') == 'HN')
        rec['real_in'] = dict(
            gh_trust=None if not t else dict(v=t[0], conf=t[1], src=t[2], repo=rn),
            paper=None if up[0] is None else dict(v=up[0], id=pa, url=up[1]),
            usage=us,
            discussion=None if hn_c is None else dict(v=hn_c, stories=hn_n))
        raw_real.append(rec['real_in'])
        items[pid] = rec

    # ---- REAL score (window independent)
    zt = [None if r['gh_trust'] is None else max(0.0, min(1.0, r['gh_trust']['v'] / 100)) for r in raw_real]
    zp = lognorm([None if r['paper'] is None else r['paper']['v'] for r in raw_real])
    zu = lognorm([None if r['usage'] is None else r['usage']['value'] for r in raw_real])
    zu = [None if z is None else z * (VENDOR_DISCOUNT if r['usage']['vendor'] else 1) for z, r in zip(zu, raw_real)]
    zd = lognorm([None if r['discussion'] is None else r['discussion']['v'] for r in raw_real])
    for i, pid in enumerate(ids):
        zs = dict(gh_trust=zt[i], paper=zp[i], usage=zu[i], discussion=zd[i])
        sc, cf = combine(zs, REAL_W)
        items[pid]['real'] = sc if cf > 0 else None
        items[pid]['real_conf'] = cf
        items[pid]['real_z'] = {k: None if v is None else round(v, 3) for k, v in zs.items()}

    # ---- HYPE score per window
    if con is None and record: con = db_connect()
    prev, prev_ts = prev_hype(con, run_id) if con is not None else ({}, None)
    views = ['all'] + list(tags)
    out_w, ranks_rows = {}, []
    win_meta = {}
    for w in ALL_WINDOWS:
        if w in ('180d', '1y'):
            win_meta[w] = dict(enabled=False, reason=f'not a research window (research measured 1d/7d/30d/90d; overall = {look_days}-day lookback)')
            continue
        cand = [pid for pid in ids if items[pid]['win'].get(w) and items[pid]['win'][w]['mentions'] > 0]
        if not cand:
            win_meta[w] = dict(enabled=False, reason='no sampled posts in this window'); continue
        win_meta[w] = dict(enabled=True, days=items[cand[0]]['win'][w]['days'])
        vel, voi, spr = [], [], []
        for pid in cand:
            m = items[pid]['win'][w]
            age = items[pid]['age_at_cutoff']
            eff = max(1.0, min(m['days'], age if age is not None and age > 0 else m['days']))
            vel.append(m['mentions'] / eff); voi.append(m['voices']); spr.append(len(m['platforms']))
        zv, zo = lognorm(vel), lognorm(voi)
        mx_s = max(spr) or 1
        scored = []
        for i, pid in enumerate(cand):
            zs = dict(velocity=zv[i], acceleration=None, voices=zo[i], spread=spr[i] / mx_s)
            sc, cf = combine(zs, HYPE_W)
            real = items[pid]['real']
            gap = round(sc - real, 1) if real is not None else None
            scored.append(dict(id=pid, score=sc, conf=cf, vel=round(vel[i], 3), gap=gap,
                               z={k: None if v is None else round(v, 3) for k, v in zs.items()}))
        scored.sort(key=lambda r: (-r['score'], -(items[r['id']]['win'][w]['mentions'])))
        vv = {}
        for v in views:
            sub = scored if v == 'all' else [r for r in scored if items[r['id']]['tag'] == v]
            hkey = 'hype' if v == 'all' else f'hype|{v}'
            pr = prev.get((hkey, w), {})
            rows = []
            for k, r in enumerate(sub[:TOPN], 1):
                ranks_rows.append((hkey, w, r['id'], k, r['score']))
                rows.append(dict(r, rank=k, prev=pr.get(r['id'])))
            vv[v] = dict(rows=rows, candidates=len(sub))
        out_w[w] = vv

    now = datetime.now(timezone.utc)
    if record and con is not None:
        if run_id is None:
            cur = con.execute('INSERT INTO runs(ts, ts_local, seconds, sources) VALUES(?,?,?,?)',
                              (now.strftime('%Y-%m-%dT%H:%M:%SZ'), now.astimezone(TZ).isoformat(timespec='seconds'),
                               round(time.time() - t0, 1), json.dumps({'hype_build': 'standalone'})))
            run_id = cur.lastrowid
        con.executemany('INSERT INTO ranks VALUES(?,?,?,?,?,?)', [(run_id,) + r for r in ranks_rows])
        con.commit()
        os.makedirs(os.path.join(HIST, 'runs'), exist_ok=True)
        save(os.path.join(HIST, 'runs', now.astimezone(TZ).strftime('%Y%m%d-%H%M%S') + '-hype.json'),
             {'run_id': run_id, 'ranks': {f'{t}/{w}': [[i, k, s] for (tt, ww, i, k, s) in ranks_rows if tt == t and ww == w]
                                          for t in sorted({r[0] for r in ranks_rows}) for w in ALL_WINDOWS}})

    cov = summ.get('coverage_limitations') or []
    def pick(rx):
        return next((c for c in cov if re.search(rx, c, re.I)), None)
    short = [c for c in (pick(r'not exhaustive'), pick(r'growth cannot'), pick(r'^HN')) if c] or cov[:3]
    comp_counts = {
        'hype': {k: sum(1 for w in out_w.values() for r in w['all']['rows'] if r['z'].get(k) is not None) for k, _ in HYPE_W},
        'real': {k: sum(1 for pid in ids if items[pid]['real_z'][k] is not None) for k, _ in REAL_W},
    }
    data = dict(
        generated_at=now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        generated_local=now.astimezone(TZ).strftime('%Y-%m-%d %H:%M') + ' BRT',
        research_generated_at=summ.get('generated_at_utc'), content_cutoff=cutoff.strftime('%Y-%m-%dT%H:%M:%SZ'),
        lookback_days=look_days, run_id=run_id, previous_run=prev_ts,
        coverage_short=short, coverage=cov, ranking_interpretation=summ.get('ranking_interpretation'),
        gap_note=summ.get('gap_ranking_note'),
        weights=dict(hype=dict(HYPE_W), real=dict(REAL_W)), gap_thresholds=[GAP_SLEEPER, GAP_HYPE],
        missing=dict(acceleration='No growth series in the research (no repeated snapshots; HN sample = first 100 hits by date, so a recent/older ratio would be biased). Weight renormalised over the other three.'),
        component_counts=comp_counts, n_projects=len(ids), views=views, windows=win_meta,
        items=items, **out_w)
    save(OUT, data)
    sz = os.path.getsize(OUT)
    log(f'[HYPE] wrote {OUT} ({sz/1024:.0f} KB): {len(ids)} projects; windows ' +
        ', '.join(f'{w}={len(out_w[w]["all"]["rows"])}' for w in out_w) + f'; prev hype run: {prev_ts}')
    return data

if __name__ == '__main__':
    build(record='--no-history' not in sys.argv)
