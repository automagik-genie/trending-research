#!/usr/bin/env python3
"""AI-research trend tracker: fetch -> score -> write web/data.json + history.

Run:  python3 /workspace/trending/run.py

Sources (all public, no auth): arXiv API, Hugging Face papers API (daily/month lists,
search, per-paper), Hacker News Algolia API (social mentions), GitHub REST API
(search + stargazers with timestamps, unauthenticated unless `gh` is logged in).
Every source is wrapped: on failure the last good cached payload is reused and the
failure is recorded in data.json["sources"]. No metric is ever invented: unknown -> null
(rendered as '—').

TRUST / MOMENTUM SCORE (0-100), never star totals alone:
  Normalise each present signal s as z_s = log1p(rate_s) / max(log1p(rate_s) in the window)
  (ratios are 0..1; missing signals contribute 0 and lower confidence). Then
  score = 100 * sum(w_s * z_s) / max(raw in window).

  Papers: upvotes/day (.40), linked-repo trust (.35) when we have the repo's activity
          (else linked-repo star growth/day when measured, else missing), HN mentions/day (.25).
          Rates = value / max(days since release, 1).

  Repos (trust index): star growth/day (.35) — stars gained in the window from our snapshots
          or GitHub stargazer timestamps (repos born in-window use total stars as gain);
          never lifetime star totals as a substitute.
          issue activity/day (.20) = (issues opened + closed in lookback) / days;
          PR volume/day (.15) = PRs opened / days;
          PR merge rate (.15) = merged/opened in lookback (0..1, not log-scaled);
          commit frequency/day (.15) = commits / days;
          contributor count (.10) = log-scaled current contributors (explicitly allowed —
          unlike star totals);
          contributor growth/day (.15) = delta in contributor count from our snapshots
          (or all contributors if the repo was born in-window).
          Activity lookback ≈ 30d via GitHub Search API; contributor counts via
          /contributors (Link: last). confidence = fraction of signals present.
"""
import os, sys, re, json, time, math, sqlite3, fcntl, threading, traceback
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
WEB, HIST, CACHE = (os.path.join(BASE, d) for d in ('web', 'history', 'cache'))
DB = os.path.join(HIST, 'trending.db')
TZ = ZoneInfo('America/Sao_Paulo')
UA = 'felipe-ai-trend-tracker/1.0 (personal research dashboard)'
NOW = datetime.now(timezone.utc)
TODAY_LOCAL = NOW.astimezone(TZ).date()
WINDOWS = [('1d', 1), ('7d', 7), ('30d', 30), ('90d', 90), ('180d', 180), ('1y', 365), ('overall', None)]
TOPN = 100
HF_PAPER_BUDGET = 400      # per-paper HF lookups per run (HF anon limit: 500 req / 5 min)
HN_BUDGET = 900            # HN Algolia lookups per run (limit 10k/h)
for d in (WEB, HIST, CACHE, os.path.join(HIST, 'runs')):
    os.makedirs(d, exist_ok=True)

SOURCES = {}   # name -> {status, detail}
def note(name, status, detail=''):
    SOURCES[name] = {'status': status, 'detail': detail}
    print(f'[{name}] {status} {detail}', flush=True)

def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)

# ---------------------------------------------------------------- utils
def iso(dt): return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def parse_dt(s):
    if not s: return None
    s = s.replace('Z', '+00:00')
    try: return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        try: return datetime.fromisoformat(s[:19]).replace(tzinfo=timezone.utc)
        except Exception: return None

def load_json(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def save_json(path, obj, indent=None):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f: json.dump(obj, f, indent=indent, ensure_ascii=False)
    os.replace(tmp, path)

def cpath(name): return os.path.join(CACHE, re.sub(r'[^A-Za-z0-9_.-]+', '_', name)[:150] + '.json')

class HTTPErr(Exception):
    def __init__(self, code, msg, headers=None):
        super().__init__(f'HTTP {code}: {msg}'); self.code = code; self.headers = headers or {}

def http_get(url, headers=None, timeout=40):
    h = {'User-Agent': UA}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        body = e.read()[:300] if hasattr(e, 'read') else b''
        raise HTTPErr(e.code, body.decode('utf-8', 'replace'), dict(e.headers or {}))

# ---------------------------------------------------------------- rate limiters
class Interval:
    def __init__(self, sec): self.sec, self.last, self.lock = sec, 0.0, threading.Lock()
    def wait(self):
        with self.lock:
            d = self.last + self.sec - time.time()
            if d > 0: time.sleep(d)
            self.last = time.time()

ARXIV_RL = Interval(3.2)
HN_RL = Interval(0.12)
GH_SEARCH_RL = Interval(6.5)       # unauthenticated search: 10 req/min

class HFLimiter:
    """HF returns `ratelimit: "api";r=<remaining>;t=<seconds to reset>` (500 req / 300 s)."""
    def __init__(self): self.lock = threading.Lock(); self.remaining = 500; self.reset_at = 0; self.count = 0; self.iv = Interval(0.15)
    def before(self):
        with self.lock:
            if self.remaining <= 8 and time.time() < self.reset_at:
                s = self.reset_at - time.time() + 1
                log(f'HF rate limit low, sleeping {s:.0f}s'); time.sleep(s); self.remaining = 500
        self.iv.wait()
    def after(self, headers):
        rl = headers.get('ratelimit') or headers.get('RateLimit') or ''
        m = re.search(r'r=(\d+);t=(\d+)', rl)
        with self.lock:
            self.count += 1
            if m: self.remaining, self.reset_at = int(m.group(1)), time.time() + int(m.group(2))
HF_RL = HFLimiter()

def hf_get(path, allow404=False):
    url = 'https://huggingface.co' + path
    for attempt in range(4):
        HF_RL.before()
        try:
            st, hd, body = http_get(url)
            HF_RL.after(hd)
            return json.loads(body)
        except HTTPErr as e:
            HF_RL.after(e.headers)
            if e.code == 404 and allow404: return None
            if e.code == 429:
                m = re.search(r't=(\d+)', e.headers.get('ratelimit', '') or '')
                s = int(m.group(1)) + 1 if m else 60
                log(f'HF 429, sleep {s}s'); time.sleep(min(s, 310)); continue
            if e.code >= 500 and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < 3: time.sleep(3 * (attempt + 1)); continue
            raise

GH_TOKEN = None
def gh_token():
    """Use gh's token only if `gh auth status` says we are logged in (never read token files)."""
    global GH_TOKEN
    try:
        import subprocess
        st = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True, timeout=15)
        if st.returncode == 0:
            t = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=15)
            if t.returncode == 0 and t.stdout.strip(): GH_TOKEN = t.stdout.strip()
    except Exception: pass
    return GH_TOKEN

