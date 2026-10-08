#!/usr/bin/env python3
"""AI-research trend tracker: fetch -> features -> score (scoring.py) -> web/data.json + history.

Run:   python3 run.py                full fetch + score (writes web/data.json, web/hype.json, history/)
       python3 run.py --rescore      no network: re-score the cached inputs of the last full run with the
                                     current scoring.py / scoring_config.json (handy for weight-change PRs)
       python3 run.py --offline --asof <ISO> --features-only <out.json.gz>
                                     write only the feature snapshot (used by eval.py; reads the DB read-only)
Env:   TRENDING_CACHE=<dir>          use another cache directory (e.g. an archived one)

Sources (all public): arXiv API, Hugging Face papers API, Hacker News Algolia API, GitHub REST API
(search, stargazer timestamps, contributors; the `gh auth` token is used when logged in). Every source
is wrapped: on failure the last good cached payload is reused and the failure is recorded in
data.json["sources"]. No metric is ever invented: unknown -> null (rendered as '—').

Scoring lives in scoring.py (algorithm v2, weights in scoring_config.json, explained in METHODOLOGY.md).
This file only builds per-item *features* (rates, momentum from history snapshots, activity) and stores
them in history/runs/<stamp>-features.json.gz so eval.py can re-score any run under v1 or v2.

HYPE tab: if hype/hype_research.json exists, hype_build.build() turns it into web/hype.json and stores
HYPE ranks in the same history DB (tab 'hype').
"""
import os, sys, re, json, time, math, sqlite3, fcntl, threading, traceback, gzip, bisect
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import scoring
WEB, HIST = (os.path.join(BASE, d) for d in ('web', 'history'))
CACHE = os.environ.get('TRENDING_CACHE') or os.path.join(BASE, 'cache')
DB = os.path.join(HIST, 'trending.db')
TZ = ZoneInfo('America/Sao_Paulo')
UA = 'trending-research/2.0 (+https://github.com/namastex888/trending-research)'

def _arg(name):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    return None

_MAIN = __name__ == '__main__'
RESCORE = _MAIN and '--rescore' in sys.argv
OFFLINE = RESCORE or (_MAIN and '--offline' in sys.argv)
FEATURES_ONLY = _arg('--features-only') if _MAIN else None
ASOF = _arg('--asof') if _MAIN else None

def _last_full_run_ts():
    try:
        con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
        cols = [r[1] for r in con.execute('PRAGMA table_info(runs)')]
        q = "SELECT ts FROM runs WHERE sources NOT LIKE '{\"hype_build\"%'" + (" AND (kind IS NULL OR kind='full')" if 'kind' in cols else '')
        row = con.execute(q + ' ORDER BY run_id DESC LIMIT 1').fetchone()
        return row[0] if row else None
    except Exception:
        return None

if RESCORE and not ASOF:
    ASOF = _last_full_run_ts()
NOW = (datetime.fromisoformat(ASOF.replace('Z', '+00:00')).astimezone(timezone.utc) if ASOF
       else datetime.now(timezone.utc))
TODAY_LOCAL = NOW.astimezone(TZ).date()
WINDOWS = [('1d', 1), ('7d', 7), ('30d', 30), ('90d', 90), ('180d', 180), ('1y', 365), ('overall', None)]
TOPN = 100
HF_PAPER_BUDGET = 400      # per-paper HF lookups per run (HF anon limit: 500 req / 5 min)
HN_BUDGET = 900            # HN Algolia lookups per run (limit 10k/h)
for d in (WEB, HIST, CACHE, os.path.join(HIST, 'runs')):
    os.makedirs(d, exist_ok=True)