def gh_get(path, accept='application/vnd.github+json', search=False):
    url = 'https://api.github.com' + path
    h = {'Accept': accept, 'X-GitHub-Api-Version': '2022-11-28'}
    if GH_TOKEN: h['Authorization'] = 'Bearer ' + GH_TOKEN
    for attempt in range(3):
        if search and not GH_TOKEN: GH_SEARCH_RL.wait()
        try:
            st, hd, body = http_get(url, h)
            return json.loads(body), hd
        except HTTPErr as e:
            rem = e.headers.get('X-RateLimit-Remaining') or e.headers.get('x-ratelimit-remaining')
            if e.code in (403, 429) and rem == '0':
                reset = int(e.headers.get('X-RateLimit-Reset') or e.headers.get('x-ratelimit-reset') or 0)
                wait = reset - time.time() + 2
                if search and 0 < wait <= 65: log(f'GH search limit, sleep {wait:.0f}s'); time.sleep(wait); continue
                raise
            if e.code >= 500 and attempt < 2: time.sleep(4); continue
            raise

def gh_core_remaining():
    try:
        d, _ = gh_get('/rate_limit')    # does not count against the limit
        c = d['resources']['core']; return c['remaining'], c['reset']
    except Exception: return 0, 0

# ---------------------------------------------------------------- subjects / tagging
TAGS = ['JEPA', 'JEV', 'world/action models', 'harness/context', 'agents', 'other']
JEV_RX = r'jev(?!ons|gen)|typesafe|type-?safe ai|(?:typed|system[- ]one) decision models?|system[- ]one models?'
OTHER_STRONG = r'energy[- ]based|active inference|neuro-?symbolic|predictive coding|liquid (?:neural|time)|hierarchical reasoning model|tiny recursive model|artificial general intelligence|spiking neural|cognitive architecture|free[- ]energy principle|hyperdimensional|thousand brains'
# (tag, title regex, summary regex); agents in the summary needs >=2 hits (the word is everywhere)
TAG_RX = [
    ('JEPA', r'\bv?-?jepas?\b|joint[- ]embedding predictive', None),
    ('JEV', JEV_RX, None),
    ('world/action models', r'world[- ]models?\b|vision[- ]language[- ]action|\bVLAs?\b|large action models?|\baction models?\b|action[- ]conditioned (?:video|world)|world simulator', None),
    ('harness/context', r'context engineering|context layers?\b|\bharness(?:es)?\b|context management|context compression|context folding|context rot|memory layer|recursive language models?|\bRLMs?\b',
                        r'context engineering|context layers?\b|agent harness|harness engineering|(?:agentic|llm|coding|model) harness|context management|context compression|context folding|context rot|memory layer|recursive language models?'),
    ('agents', r'\bagents?\b|\bagentic\b|multi-agent|computer[- ]use|tool[- ]use|tool[- ]calling|\bmcp\b|model context protocol', None),
    ('other', OTHER_STRONG + r'|\bAGI\b|deepseek|continual learning|non-llm', OTHER_STRONG),
]
TAG_RX = [(t, re.compile(a, re.I), re.compile(b or a, re.I)) for t, a, b in TAG_RX]
FAV_RX = re.compile(r'^deepseek|recursive language model', re.I)

def tag_for(title, summary=''):
    for t, rt, _ in TAG_RX:
        if rt.search(title): return t
    for t, _, rs in TAG_RX:
        hits = len(rs.findall(summary or ''))
        if hits >= (2 if t == 'agents' else 1): return t
    return None

def is_fav(title, authors, lab):
    return bool(FAV_RX.search(title or '') or re.search(r'deepseek', ' '.join(authors[:50]), re.I)
                or re.search(r'deepseek|massachusetts institute|\bMIT\b', lab or '', re.I))