def nap(sec):
    if not OFFLINE: time.sleep(sec)

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
    if OFFLINE: raise HTTPErr(0, 'offline mode (no network)')
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
GH_SEARCH_RL_AUTH = Interval(2.1)  # authenticated search: 30 req/min

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
        if search and not OFFLINE: (GH_SEARCH_RL_AUTH if GH_TOKEN else GH_SEARCH_RL).wait()
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
                err = str(e); nap(5 * (attempt + 1))
                if OFFLINE: break
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
        if c and (OFFLINE or (time.time() - c.get('ts', 0)) < ttl_h * 3600):
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
    if OFFLINE:
        note('GitHub stargazers API', 'cache', f'offline: {len(cache)} cached repos'); return cache
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
    if consec_fail >= 3 and 'HTTP 404' in last_err:
        note('GitHub stargazers API', 'unavailable', f'the stargazers endpoint answered HTTP 404 for every repo tried (even authenticated); '
             f'star growth comes from our own snapshots instead. {len(cache)} cached')
    elif consec_fail >= 3:
        note('GitHub stargazers API', 'failed', f'stopped after 3 consecutive errors ({last_err}); star timestamps for {done} repos this run, {len(cache)} cached')
    elif budget == 0:
        note('GitHub stargazers API', 'skipped', f'core rate limit exhausted (unauthenticated 60/h); resets {datetime.fromtimestamp(reset, TZ).strftime("%H:%M")} BRT. Using cached timestamps for {len(cache)} repos')
    else:
        note('GitHub stargazers API', 'ok', f'{used} requests, star timestamps for {done} new repos ({len(cache)} cached total)')
    return cache

ACTIVITY_LOOKBACK = 30   # days for cached activity snapshot; scaled into each window
ACTIVITY_BUDGET = 30     # repos to enrich per run (4 search queries each ≈ 3–6 min)
ACTIVITY_BUDGET_AUTH = 100  # with gh auth (30 search req/min): 5 queries/repo ≈ 17 min

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
    if OFFLINE:
        note('GitHub activity (issues/PRs/commits)', 'cache', f'offline: {len(cache)} cached'); return cache
    since = (TODAY_LOCAL - timedelta(days=ACTIVITY_LOOKBACK)).isoformat()
    todo, done, fail = [], 0, 0
    for fn in order:
        c = cache.get(fn)
        if c and time.time() - c.get('ts', 0) < 18 * 3600: continue
        todo.append(fn)
        if len(todo) >= (ACTIVITY_BUDGET_AUTH if GH_TOKEN else ACTIVITY_BUDGET): break
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
    if OFFLINE: return activity
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
    if OFFLINE: return cache
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
    if OFFLINE: return cache
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
    if OFFLINE: return
    try:
        http_get('https://www.reddit.com/search.json?q=arxiv&limit=1', timeout=15)
        note('Reddit search JSON', 'not used', 'reachable but not wired in (HN used for mentions)')
    except Exception as e:
        note('Reddit search JSON', 'failed', f'HTTP {getattr(e, "code", "error")} (blocked without auth) -> social mentions come from Hacker News only')

# ---------------------------------------------------------------- history DB
def db(readonly=False):
    if readonly:
        return sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
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

    for t, col in (('repo_snap', 'contributors INT'), ('runs', 'scoring_version TEXT'), ('runs', 'kind TEXT'),
                   ('runs', 'config_sha TEXT')):
        try: con.execute(f'ALTER TABLE {t} ADD COLUMN {col}')
        except Exception: pass
    return con

def run_version(con, run_id):
    try:
        row = con.execute('SELECT scoring_version FROM runs WHERE run_id=?', (run_id,)).fetchone()
        return (row[0] if row and row[0] else '1.x')
    except Exception:
        return '1.x'

def prev_ranks(con, tabs=('papers', 'repos')):
    """Previous ranks+scores per tab = the latest run that recorded that tab (hype_build.py can add
    HYPE-only runs). Returns ({(tab, win): {id: (rank, score)}}, ts_local, {tab: scoring_version})."""
    out, ts, ver = {}, None, {}
    for t in tabs:
        r = con.execute('SELECT MAX(run_id) FROM ranks WHERE tab=?', (t,)).fetchone()[0]
        if r is None: continue
        ver[t] = run_version(con, r)
        for tab, win, item, rank, score in con.execute('SELECT tab, win, item_id, rank, score FROM ranks WHERE run_id=? AND (tab=? OR tab LIKE ?)',
                                                       (r, t, t + '|%')):
            out.setdefault((tab, win), {})[item] = (rank, score)
        if ts is None: ts = con.execute('SELECT ts_local FROM runs WHERE run_id=?', (r,)).fetchone()[0]
    return out, ts, ver

def repo_snapshot_gain(con, fn, stars_now, days):
    """Stars gained over ~`days` from our own snapshots: needs a snapshot observed near the window start."""
    start = NOW - timedelta(days=days)
    tol = timedelta(days=max(0.15 * days, 0.25))
    row = con.execute('SELECT stars, observed_at FROM repo_snap WHERE full_name=? AND observed_at BETWEEN ? AND ? AND observed_at <= ? '
                      'ORDER BY observed_at DESC LIMIT 1', (fn, iso(start - tol), iso(start + tol), iso(NOW))).fetchone()
    if not row: return None
    span = (NOW - parse_dt(row[1])).total_seconds() / 86400
    if span < 0.25: return None
    return stars_now - row[0], span

# ---------------------------------------------------------------- features (inputs to scoring.py)
_DT = {}
def pdt(s):
    if not s: return None
    v = _DT.get(s)
    if v is None: v = _DT[s] = parse_dt(s)
    return v

def load_snapshots(con):
    """All earlier observations from the history DB: papers (upvotes, stars, HN mentions) and repos (stars, contributors)."""
    ps, rs = {}, {}
    for row in con.execute('SELECT arxiv_id, upvotes, upvotes_at, stars, stars_at, mentions, mentions_at FROM paper_snap'):
        ps.setdefault(row[0], []).append(row[1:])
    for fn, st, obs, ct in con.execute('SELECT full_name, stars, observed_at, contributors FROM repo_snap'):
        rs.setdefault(fn, []).append((obs, st, ct))
    return ps, rs

def snap_rate(series, now_val, now_at, target_days, min_span):
    """Real delta from our own snapshots. series = [(observed_at_iso, value)]. Picks the earlier observation
    closest to (now_at - target_days) that is at least min_span days old and not after NOW (as-of).
    -> (rate/day >= 0, delta, span_days) or None."""
    if not isinstance(now_val, (int, float)) or now_at is None: return None
    target, best = now_at - timedelta(days=target_days), None
    for at, v in series:
        if v is None: continue
        t = pdt(at)
        if t is None or t > NOW: continue
        span = (now_at - t).total_seconds() / 86400
        if span < min_span: continue
        key = abs((t - target).total_seconds())
        if best is None or key < best[0]: best = (key, v, span)
    if not best: return None
    delta = now_val - best[1]
    return max(delta, 0) / best[2], delta, best[2]