# ---------------------------------------------------------------- arXiv
CS = '(cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.MA OR cat:cs.RO OR cat:cs.CV OR cat:cs.NE OR cat:cs.SE)'
ARXIV_QUERIES = {
    'agents': (f'(ti:agent OR ti:agents OR ti:agentic) AND (cat:cs.AI OR cat:cs.CL OR cat:cs.MA OR cat:cs.LG)', 300),
    'harness_context': (f'(abs:"context engineering" OR abs:"agent harness" OR ti:harness OR abs:"context management" OR abs:"context layer" OR abs:"context compression" OR abs:"context folding") AND {CS}', 200),
    'jepa': ('abs:JEPA OR abs:"joint-embedding predictive" OR abs:"joint embedding predictive"', 200),
    'jev': (f'(abs:JEV OR abs:Jev OR abs:TypeSafe OR abs:"typed decision model" OR abs:"typed decision models" OR abs:"system one model" OR abs:"system one models" OR abs:"system one decision") AND {CS}', 200),
    'world_models': (f'(abs:"world model" OR abs:"world models") AND {CS}', 200),
    'action_models': (f'(abs:"vision-language-action" OR abs:"large action model" OR ti:VLA OR abs:"action model") AND {CS}', 200),
    'rlm': ('abs:"recursive language model" OR abs:"recursive language models"', 100),
    'deepseek': ('au:DeepSeek OR ti:DeepSeek', 100),
    'non_llm_agi': (f'(abs:"energy-based model" OR abs:"active inference" OR abs:"neuro-symbolic" OR abs:"predictive coding" OR abs:"hierarchical reasoning model" OR abs:"artificial general intelligence" OR abs:"liquid neural") AND {CS}', 200),
}
NS = {'a': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

def parse_arxiv(xml):
    root = ET.fromstring(xml)
    out = []
    for e in root.findall('a:entry', NS):
        aid_url = (e.findtext('a:id', '', NS) or '')
        m = re.search(r'abs/([^v\s]+?)(v\d+)?$', aid_url)
        if not m: continue
        authors, affs = [], []
        for a in e.findall('a:author', NS):
            authors.append(a.findtext('a:name', '', NS))
            for af in a.findall('arxiv:affiliation', NS):
                if af.text and af.text not in affs: affs.append(af.text)
        out.append(dict(id=m.group(1), title=' '.join((e.findtext('a:title', '', NS) or '').split()),
                        summary=' '.join((e.findtext('a:summary', '', NS) or '').split()),
                        authors=authors, affiliations=affs, published=e.findtext('a:published', '', NS)))
    return out

def fetch_arxiv():
    res, ok, fail = {}, 0, []
    for name, (q, n) in ARXIV_QUERIES.items():
        cp = cpath('arxiv_' + name)
        url = 'https://export.arxiv.org/api/query?' + urllib.parse.urlencode(
            {'search_query': q, 'start': 0, 'max_results': n, 'sortBy': 'submittedDate', 'sortOrder': 'descending'})
        entries = None
        for attempt in range(3):
            ARXIV_RL.wait()
            try:
                _, _, body = http_get(url, timeout=60)
                entries = parse_arxiv(body)
                if not entries and b'<entry>' in body: raise ValueError('parse failed')
                break
            except Exception as e:
                err = str(e); time.sleep(5 * (attempt + 1))
        if entries is not None:
            save_json(cp, {'fetched_at': iso(datetime.now(timezone.utc)), 'entries': entries}); ok += 1
        else:
            c = load_json(cp, None); entries = c['entries'] if c else []
            fail.append(f'{name} ({"cached " + c["fetched_at"] if c else "no cache"}: {err[:80]})')
        for p in entries:
            p.setdefault('queries', []); res.setdefault(p['id'], p)
            res[p['id']].setdefault('queries', []).append(name)
    note('arXiv API', 'ok' if not fail else ('partial' if ok else 'failed'),
         f'{ok}/{len(ARXIV_QUERIES)} keyword queries, {len(res)} papers' + ('; failed: ' + '; '.join(fail) if fail else ''))
    return res

# ---------------------------------------------------------------- Hugging Face lists
HF_SEARCH = ['JEPA', 'joint embedding predictive architecture', 'world model', 'vision-language-action',
             'large action model', 'context engineering', 'agent harness', 'recursive language models',
             'DeepSeek', 'LLM agents', 'energy-based model', 'JEV', 'Jev decision model', 'system one decision model']

def months_back(n):
    y, m = TODAY_LOCAL.year, TODAY_LOCAL.month
    out = []
    for _ in range(n):
        out.append(f'{y:04d}-{m:02d}'); m -= 1
        if m == 0: y, m = y - 1, 12
    return out

def hf_entry(x, observed):
    p = x.get('paper', x)
    org = p.get('organization') or x.get('organization') or {}
    return dict(id=p.get('id'), title=' '.join((p.get('title') or x.get('title') or '').split()),
                summary=' '.join((p.get('summary') or x.get('summary') or '').split()),
                authors=[a.get('name') for a in p.get('authors', []) if not a.get('hidden')],
                published=p.get('publishedAt') or x.get('publishedAt'), upvotes=p.get('upvotes'),
                upvotes_at=observed, githubRepo=p.get('githubRepo'), githubStars=p.get('githubStars'),
                org=org.get('fullname') or org.get('name'))

def fetch_hf_lists():
    res, fetched, cached, fail = {}, 0, 0, []
    months = months_back(13)
    for i, mo in enumerate(months):
        cp = cpath('hf_month_' + mo)
        c = load_json(cp, None)
        ttl_h = 1 if i < 2 else 72          # current & previous month refreshed every run
        if c and (time.time() - c.get('ts', 0)) < ttl_h * 3600:
            items = c['items']; cached += 1
        else:
            try:
                items, observed = [], iso(datetime.now(timezone.utc))
                for page in range(20):
                    d = hf_get(f'/api/daily_papers?month={mo}&limit=100&p={page}')
                    if not isinstance(d, list) or not d: break
                    items += [hf_entry(x, observed) for x in d]
                    if len(d) < 100: break
                save_json(cp, {'ts': time.time(), 'items': items}); fetched += 1
            except Exception as e:
                fail.append(f'{mo}: {str(e)[:80]}')
                items = c['items'] if c else []
        for it in items:
            if it.get('id'): res[it['id']] = it
    n_month = len(res)
    s_ok = 0
    for q in HF_SEARCH:
        cp = cpath('hf_search_' + q)
        try:
            observed = iso(datetime.now(timezone.utc))
            d = hf_get('/api/papers/search?' + urllib.parse.urlencode({'q': q, 'limit': 50}))
            items = [hf_entry(x, observed) for x in (d or [])]
            save_json(cp, {'ts': time.time(), 'items': items}); s_ok += 1
        except Exception as e:
            c = load_json(cp, None); items = c['items'] if c else []
            fail.append(f'search "{q}": {str(e)[:60]}')
        for it in items:
            if it.get('id') and it['id'] not in res: res[it['id']] = it
    note('Hugging Face lists', 'ok' if not fail else 'partial',
         f'{len(months)} months ({fetched} fetched, {cached} from <72h cache) = {n_month} papers; '
         f'{s_ok}/{len(HF_SEARCH)} searches; total {len(res)}' + ('; failed: ' + '; '.join(fail) if fail else ''))
    return res

# ---------------------------------------------------------------- GitHub search
GH_QUERIES = [
    ('topic:ai-agents', 'stars'), ('topic:llm-agent', 'stars'), ('topic:agentic-ai', 'stars'),
    ('agent created:>{d90}', 'stars'), ('agent framework pushed:>{d30}', 'stars'),
    ('"context engineering" in:name,description,topics', 'stars'),
    ('harness agent in:name,description', 'stars'),
    ('jepa in:name,description,topics', 'stars'),
    ('"world model" in:name,description,topics', 'stars'), ('topic:world-models', 'stars'),
    ('vision-language-action in:name,description,topics', 'stars'), ('topic:vla', 'stars'),
    ('"large action model" in:name,description', 'stars'),
    ('"recursive language model" in:name,description', 'stars'), ('rlm recursive in:name,description', 'stars'),
    ('user:deepseek-ai', 'stars'),
    ('"energy-based model" OR "active inference" OR neuro-symbolic in:name,description,topics', 'stars'),
    ('jev in:name,description,topics', 'stars'), ('topic:jev', 'stars'), ('topic:decision-model', 'stars'),
    ('topic:agent-harness', 'stars'), ('topic:context-engineering', 'stars'),
]

def fetch_github_search():
    d90 = (TODAY_LOCAL - timedelta(days=90)).isoformat(); d30 = (TODAY_LOCAL - timedelta(days=30)).isoformat()
    res, ok, fail = {}, 0, []
    for tmpl, sort in GH_QUERIES:
        q = tmpl.format(d90=d90, d30=d30)
        cp = cpath('gh_search_' + tmpl)
        try:
            d, _ = gh_get('/search/repositories?' + urllib.parse.urlencode({'q': q, 'sort': sort, 'order': 'desc', 'per_page': 100}), search=True)
            observed = iso(datetime.now(timezone.utc))
            items = [dict(full_name=x['full_name'], url=x['html_url'], owner=x['owner']['login'],
                          description=x.get('description') or '', stars=x['stargazers_count'], forks=x['forks_count'],
                          created_at=x['created_at'], pushed_at=x['pushed_at'], topics=x.get('topics') or [],
                          homepage=x.get('homepage') or '', archived=x.get('archived'), fork=x.get('fork'),
                          observed_at=observed) for x in d.get('items', [])]
            save_json(cp, {'ts': time.time(), 'items': items}); ok += 1
        except Exception as e:
            c = load_json(cp, None); items = c['items'] if c else []
            fail.append(f'"{q}" ({"cached" if c else "no cache"}: {str(e)[:70]})')
        for it in items:
            if it['fork']: continue
            old = res.get(it['full_name'])
            if not old or it['observed_at'] > old['observed_at']: res[it['full_name']] = it
    note('GitHub search API', 'ok' if not fail else ('partial' if ok else 'failed'),
         f'{ok}/{len(GH_QUERIES)} queries ({"authenticated" if GH_TOKEN else "unauthenticated, 10 req/min"}), {len(res)} repos'
         + ('; failed: ' + '; '.join(fail) if fail else ''))
    return res

def fetch_stargazers(repos, order):
    """Star timestamps for repos (newest pages first) using the core API budget."""
    cache = load_json(cpath('stargazers'), {})
    rem, reset = gh_core_remaining()
    budget = max(0, rem - 3)
    used, done, consec_fail, last_err = 0, 0, 0, ''
    for fn in order:
        if consec_fail >= 3: break
        r = repos[fn]
        c = cache.get(fn)
        if c and time.time() - c['ts'] < 20 * 3600: continue
        if r['stars'] > 40000 or r['stars'] == 0: continue
        last_page = max(1, math.ceil(r['stars'] / 100))
        pages_needed = 1
        times, complete, page = [], False, last_page
        cutoff = NOW - timedelta(days=365)
        while page >= 1 and used < budget and pages_needed <= 3:
            try:
                d, _ = gh_get(f'/repos/{fn}/stargazers?per_page=100&page={page}', accept='application/vnd.github.star+json')
                used += 1
            except Exception as e:
                used += 1; times = None; consec_fail += 1; last_err = str(e)[:100]; break
            consec_fail = 0
            times += [x['starred_at'] for x in d if x.get('starred_at')]
            if page == 1: complete = True; break
            oldest = min((parse_dt(t) for t in times), default=NOW)
            if oldest < cutoff: break
            page -= 1; pages_needed += 1
        if times is None or (not times and not complete): 
            if used >= budget: break
            continue
        cache[fn] = {'ts': time.time(), 'times': sorted(times), 'complete': complete,
                     'oldest': min(times) if times else None, 'stars_at_fetch': r['stars']}
        done += 1
        if used >= budget: break
    save_json(cpath('stargazers'), cache)
    if consec_fail >= 3:
        note('GitHub stargazers API', 'failed', f'stopped after 3 consecutive errors ({last_err}); star timestamps for {done} repos this run, {len(cache)} cached')
    elif budget == 0:
        note('GitHub stargazers API', 'skipped', f'core rate limit exhausted (unauthenticated 60/h); resets {datetime.fromtimestamp(reset, TZ).strftime("%H:%M")} BRT. Using cached timestamps for {len(cache)} repos')
    else:
        note('GitHub stargazers API', 'ok', f'{used} requests, star timestamps for {done} new repos ({len(cache)} cached total)')
    return cache

ACTIVITY_LOOKBACK = 30   # days for cached activity snapshot; scaled into each window
ACTIVITY_BUDGET = 30     # repos to enrich per run (4 search queries each ≈ 3–6 min)

def _gh_search_count(q, commits=False):
    path = '/search/commits?' if commits else '/search/issues?'
    path += urllib.parse.urlencode({'q': q, 'per_page': 1})
    accept = 'application/vnd.github.cloak-preview+json' if commits else 'application/vnd.github+json'
    d, _ = gh_get(path, accept=accept, search=True)
    return int(d.get('total_count') or 0)

def fetch_repo_activity(repos, order):
    """Issue / PR / commit activity via GitHub Search (separate quota from core).

    Stores a 30-day lookback snapshot per repo. Missing fields stay null — never invented.
    """
    cache = load_json(cpath('repo_activity'), {})
    since = (TODAY_LOCAL - timedelta(days=ACTIVITY_LOOKBACK)).isoformat()
    todo, done, fail = [], 0, 0
    for fn in order:
        c = cache.get(fn)
        if c and time.time() - c.get('ts', 0) < 18 * 3600: continue
        todo.append(fn)
        if len(todo) >= ACTIVITY_BUDGET: break
    for fn in todo:
        try:
            issues_open = _gh_search_count(f'repo:{fn} type:issue created:>{since}')
            issues_closed = _gh_search_count(f'repo:{fn} type:issue is:closed closed:>{since}')
            prs_open = _gh_search_count(f'repo:{fn} type:pr created:>{since}')
            prs_merged = _gh_search_count(f'repo:{fn} type:pr is:merged merged:>{since}')
            try:
                commits = _gh_search_count(f'repo:{fn} committer-date:>{since}', commits=True)
            except Exception:
                commits = None   # commit search sometimes 422 / unsupported
            # Contributor count via core API (Link: rel=last); growth comes from our snapshots later.
            contributors = None
            rem, _ = gh_core_remaining()
            if rem > 5:
                try:
                    body, hd = gh_get(f'/repos/{fn}/contributors?per_page=1&anon=true')
                    link = hd.get('Link') or hd.get('link') or ''
                    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
                    if m:
                        contributors = int(m.group(1))
                    else:
                        contributors = len(body) if isinstance(body, list) else None
                except Exception:
                    contributors = None
            cache[fn] = dict(ts=time.time(), lookback_days=ACTIVITY_LOOKBACK, since=since,
                             observed_at=iso(datetime.now(timezone.utc)),
                             issues_opened=issues_open, issues_closed=issues_closed,
                             prs_opened=prs_open, prs_merged=prs_merged, commits=commits,
                             contributors=contributors)
            done += 1
            save_json(cpath('repo_activity'), cache)   # checkpoint
        except Exception as e:
            fail += 1
            if 'rate limit' in str(e).lower() or '403' in str(e) or '429' in str(e):
                note('GitHub activity (issues/PRs/commits)', 'partial',
                     f'stopped on rate limit after {done} repos ({fail} fails); {len(cache)} cached. {str(e)[:80]}')
                save_json(cpath('repo_activity'), cache)
                return cache
            if fail >= 5:
                note('GitHub activity (issues/PRs/commits)', 'partial',
                     f'{done} ok, {fail} fails — last: {str(e)[:80]}; {len(cache)} cached')
                save_json(cpath('repo_activity'), cache)
                return cache
    note('GitHub activity (issues/PRs/commits)', 'ok' if fail == 0 else 'partial',
         f'{done}/{len(todo)} repos enriched this run ({ACTIVITY_LOOKBACK}d lookback via Search API), '
         f'{len(cache)} cached, fails={fail}')
    save_json(cpath('repo_activity'), cache)
    return cache


def fill_contributor_counts(activity, order):
    """Backfill contributor counts on cached activity entries using core API budget."""
    rem, reset = gh_core_remaining()
    budget = max(0, rem - 5)
    filled = 0
    for fn in order:
        if budget <= 0: break
        a = activity.get(fn)
        if not a: continue
        if a.get('contributors') is not None and time.time() - a.get('ts', 0) < 18 * 3600:
            continue
        try:
            body, hd = gh_get(f'/repos/{fn}/contributors?per_page=1&anon=true')
            budget -= 1
            link = hd.get('Link') or hd.get('link') or ''
            m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
            if m:
                n = int(m.group(1))
            else:
                n = len(body) if isinstance(body, list) else None
            if a is None:
                activity[fn] = dict(ts=time.time(), observed_at=iso(datetime.now(timezone.utc)))
                a = activity[fn]
            a['contributors'] = n
            a['contributors_at'] = iso(datetime.now(timezone.utc))
            a['ts'] = time.time()
            filled += 1
        except Exception as e:
            if 'rate limit' in str(e).lower(): break
            continue
    save_json(cpath('repo_activity'), activity)
    note('GitHub contributors', 'ok' if filled or any(a.get('contributors') is not None for a in activity.values()) else 'skipped',
         f'{filled} counts fetched this run; {sum(1 for a in activity.values() if a.get("contributors") is not None)} cached'
         + (f'; core reset {datetime.fromtimestamp(reset, TZ).strftime("%H:%M")} BRT' if budget <= 0 else ''))
    return activity

# ---------------------------------------------------------------- per-paper HF + HN
def hf_paper_lookups(ids_prio):
    cache = load_json(cpath('hf_papers'), {})
    todo = []
    for pid, age_days, kind in ids_prio:
        c = cache.get(pid)
        ttl = 6 if age_days <= 30 else (24 if age_days <= 180 else 72)
        if c and time.time() - c['ts'] < ttl * 3600: continue
        todo.append(pid)
        if len(todo) >= HF_PAPER_BUDGET: break
    errs = 0
    def one(pid):
        nonlocal errs
        try:
            observed = iso(datetime.now(timezone.utc))
            d = hf_get('/api/papers/' + pid, allow404=True)
            cache[pid] = {'ts': time.time(), 'found': d is not None,
                          'data': hf_entry(d, observed) if d else None}
        except Exception: errs += 1
    with ThreadPoolExecutor(4) as ex: list(ex.map(one, todo))
    save_json(cpath('hf_papers'), cache)
    note('Hugging Face per-paper API', 'ok' if errs < max(5, len(todo) // 10) else 'partial',
         f'{len(todo) - errs}/{len(todo)} lookups this run (budget {HF_PAPER_BUDGET}), {len(cache)} cached; errors {errs}')
    return cache

def hn_lookups(papers_prio):
    cache = load_json(cpath('hn'), {})
    todo = []
    for pid, age_days in papers_prio:
        c = cache.get(pid)
        ttl = 6 if age_days <= 30 else 72
        if c and time.time() - c['ts'] < ttl * 3600: continue
        todo.append(pid)
        if len(todo) >= HN_BUDGET: break
    errs = 0
    def one(pid):
        nonlocal errs
        try:
            HN_RL.wait()
            q = urllib.parse.urlencode({'query': f'"{pid}"', 'tags': '(story,comment)', 'hitsPerPage': 200})
            _, _, body = http_get('https://hn.algolia.com/api/v1/search?' + q, timeout=20)
            d = json.loads(body)
            stories = comments = points = 0
            for h in d.get('hits', []):
                blob = ' '.join(str(h.get(k) or '') for k in ('url', 'title', 'story_text', 'comment_text'))
                if not re.search(r'(?<![\d.])' + re.escape(pid) + r'(?!\d)', blob): continue   # exact id only
                if 'story' in (h.get('_tags') or []): stories += 1; points += h.get('points') or 0
                else: comments += 1
            cache[pid] = {'ts': time.time(), 'observed_at': iso(datetime.now(timezone.utc)),
                          'mentions': stories + comments, 'stories': stories, 'comments': comments, 'points': points}
        except Exception: errs += 1
    with ThreadPoolExecutor(6) as ex: list(ex.map(one, todo))
    save_json(cpath('hn'), cache)
    note('Hacker News (Algolia) mentions', 'ok' if errs < max(5, len(todo) // 10) else ('failed' if errs == len(todo) else 'partial'),
         f'{len(todo) - errs}/{len(todo)} lookups this run, {len(cache)} cached; errors {errs}')
    return cache

def check_reddit():
    try:
        http_get('https://www.reddit.com/search.json?q=arxiv&limit=1', timeout=15)
        note('Reddit search JSON', 'not used', 'reachable but not wired in (HN used for mentions)')
    except Exception as e:
        note('Reddit search JSON', 'failed', f'HTTP {getattr(e, "code", "error")} (blocked without auth) -> social mentions come from Hacker News only')

# ---------------------------------------------------------------- history DB
def db():
    con = sqlite3.connect(DB)
    con.executescript('''
    CREATE TABLE IF NOT EXISTS runs(run_id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, ts_local TEXT, seconds REAL, sources TEXT);
    CREATE TABLE IF NOT EXISTS paper_snap(run_id INT, arxiv_id TEXT, upvotes INT, upvotes_at TEXT, stars INT, stars_at TEXT,
        mentions INT, mentions_at TEXT, hn_points INT);
    CREATE TABLE IF NOT EXISTS repo_snap(run_id INT, full_name TEXT, stars INT, forks INT, observed_at TEXT, contributors INT);
    CREATE TABLE IF NOT EXISTS repo_activity_snap(run_id INT, full_name TEXT, issues_opened INT, issues_closed INT,
        prs_opened INT, prs_merged INT, commits INT, contributors INT, lookback_days INT, observed_at TEXT);
    CREATE TABLE IF NOT EXISTS ranks(run_id INT, tab TEXT, win TEXT, item_id TEXT, rank INT, score REAL);
    CREATE INDEX IF NOT EXISTS i_ranks ON ranks(tab, win, run_id);
    CREATE INDEX IF NOT EXISTS i_repo ON repo_snap(full_name, observed_at);
    CREATE INDEX IF NOT EXISTS i_paper ON paper_snap(arxiv_id);
    ''')

    try: con.execute('ALTER TABLE repo_snap ADD COLUMN contributors INT')
    except Exception: pass
    return con

def prev_ranks(con):
    out = {}
    r = con.execute('SELECT MAX(run_id) FROM runs').fetchone()[0]
    if r is None: return out, None
    for tab, win, item, rank in con.execute('SELECT tab, win, item_id, rank FROM ranks WHERE run_id=?', (r,)):
        out.setdefault((tab, win), {})[item] = rank
    ts = con.execute('SELECT ts_local FROM runs WHERE run_id=?', (r,)).fetchone()[0]
    return out, ts

def repo_snapshot_gain(con, fn, stars_now, days):
    """Stars gained over ~`days` from our own snapshots: needs a snapshot observed near the window start."""
    start = NOW - timedelta(days=days)
    tol = timedelta(days=max(0.15 * days, 0.25))
    row = con.execute('SELECT stars, observed_at FROM repo_snap WHERE full_name=? AND observed_at BETWEEN ? AND ? '
                      'ORDER BY observed_at DESC LIMIT 1', (fn, iso(start - tol), iso(start + tol))).fetchone()
    if not row: return None
    span = (NOW - parse_dt(row[1])).total_seconds() / 86400
    if span < 0.25: return None
    return stars_now - row[0], span

# ---------------------------------------------------------------- scoring
def norm_scores(items, signals, ratio_keys=()):
    """signals: list of (key, weight). rates use log1p; ratio_keys (e.g. merge rate) stay in [0,1]."""
    mx = {}
    for k, _ in signals:
        if k in ratio_keys:
            mx[k] = 1.0
        else:
            mx[k] = max((math.log1p(i['_rates'][k]) for i in items
                         if i['_rates'].get(k) is not None and i['_rates'][k] > 0), default=0)
    raws = []
    for i in items:
        raw = 0.0
        present = 0
        for k, w in signals:
            v = i['_rates'].get(k)
            if v is None: continue
            present += 1
            if k in ratio_keys:
                raw += w * max(0.0, min(1.0, float(v)))
            elif v > 0 and mx[k] > 0:
                raw += w * math.log1p(v) / mx[k]
        i['_confidence'] = round(present / max(len(signals), 1), 2)
        raws.append(raw)
    m = max(raws, default=0)
    for i, raw in zip(items, raws):
        i['_score'] = round(100 * raw / m, 1) if m > 0 else 0.0

def in_window_date(d, days):
    if days is None: return True
    return d is not None and d >= TODAY_LOCAL - timedelta(days=days)

def local_date(dt): return dt.astimezone(TZ).date() if dt else None

# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    lockf = open(os.path.join(BASE, '.run.lock'), 'w')
    try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: print('another run.py is in progress; exiting'); return 1
    gh_token()
    log('start', 'gh auth: ' + ('yes' if GH_TOKEN else 'no (unauthenticated GitHub API)'))

    def safe(fn, name, default):
        try: return fn()
        except Exception as e:
            traceback.print_exc(); note(name, 'failed', str(e)[:120]); return default
    with ThreadPoolExecutor(3) as ex:
        fa = ex.submit(safe, fetch_arxiv, 'arXiv API', {})
        fh = ex.submit(safe, fetch_hf_lists, 'Hugging Face lists', {})
        fg = ex.submit(safe, fetch_github_search, 'GitHub search API', {})
        arx, hfl, repos = fa.result(), fh.result(), fg.result()
    log('lists done', len(arx), len(hfl), len(repos))

    # ---- merge paper candidates (subject filter applied to HF lists; arXiv already keyword-queried)
    papers = {}
    for pid, a in arx.items():
        papers[pid] = dict(id=pid, title=a['title'], summary=a['summary'], authors=a['authors'], lab=None,
                           affiliations=a['affiliations'], published=a['published'], upvotes=None, upvotes_at=None,
                           githubRepo=None, githubStars=None, stars_at=None, on_hf=False, src=['arXiv'])
    for pid, h in hfl.items():
        if pid not in papers:
            if not tag_for(h.get('title') or '', h.get('summary') or ''): continue   # keep only Felipe's subjects
            papers[pid] = dict(id=pid, title=h['title'], summary=h.get('summary') or '', authors=h['authors'], lab=None, affiliations=[],
                               published=h['published'], upvotes=None, upvotes_at=None, githubRepo=None,
                               githubStars=None, stars_at=None, on_hf=True, src=[])
        p = papers[pid]
        p['on_hf'] = True; p['src'].append('HF')
        if h.get('upvotes') is not None: p['upvotes'], p['upvotes_at'] = h['upvotes'], h['upvotes_at']
        if h.get('githubRepo'): p['githubRepo'] = h['githubRepo']
        if h.get('githubStars') is not None: p['githubStars'], p['stars_at'] = h['githubStars'], h['upvotes_at']
        if h.get('org'): p['lab'] = h['org']
    for p in papers.values():
        p['pub_dt'] = parse_dt(p['published'])
        p['age'] = max((NOW - p['pub_dt']).total_seconds() / 86400, 0) if p['pub_dt'] else None
    log('paper candidates', len(papers))

    # ---- per-paper HF lookups (stars for linked repos, upvotes for arXiv-only papers)
    def pre_rate(p):
        a = max(p['age'] or 1, 1)
        return (p['upvotes'] or 0) / a
    with_repo = sorted([p for p in papers.values() if p['githubRepo'] and p['age'] is not None],
                       key=lambda p: -pre_rate(p))
    arxiv_only = sorted([p for p in papers.values() if not p['on_hf'] and p['age'] is not None], key=lambda p: p['age'])
    prio, seen = [], set()
    # interleave 3 repo-stars lookups : 2 arXiv-only lookups
    ia = ib = 0
    while ia < len(with_repo) or ib < len(arxiv_only):
        for _ in range(3):
            if ia < len(with_repo): p = with_repo[ia]; ia += 1; prio.append((p['id'], p['age'], 'repo'))
        for _ in range(2):
            if ib < len(arxiv_only): p = arxiv_only[ib]; ib += 1; prio.append((p['id'], p['age'], 'arxiv'))
    hfp = safe(lambda: hf_paper_lookups(prio), 'Hugging Face per-paper API', load_json(cpath('hf_papers'), {}))
    for pid, c in hfp.items():
        p = papers.get(pid)
        if not p or not c.get('found') or not c.get('data'): continue
        d = c['data']; p['on_hf'] = True
        if d.get('upvotes') is not None and (p['upvotes_at'] or '') <= d['upvotes_at']: p['upvotes'], p['upvotes_at'] = d['upvotes'], d['upvotes_at']
        if d.get('githubRepo'): p['githubRepo'] = d['githubRepo']
        if d.get('githubStars') is not None: p['githubStars'], p['stars_at'] = d['githubStars'], d['upvotes_at']
        if d.get('org'): p['lab'] = d['org']
    # stars from GitHub search results are fresher when the same repo was found
    by_url = {r['url'].lower().rstrip('/'): r for r in repos.values()}
    for p in papers.values():
        if p['githubRepo']:
            r = by_url.get(p['githubRepo'].lower().rstrip('/').removesuffix('.git'))
            if r: p['githubStars'], p['stars_at'] = r['stars'], r['observed_at']

    # ---- HN mentions: every paper that could plausibly enter a top-100 (by pre-score), newest first
    def pre_score(p):
        a = max(p['age'] or 1, 1)
        return math.log1p((p['upvotes'] or 0) / a) * .45 + math.log1p((p['githubStars'] or 0) / a) * .35
    hn_set = set()
    for wname, days in WINDOWS:
        cand = [p for p in papers.values() if in_window_date(local_date(p['pub_dt']), days)]
        cand.sort(key=lambda p: (-pre_score(p), p['age'] or 1e9))
        hn_set.update(p['id'] for p in cand[:160])
        for t in TAGS:      # also cover each paradigm view's likely top 100
            hn_set.update([p['id'] for p in cand if (tag_for(p['title'], p['summary']) or 'other') == t][:130])
    hn_prio = sorted(((pid, papers[pid]['age'] or 9999) for pid in hn_set), key=lambda x: x[1])
    hn = safe(lambda: hn_lookups(hn_prio), 'Hacker News (Algolia) mentions', load_json(cpath('hn'), {}))
    check_reddit()
    for p in papers.values():
        c = hn.get(p['id'])
        p['mentions'] = c['mentions'] if c else None
        p['mentions_at'] = c['observed_at'] if c else None
        p['hn_points'] = c['points'] if c else None
        p['tag'] = tag_for(p['title'], p['summary']) or 'other'
        if not p['lab']:
            p['lab'] = ', '.join(p['affiliations'][:2]) if p['affiliations'] else None
        p['fav'] = is_fav(p['title'], p['authors'], p['lab'])

    # ---- repos: linked paper + tags + stargazer gains
    repo_by_url_to_paper = {}
    for p in papers.values():
        if p['githubRepo']: repo_by_url_to_paper[p['githubRepo'].lower().rstrip('/').removesuffix('.git')] = p['id']
    for r in repos.values():
        text = ' '.join([r['full_name'].replace('/', ' ').replace('-', ' '), r['description'], ' '.join(t.replace('-', ' ') for t in r['topics'])])
        r['tag'] = tag_for(text)
        m = re.search(r'(?:arxiv\.org/(?:abs|pdf)/|huggingface\.co/papers/|arXiv[: ]+)(\d{4}\.\d{4,5})', r['description'] + ' ' + r['homepage'], re.I)
        r['paper'] = repo_by_url_to_paper.get(r['url'].lower().rstrip('/')) or (m.group(1) if m else None)
        r['created_dt'], r['pushed_dt'] = parse_dt(r['created_at']), parse_dt(r['pushed_at'])
        r['age'] = max((NOW - r['created_dt']).total_seconds() / 86400, 1)
        r['fav'] = bool(re.search(r'deepseek|recursive language model|\brlm\b', text, re.I))
    # keep only on-subject repos (the 'other' bucket covers DeepSeek & non-LLM paradigms)
    repos = {k: v for k, v in repos.items() if v['tag'] or v['fav']}
    for r in repos.values(): r['tag'] = r['tag'] or 'other'
    order = sorted(repos, key=lambda k: -(repos[k]['stars'] / repos[k]['age']))
    sg = safe(lambda: fetch_stargazers(repos, order), 'GitHub stargazers API', load_json(cpath('stargazers'), {}))
    act_order = sorted(repos, key=lambda k: (
        -(1 if repos[k]['pushed_dt'] and repos[k]['pushed_dt'] >= NOW - timedelta(days=30) else 0),
        -(repos[k]['stars'] / max(repos[k]['age'], 1)),
        -repos[k]['stars']))
    linked = []
    for p in papers.values():
        if p.get('githubRepo'):
            fn = p['githubRepo'].rstrip('/').removesuffix('.git').split('github.com/')[-1]
            if fn in repos and fn not in linked: linked.append(fn)
    act_order = linked + [k for k in act_order if k not in linked]
    activity = safe(lambda: fetch_repo_activity(repos, act_order), 'GitHub activity (issues/PRs/commits)',
                    load_json(cpath('repo_activity'), {}))
    activity = safe(lambda: fill_contributor_counts(activity, act_order), 'GitHub contributors', activity)

    con = db()
    prev, prev_ts = prev_ranks(con)
    out = {'papers': {'items': {}}, 'repos': {'items': {}}}
    ranks_rows = []
    VIEWS = ['all'] + TAGS     # 'all' = the spec'd top-100; per-paradigm views rank within that tag

    def emit(tab, wname, cand, key, extra):
        """cand is sorted by score; writes top-N per view with movement vs previous run."""
        views = {}
        for v in VIEWS:
            sub = cand if v == 'all' else [c for c in cand if c['tag'] == v]
            hkey = tab if v == 'all' else f'{tab}|{v}'
            pr = prev.get((hkey, wname), {})
            lst = []
            for i, c in enumerate(sub[:TOPN], 1):
                ranks_rows.append((hkey, wname, c[key], i, c['_score']))
                lst.append(dict(id=c[key], rank=i, prev=pr.get(c[key]), score=c['_score'], **extra(c)))
            views[v] = {'rows': lst, 'candidates': len(sub)}
        out[tab][wname] = views

    # ---- repos per window (trust index)
    def star_growth(r, days):
        # (gained, rate/day) or (None, None). Never uses bare star totals for old repos.
        use_days = 90 if days is None else days
        start = NOW - timedelta(days=use_days)
        if r['created_dt'] and r['created_dt'] >= start:
            return r['stars'], r['stars'] / max(r['age'], 1)
        sgz = sg.get(r['full_name'])
        if sgz and sgz.get('times') is not None:
            fetched = datetime.fromtimestamp(sgz['ts'], timezone.utc)
            wstart = fetched - timedelta(days=use_days)
            covered = sgz['complete'] or (sgz['oldest'] and parse_dt(sgz['oldest']) <= wstart)
            if covered:
                gained = sum(1 for t in sgz['times'] if parse_dt(t) >= wstart)
                return gained, gained / max(use_days, 1)
        g = repo_snapshot_gain(con, r['full_name'], r['stars'], use_days)
        if g:
            return g[0], max(g[0], 0) / max(g[1], 0.25)
        return None, None

    def contrib_growth(fn, current, days):
        # Delta in contributor count vs a snapshot near window start. Missing -> None.
        if current is None:
            return None, None
        use_days = 90 if days is None else days
        start = NOW - timedelta(days=use_days)
        # Repo born in window: all contributors are growth
        r = repos[fn]
        if r['created_dt'] and r['created_dt'] >= start:
            return current, current / max(r['age'], 1)
        tol = timedelta(days=max(0.15 * use_days, 0.25))
        row = con.execute(
            'SELECT contributors, observed_at FROM repo_snap WHERE full_name=? AND contributors IS NOT NULL '
            'AND observed_at BETWEEN ? AND ? ORDER BY observed_at DESC LIMIT 1',
            (fn, iso(start - tol), iso(start + tol))).fetchone()
        if not row:
            # fall back to oldest snapshot older than half the window
            row = con.execute(
                'SELECT contributors, observed_at FROM repo_snap WHERE full_name=? AND contributors IS NOT NULL '
                'AND observed_at <= ? ORDER BY observed_at DESC LIMIT 1',
                (fn, iso(start + tol))).fetchone()
        if not row:
            return None, None
        span = (NOW - parse_dt(row[1])).total_seconds() / 86400
        if span < 0.25:
            return None, None
        gained = current - row[0]
        return gained, gained / span

    def activity_bundle(r, days):
        a = activity.get(r['full_name']) or {}
        lb = max(a.get('lookback_days') or ACTIVITY_LOOKBACK, 1)
        # Short windows: don't pretend 30d averages are 1d counts
        apply_activity = (days is None) or (days >= lb / 2)
        out = {'contributors': a.get('contributors')}
        if apply_activity:
            io, ic = a.get('issues_opened'), a.get('issues_closed')
            po, pm = a.get('prs_opened'), a.get('prs_merged')
            cm = a.get('commits')
            if io is not None and ic is not None:
                out['issues'] = (io + ic) / lb
                out['issues_opened'] = io
                out['issues_closed'] = ic
            if po is not None:
                out['prs'] = po / lb
                out['prs_opened'] = po
                if pm is not None:
                    out['merge'] = (pm / po) if po > 0 else 0.0
                    out['prs_merged'] = pm
            if cm is not None:
                out['commits'] = cm / lb
                out['commits_n'] = cm
        return out

    TRUST_WEIGHTS = [('stars', .25), ('issues', .15), ('prs', .10), ('merge', .10),
                     ('commits', .15), ('contribs', .10), ('contrib_growth', .15)]

    # Precompute 30d trust so papers can use linked-repo trust
    for r in repos.values():
        g30, rate30 = star_growth(r, 30)
        act = activity_bundle(r, 30)
        cg, cgr = contrib_growth(r['full_name'], act.get('contributors'), 30)
        r['_gained_30'] = g30
        r['_star_rate_30'] = rate30
        r['_contribs'] = act.get('contributors')
        r['_contrib_gained_30'] = cg
        r['_rates'] = {
            'stars': rate30, 'issues': act.get('issues'), 'prs': act.get('prs'),
            'merge': act.get('merge'), 'commits': act.get('commits'),
            'contribs': act.get('contributors'),  # level signal (explicitly allowed)
            'contrib_growth': cgr,
        }
    all_repos = list(repos.values())
    norm_scores(all_repos, TRUST_WEIGHTS, ratio_keys={'merge'})
    for r in all_repos:
        has = any(r['_rates'].get(k) is not None for k, _ in TRUST_WEIGHTS)
        r['_trust'] = r['_score'] if has else None

    by_url = {r['url'].lower().rstrip('/'): r for r in repos.values()}
    for p in papers.values():
        p['_repo_trust'] = None
        p['_repo_star_growth'] = None
        if not p.get('githubRepo'):
            continue
        key = p['githubRepo'].lower().rstrip('/').removesuffix('.git')
        rr = by_url.get(key)
        if not rr:
            continue
        p['_repo_trust'] = rr.get('_trust')
        p['_repo_star_growth'] = rr.get('_star_rate_30')

    for wname, days in WINDOWS:
        if days is None:
            cand = list(repos.values())
        else:
            start = NOW - timedelta(days=days)
            cand = [r for r in repos.values()
                    if (r['created_dt'] and r['created_dt'] >= start)
                    or (r['pushed_dt'] and r['pushed_dt'] >= start)]
        for r in cand:
            gained, rate = star_growth(r, days)
            act = activity_bundle(r, days if days is not None else 90)
            cg, cgr = contrib_growth(r['full_name'], act.get('contributors'), days)
            r['_gained'] = gained
            r['_contrib_gained'] = cg
            r['_act_w'] = act
            r['_rates'] = {
                'stars': rate, 'issues': act.get('issues'), 'prs': act.get('prs'),
                'merge': act.get('merge'), 'commits': act.get('commits'),
                'contribs': act.get('contributors'), 'contrib_growth': cgr,
            }
        norm_scores(cand, TRUST_WEIGHTS, ratio_keys={'merge'})
        cand.sort(key=lambda r: (-r['_score'], -(r['_gained'] or -1), -r['stars']))

        def extra(c, _act_key='_act_w'):
            a = c.get('_act_w') or {}
            return dict(
                gained=c.get('_gained'), confidence=c.get('_confidence'),
                issues_opened=a.get('issues_opened'), issues_closed=a.get('issues_closed'),
                prs_opened=a.get('prs_opened'), prs_merged=a.get('prs_merged'),
                merge_rate=a.get('merge'), commits=a.get('commits_n'),
                contributors=a.get('contributors'), contrib_gained=c.get('_contrib_gained'),
            )
        emit('repos', wname, cand, 'full_name', extra)

    used = {row['id'] for w in out['repos'] if w != 'items'
            for v in out['repos'][w].values() for row in v['rows']}
    for fn in used:
        r = repos[fn]
        pp = papers.get(r['paper']) if r['paper'] else None
        out['repos']['items'][fn] = dict(
            url=r['url'], owner=r['owner'], desc=r['description'][:200], stars=r['stars'],
            forks=r['forks'], paper=r['paper'], paper_title=pp['title'] if pp else None,
            pushed=r['pushed_at'], created=r['created_at'][:10], tag=r['tag'], fav=r['fav'],
            contributors=r.get('_contribs'))

    # ---- papers per window
    for wname, days in WINDOWS:
        cand = [p for p in papers.values() if p['pub_dt'] and in_window_date(local_date(p['pub_dt']), days)]
        for p in cand:
            a = max(p['age'], 1)
            trust = p.get('_repo_trust')
            star_g = p.get('_repo_star_growth')
            code_sig = trust if trust is not None else star_g
            p['_rates'] = {'up': p['upvotes'] / a if p['upvotes'] is not None else None,
                           'code': code_sig,
                           'ment': p['mentions'] / a if p['mentions'] is not None else None}
        norm_scores(cand, [('up', .40), ('code', .35), ('ment', .25)])
        cand.sort(key=lambda p: (-p['_score'], p['age']))
        emit('papers', wname, cand, 'id', lambda c: {'confidence': c.get('_confidence')})
    used = {r['id'] for w in out['papers'] if w != 'items' for v in out['papers'][w].values() for r in v['rows']}
    for pid in used:
        p = papers[pid]
        out['papers']['items'][pid] = dict(title=p['title'], authors=p['authors'][:4], n_authors=len(p['authors']), lab=p['lab'],
                                           upvotes=p['upvotes'], stars=p['githubStars'], code=p['githubRepo'],
                                           mentions=p['mentions'], hn_points=p['hn_points'], days=round(p['age'], 1),
                                           published=p['published'][:10], tag=p['tag'], fav=p['fav'])


    # ---- history
    secs = round(time.time() - t0, 1)
    now_local = NOW.astimezone(TZ)
    cur = con.execute('INSERT INTO runs(ts, ts_local, seconds, sources) VALUES(?,?,?,?)',
                      (iso(NOW), now_local.isoformat(timespec='seconds'), secs, json.dumps(SOURCES)))
    run_id = cur.lastrowid
    con.executemany('INSERT INTO ranks VALUES(?,?,?,?,?,?)', [(run_id,) + r for r in ranks_rows])
    con.executemany('INSERT INTO paper_snap VALUES(?,?,?,?,?,?,?,?,?)',
                    [(run_id, p['id'], p['upvotes'], p['upvotes_at'], p['githubStars'], p['stars_at'],
                      p['mentions'], p['mentions_at'], p['hn_points']) for p in papers.values()])
    con.executemany('INSERT INTO repo_snap(run_id, full_name, stars, forks, observed_at, contributors) VALUES(?,?,?,?,?,?)',
                    [(run_id, r['full_name'], r['stars'], r['forks'], r['observed_at'],
                      (activity.get(r['full_name']) or {}).get('contributors')) for r in repos.values()])
    con.executemany(
        'INSERT INTO repo_activity_snap VALUES(?,?,?,?,?,?,?,?,?,?)',
        [(run_id, fn, a.get('issues_opened'), a.get('issues_closed'), a.get('prs_opened'),
          a.get('prs_merged'), a.get('commits'), a.get('contributors'), a.get('lookback_days'),
          a.get('observed_at')) for fn, a in activity.items()])
    con.commit()
    stamp = now_local.strftime('%Y%m%d-%H%M%S')
    save_json(os.path.join(HIST, 'runs', f'{stamp}.json'),
              {'run_id': run_id, 'ts_local': now_local.isoformat(timespec='seconds'),
               'ranks': {f'{t}/{w}': [[i, rk, sc] for (tt, ww, i, rk, sc) in ranks_rows if tt == t and ww == w]
                         for t in sorted({r[0] for r in ranks_rows}) for w, _ in WINDOWS}})
    data = {'generated_at': iso(NOW), 'generated_local': now_local.strftime('%Y-%m-%d %H:%M:%S') + ' BRT (America/Sao_Paulo)',
            'run_id': run_id, 'previous_run': prev_ts, 'run_seconds': secs, 'sources': SOURCES,
            'windows': [w for w, _ in WINDOWS], 'views': VIEWS, 'tracked': {'papers': len(papers), 'repos': len(repos)},
            'papers': out['papers'], 'repos': out['repos']}
    save_json(os.path.join(WEB, 'data.json'), data)
    log(f'done run {run_id} in {secs}s; papers {len(papers)}, repos {len(repos)}')
    for t in ('papers', 'repos'):
        print(t, {w: len(out[t][w]['all']['rows']) for w, _ in WINDOWS})
        print('  per paradigm (rows):', {v: [len(out[t][w][v]['rows']) for w, _ in WINDOWS] for v in TAGS})
    return 0

if __name__ == '__main__':
    sys.exit(main())