def build_features(papers, repos, sg, activity, con, cfg):
    """Everything scoring.py needs, per item and window. Missing stays None (never invented)."""
    min_span = cfg['momentum']['min_snapshot_span_days']
    pmd = cfg['momentum']['paper_momentum_days']
    ps, rs = load_snapshots(con)
    sgt = {}
    for fn, z in sg.items():
        if not z or z.get('times') is None: continue
        fetched = datetime.fromtimestamp(z['ts'], timezone.utc)
        if fetched > NOW + timedelta(hours=6): continue          # fetched after the as-of time
        sgt[fn] = (fetched, z.get('complete'), pdt(z.get('oldest')),
                   sorted(pdt(t).timestamp() for t in z['times'] if pdt(t)))

    def stargazer_gain(fn, use):
        z = sgt.get(fn)
        if not z: return None
        fetched, complete, oldest, ts = z
        wstart = fetched - timedelta(days=use)
        if not (complete or (oldest and oldest <= wstart)): return None
        return bisect.bisect_right(ts, fetched.timestamp()) - bisect.bisect_left(ts, wstart.timestamp())

    F = {'asof': iso(NOW), 'scoring_version': scoring.SCORING_VERSION, 'windows': WINDOWS, 'tags': TAGS,
         'repos': {}, 'papers': {}}
    for fn, r in repos.items():
        a = activity.get(fn) or {}
        lb = max(a.get('lookback_days') or ACTIVITY_LOOKBACK, 1)
        act = {}
        io, ic, po, pm, cm = (a.get(k) for k in ('issues_opened', 'issues_closed', 'prs_opened', 'prs_merged', 'commits'))
        if io is not None and ic is not None: act.update(issues=(io + ic) / lb, issues_opened=io, issues_closed=ic)
        if po is not None:
            act.update(prs=po / lb, prs_opened=po)
            if pm is not None: act.update(merge=(pm / po) if po > 0 else 0.0, prs_merged=pm)
        if cm is not None: act.update(commits=cm / lb, commits_n=cm)
        contributors = a.get('contributors')
        rsn = rs.get(fn, [])
        now_obs = pdt(r['observed_at'])
        c_at = pdt(a.get('contributors_at') or a.get('observed_at')) or now_obs
        h = {}
        for hz in cfg['repos']['persistence_horizons']:
            if r['created_dt'] and r['created_dt'] >= NOW - timedelta(days=hz): continue
            g = stargazer_gain(fn, hz)
            if g is not None: h[str(hz)] = round(g / hz, 4)
        cands, win = [], {}
        for wname, days in WINDOWS:
            is_c = days is None or bool((r['created_dt'] and r['created_dt'] >= NOW - timedelta(days=days))
                                        or (r['pushed_dt'] and r['pushed_dt'] >= NOW - timedelta(days=days)))
            if not is_c and wname != '30d': continue       # 30d is always kept: it is the trust/reference window
            if is_c: cands.append(wname)
            use = 90 if days is None else days
            ustart = NOW - timedelta(days=use)
            born = bool(r['created_dt'] and r['created_dt'] >= ustart)
            if born:
                sr, gained, gspan, kind, src, mw = r['stars'] / max(r['age'], 1), r['stars'], round(r['age'], 1), 'measured', 'born-in-window', 1.0
            else:
                g = stargazer_gain(fn, use)
                s = None if g is not None else snap_rate([(o, st) for o, st, _ in rsn], r['stars'], now_obs, use, min_span)
                proxy = r['stars'] / max(r['age'], 1)
                if g is not None: sr, gained, gspan, kind, src, mw = g / use, g, use, 'measured', 'stargazers', 1.0
                elif s:      # real delta; if it spans less than the window, blend it with the since-creation rate
                    mw = min(1.0, s[2] / use)
                    sr, gained, gspan, src = mw * s[0] + (1 - mw) * proxy, s[1], round(s[2], 2), 'snapshots'
                    kind = 'measured' if mw >= 1 else 'blended'
                else: sr, gained, gspan, kind, src, mw = proxy, None, None, 'rate-proxy', 'stars/age', 0.0
            if src in ('born-in-window', 'stargazers'): sr1, g1 = sr, gained          # legacy v1 rule, for eval.py
            else:
                g = repo_snapshot_gain(con, fn, r['stars'], use)
                sr1, g1 = (max(g[0], 0) / max(g[1], 0.25), g[0]) if g else (None, None)
            cr = cg = None
            if contributors is not None:
                if born: cg, cr = contributors, contributors / max(r['age'], 1)
                else:
                    s = snap_rate([(o, ct) for o, _, ct in rsn], contributors, c_at, use, min_span)
                    if s: cr, cg = s[0], s[1]
            win[wname] = dict(stars_rate=sr, stars_kind=kind, stars_mw=round(mw, 3), stars_src=src, gained=gained, gspan=gspan,
                              stars_rate_v1=sr1, gained_v1=g1, contrib_rate=cr, contrib_gained=cg)
        F['repos'][fn] = dict(tag=r['tag'], fav=r['fav'], stars=r['stars'], contributors=contributors, act=act,
                              cands=cands, win=win, h=h, age=round(r['age'], 2))
    by_url = {r['url'].lower().rstrip('/'): fn for fn, r in repos.items()}
    for pid, p in papers.items():
        if not p['pub_dt'] or p['age'] is None: continue
        cands = [w for w, d in WINDOWS if in_window_date(local_date(p['pub_dt']), d)]
        if not cands: continue
        sn, age = ps.get(pid, []), p['age']
        a1 = max(age, 1)

        def rate(cur, cur_at, vi, ti):
            # -> (rate, kind, momentum weight). Real delta over the momentum horizon when our snapshots span it;
            # a shorter span is blended with the since-release rate in proportion span / horizon.
            if cur is None: return None, None, 0.0
            base, kind = cur / a1, ('since-release' if age <= pmd else 'rate-proxy')
            s = snap_rate([(x[ti], x[vi]) for x in sn], cur, pdt(cur_at), pmd, min_span)
            if not s: return base, kind, (1.0 if kind == 'since-release' else 0.0)
            mw = min(1.0, s[2] / pmd)
            if mw >= 1: return s[0], 'measured', 1.0
            return mw * s[0] + (1 - mw) * base, ('since-release' if kind == 'since-release' else 'blended'), (1.0 if kind == 'since-release' else mw)
        up_rate, up_kind, up_mw = rate(p['upvotes'], p['upvotes_at'], 0, 1)
        ment_rate, ment_kind, ment_mw = rate(p['mentions'], p['mentions_at'], 4, 5)
        st = snap_rate([(x[3], x[2]) for x in sn], p['githubStars'], pdt(p['stars_at']), pmd, min_span)
        repo = by_url.get(p['githubRepo'].lower().rstrip('/').removesuffix('.git')) if p.get('githubRepo') else None
        F['papers'][pid] = dict(tag=p['tag'], age=round(age, 2), cands=cands,
                                upvotes=p['upvotes'], up_rate=up_rate, up_kind=up_kind, up_mw=round(up_mw, 3),
                                up_rate_v1=p['upvotes'] / a1 if p['upvotes'] is not None else None,
                                mentions=p['mentions'], ment_rate=ment_rate, ment_kind=ment_kind, ment_mw=round(ment_mw, 3),
                                ment_rate_v1=p['mentions'] / a1 if p['mentions'] is not None else None,
                                repo=repo, repo_star_rate=st[0] if st else None)
    return F

def save_features(F, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with gzip.open(path + '.tmp', 'wt') as f: json.dump(F, f, separators=(',', ':'))
    os.replace(path + '.tmp', path)

def in_window_date(d, days):
    if days is None: return True
    return d is not None and d >= TODAY_LOCAL - timedelta(days=days)

def local_date(dt): return dt.astimezone(TZ).date() if dt else None

# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    if not FEATURES_ONLY:     # feature-only replays write nothing shared, so they need no lock
        lockf = open(os.path.join(BASE, '.run.lock'), 'w')
        try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError: print('another run.py is in progress; exiting'); return 1
    if not OFFLINE: gh_token()
    log('start', f'scoring v{scoring.SCORING_VERSION}; as of {iso(NOW)}; ' + ('OFFLINE (cached inputs only)' if OFFLINE else
        'gh auth: ' + ('yes' if GH_TOKEN else 'no (unauthenticated GitHub API)')))

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

    cfg = scoring.load_config()
    con = db(readonly=bool(FEATURES_ONLY))
    F = build_features(papers, repos, sg, activity, con, cfg)
    if FEATURES_ONLY:
        save_features(F, FEATURES_ONLY)
        log(f'features only -> {FEATURES_ONLY}: {len(F["papers"])} papers, {len(F["repos"])} repos (as of {F["asof"]})')
        return 0
    S = scoring.score_run(F, cfg)                      # v2 (the published scores)
    S1 = scoring.score_run(F, version='1.0')           # legacy v1, kept for transparency / eval.py
    prev, prev_ts, prev_ver = prev_ranks(con)
    out = {'papers': {'items': {}}, 'repos': {'items': {}}}
    ranks_rows = []
    VIEWS = ['all'] + TAGS     # 'all' = the top-100; per-paradigm views rank within that tag
    tag_of = {'papers': {pid: f['tag'] for pid, f in F['papers'].items()},
              'repos': {fn: f['tag'] for fn, f in F['repos'].items()}}

    def emit(tab, wname, rows, extra):
        views = {}
        for v in VIEWS:
            sub = rows if v == 'all' else [c for c in rows if tag_of[tab].get(c['id']) == v]
            hkey = tab if v == 'all' else f'{tab}|{v}'
            pr = prev.get((hkey, wname), {})
            top = sub[:TOPN]
            mvs = scoring.movement([(c['id'], c['score']) for c in top], pr, cfg,
                                   comparable=prev_ver.get(tab) == scoring.SCORING_VERSION)
            lst = []
            for i, (c, mv) in enumerate(zip(top, mvs), 1):
                ranks_rows.append((hkey, wname, c['id'], i, c['score']))
                lst.append(dict(id=c['id'], rank=i, prev=(pr.get(c['id']) or (None,))[0], mv=mv, score=c['score'],
                                confidence=c['conf'], raw=c['raw'], flags=c['flags'] or None, kind=c['kind'], **extra(c, wname)))
            views[v] = {'rows': lst, 'candidates': len(sub)}
        out[tab][wname] = views

    # ---- repos per window (trust index)
    def repo_extra(c, wname):
        f = F['repos'][c['id']]
        w = f['win'].get(wname) or {}
        days = dict(WINDOWS)[wname]
        a = f['act'] if (days is None or days >= cfg['momentum']['activity_min_window_days']) else {}
        return dict(gained=w.get('gained'), gspan=w.get('gspan'), src=w.get('stars_src'),
                    issues_opened=a.get('issues_opened'), issues_closed=a.get('issues_closed'),
                    prs_opened=a.get('prs_opened'), prs_merged=a.get('prs_merged'), merge_rate=a.get('merge'),
                    commits=a.get('commits_n'), contributors=f.get('contributors'), contrib_gained=w.get('contrib_gained'))
    for wname, _ in WINDOWS:
        emit('repos', wname, S['repos'][wname], repo_extra)
    repo_trust = {fn: {'trust': S['trust'][fn][0], 'confidence': S['trust'][fn][1],
                       'trust_v1': S1['trust'][fn][0], 'confidence_v1': S1['trust'][fn][1]} for fn in repos}
    if not FEATURES_ONLY:
        save_json(os.path.join(CACHE, 'repo_trust.json'), {'generated_at': iso(NOW), 'scoring_version': scoring.SCORING_VERSION,
                                                           'repos': repo_trust})
    used = {row['id'] for w in out['repos'] if w != 'items' for v in out['repos'][w].values() for row in v['rows']}
    for fn in used:
        r = repos[fn]
        pp = papers.get(r['paper']) if r['paper'] else None
        out['repos']['items'][fn] = dict(
            url=r['url'], owner=r['owner'], desc=r['description'][:200], stars=r['stars'],
            forks=r['forks'], paper=r['paper'], paper_title=pp['title'] if pp else None,
            pushed=r['pushed_at'], created=r['created_at'][:10], tag=r['tag'], fav=r['fav'],
            contributors=F['repos'][fn].get('contributors'))

    # ---- papers per window
    for wname, _ in WINDOWS:
        emit('papers', wname, S['papers'][wname], lambda c, w: {})
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
    stamp = now_local.strftime('%Y%m%d-%H%M%S')
    kind = 'rescore' if RESCORE else 'full'
    if RESCORE:     # keep the source status of the run whose cached inputs we re-scored
        try:
            row = con.execute("SELECT sources FROM runs WHERE ts=? AND (kind IS NULL OR kind='full') ORDER BY run_id DESC LIMIT 1",
                              (iso(NOW),)).fetchone()
            prev_sources = json.loads(row[0]) if row else {}
        except Exception:
            prev_sources = {}
        SOURCES.clear(); SOURCES.update(prev_sources)
        note('Rescore', 'ok', f'offline re-score with scoring v{scoring.SCORING_VERSION} of the cached inputs of the run at '
             f'{now_local.strftime("%Y-%m-%d %H:%M")} BRT; no network calls')
    cur = con.execute('INSERT INTO runs(ts, ts_local, seconds, sources, scoring_version, kind, config_sha) VALUES(?,?,?,?,?,?,?)',
                      (iso(NOW), now_local.isoformat(timespec='seconds'), secs, json.dumps(SOURCES),
                       scoring.SCORING_VERSION, kind, scoring.config_sha()))
    run_id = cur.lastrowid
    con.executemany('INSERT INTO ranks VALUES(?,?,?,?,?,?)', [(run_id,) + r for r in ranks_rows])
    if not OFFLINE:     # snapshots only for real observations (a rescore would duplicate them)
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
    save_features(F, os.path.join(HIST, 'runs', f'{stamp}-features.json.gz'))
    # ---- HYPE tab (web/hype.json) from the social-research dossier, if present
    if os.path.exists(os.path.join(BASE, 'hype', 'hype_research.json')):
        try:
            import hype_build
            h = hype_build.build(con=con, run_id=run_id, repo_trust=repo_trust, tagger=tag_for, tags=TAGS, log=log, cfg=cfg)
            hype_rows = {w: len(h[w]['all']['rows']) for w in h['windows'] if h['windows'][w].get('enabled')}
            note('HYPE (social research dossier)', 'ok', f'{h["n_projects"]} projects from hype/hype_research.json '
                 f'(research {h.get("research_generated_at") or "?"}); rows {hype_rows}')
        except Exception as e:
            traceback.print_exc(); note('HYPE (social research dossier)', 'failed', str(e)[:120])
        con.execute('UPDATE runs SET sources=? WHERE run_id=?', (json.dumps(SOURCES), run_id)); con.commit()
    save_json(os.path.join(HIST, 'runs', f'{stamp}.json' if kind == 'full' else f'{stamp}-rescore-v{scoring.SCORING_VERSION}.json'),
              {'run_id': run_id, 'ts_local': now_local.isoformat(timespec='seconds'), 'scoring_version': scoring.SCORING_VERSION,
               'ranks': {f'{t}/{w}': [[i, rk, sc] for (tt, ww, i, rk, sc) in ranks_rows if tt == t and ww == w]
                         for t in sorted({r[0] for r in ranks_rows}) for w, _ in WINDOWS}})
    resets = sorted({t for t in ('papers', 'repos') if prev_ver.get(t) and prev_ver[t] != scoring.SCORING_VERSION})
    data = {'generated_at': iso(NOW), 'generated_local': now_local.strftime('%Y-%m-%d %H:%M:%S') + ' BRT (America/Sao_Paulo)',
            'run_id': run_id, 'run_kind': kind, 'previous_run': prev_ts, 'run_seconds': secs, 'sources': SOURCES,
            'scoring_version': scoring.SCORING_VERSION, 'config_sha': scoring.config_sha(), 'priors': S['priors'],
            'movement_note': (f'movement reset: the previous run used scoring v{prev_ver[resets[0]]}' if resets else None),
            'windows': [w for w, _ in WINDOWS], 'views': VIEWS, 'tracked': {'papers': len(papers), 'repos': len(repos)},
            'papers': out['papers'], 'repos': out['repos']}
    save_json(os.path.join(WEB, 'data.json'), data)
    try:    # the page renders web/METHODOLOGY.md; the repo-root METHODOLOGY.md is the source of truth
        import shutil; shutil.copyfile(os.path.join(BASE, 'METHODOLOGY.md'), os.path.join(WEB, 'METHODOLOGY.md'))
    except OSError:
        pass
    log(f'done run {run_id} ({kind}, scoring v{scoring.SCORING_VERSION}) in {secs}s; papers {len(papers)}, repos {len(repos)}')
    for t in ('papers', 'repos'):
        print(t, {w: len(out[t][w]['all']['rows']) for w, _ in WINDOWS})
    return 0


if __name__ == '__main__':
    sys.exit(main())
