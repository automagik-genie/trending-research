"""Unit tests for scoring.py: shrinkage bounds, monotonicity, missing-data handling, gap labels, movement.

Run:  python -m unittest discover tests
All numbers below are synthetic test inputs, not data.
"""
import copy, json, os, sys, unittest, sqlite3
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
from contextlib import closing

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import scoring
import hype_build
import run

CFG = scoring.load_config()


def repo(stars_rate=None, issues=None, prs=None, merge=None, commits=None, contributors=None, kind='measured', cands=('30d',), h=None):
    act = {k: v for k, v in dict(issues=issues, prs=prs, commits=commits).items() if v is not None}
    if merge is not None:
        act.update(merge=merge, prs_opened=10, prs_merged_in_opened_cohort=10 * merge)
    return dict(tag='agents', stars=100, contributors=contributors, act=act, cands=list(cands), h=h or {},
                win={'30d': dict(stars_rate=stars_rate, stars_kind=kind if stars_rate is not None else None,
                                 contrib_rate=None, gained=None)})


def features(repos, papers=None):
    return dict(asof='2026-01-01T00:00:00Z', windows=[['30d', 30]], tags=['agents'], repos=repos, papers=papers or {})


class TestPrimitives(unittest.TestCase):
    def test_shrink_bounds(self):
        for raw in (0, 12.5, 50, 99, 100):
            for prior in (0, 20, 50, 80):
                for c in (0, 0.1, 0.25, 0.5, 0.9, 1):
                    s = scoring.shrink(raw, c, prior)
                    self.assertGreaterEqual(s, min(raw, prior) - 1e-9)
                    self.assertLessEqual(s, max(raw, prior) + 1e-9)
                    self.assertTrue(0 <= s <= 100)
        self.assertEqual(scoring.shrink(90, 0, 30), 30)
        self.assertEqual(scoring.shrink(90, 1, 30), 90)
        # a 25%-confidence row can move at most a quarter of the way from the prior
        self.assertAlmostEqual(scoring.shrink(100, 0.25, 50), 62.5)
        self.assertIsNone(scoring.shrink(None, 0.5, 30))

    def test_ref_unit_monotone_and_bounded(self):
        ref = scoring.Ref([0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 1000], CFG['normalization'])
        prev = -1
        for v in (0, 0.5, 1, 2, 5, 10, 40, 55, 100, 1000, 10 ** 6):
            u = ref.unit(v)
            self.assertTrue(0 <= u <= 1)
            self.assertGreaterEqual(u, prev)
            prev = u
        self.assertEqual(ref.unit(0), 0.0)
        self.assertIsNone(ref.unit(None))
        self.assertEqual(ref.unit(10 ** 6), 1.0)   # winsorized: an outlier only caps itself

    def test_outlier_does_not_squash(self):
        base = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 3
        r1 = scoring.Ref(base, CFG['normalization'])
        r2 = scoring.Ref(base + [10 ** 7], CFG['normalization'])
        self.assertAlmostEqual(r1.unit(5), r2.unit(5), places=6)

    def test_percentile_method(self):
        n = dict(CFG['normalization'], method='percentile')
        ref = scoring.Ref([1, 2, 3, 4], n)
        self.assertEqual(ref.unit(0), 0.0)
        self.assertTrue(ref.unit(1) < ref.unit(3) <= 1)

    def test_combine_missing(self):
        w = {'a': 0.5, 'b': 0.3, 'c': 0.2}
        raw, c = scoring.combine({'a': 1.0, 'b': None, 'c': None}, w)
        self.assertEqual(raw, 100.0)             # renormalised over present signals
        self.assertAlmostEqual(c, 0.5)           # confidence = weight share present
        raw, c = scoring.combine({'a': None, 'b': None, 'c': None}, w)
        self.assertIsNone(raw)
        self.assertEqual(c, 0.0)
        _, c_half = scoring.combine({'a': 1.0, 'b': 1.0, 'c': 1.0}, w, {'a': 0.5})
        self.assertAlmostEqual(c_half, 0.75)     # weaker evidence -> lower confidence

    def test_spearman(self):
        self.assertAlmostEqual(scoring.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(scoring.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(scoring.spearman([1, 2], [1, 2]))


class TestRepoScoring(unittest.TestCase):
    def setUp(self):
        self.R = {f'o/r{i}': repo(stars_rate=i, issues=i / 2, prs=i / 4, merge=0.5, commits=i, contributors=i + 1) for i in range(1, 21)}

    def test_monotone_in_activity(self):
        prev = None
        for commits in (0, 1, 5, 20, 100):
            R = copy.deepcopy(self.R)
            R['o/x'] = repo(stars_rate=5, issues=2, prs=1, merge=0.5, commits=commits, contributors=5)
            s = {r['id']: r['score'] for r in scoring.score_run(features(R), CFG)['repos']['30d']}['o/x']
            if prev is not None:
                self.assertGreaterEqual(s, prev)
            prev = s

    def test_missing_data_lowers_coverage_and_is_shrunk(self):
        R = copy.deepcopy(self.R)
        R['o/thin'] = repo(stars_rate=10 ** 6)                       # one huge signal, nothing else
        R['o/none'] = repo()                                          # no signal at all
        out = {r['id']: r for r in scoring.score_run(features(R), CFG)['repos']['30d']}
        thin = out['o/thin']
        self.assertLessEqual(thin['coverage'], CFG['repos']['weights']['stars'] + 1e-9)
        prior = scoring.score_run(features(R), CFG)['priors']['repos']
        self.assertLessEqual(thin['score'], prior + thin['coverage'] * (100 - prior) + 0.1)
        self.assertIsNone(out['o/none']['score'])
        rows = scoring.score_run(features(R), CFG)['repos']['30d']
        self.assertEqual(rows[-1]['id'], 'o/none')                    # no-evidence rows sort last

    def test_star_farming_cap(self):
        R = copy.deepcopy(self.R)
        R['o/farm'] = repo(stars_rate=500, issues=0, prs=0, merge=0, commits=0, contributors=3)
        out = {r['id']: r for r in scoring.score_run(features(R), CFG)['repos']['30d']}
        self.assertIn('stars>activity', out['o/farm']['flags'])

    def test_solo_penalty(self):
        R = copy.deepcopy(self.R)
        R['o/solo'] = repo(stars_rate=20, issues=10, prs=5, merge=0.5, commits=20, contributors=1)
        R['o/team'] = repo(stars_rate=20, issues=10, prs=5, merge=0.5, commits=20, contributors=1.0001)
        out = {r['id']: r for r in scoring.score_run(features(R), CFG)['repos']['30d']}
        self.assertIn('solo', out['o/solo']['flags'])

    def test_persistence(self):
        R = copy.deepcopy(self.R)
        R['o/steady'] = repo(stars_rate=10, issues=5, prs=2, merge=0.5, commits=10, contributors=5, h={'7': 10, '30': 10, '90': 10})
        R['o/spike'] = repo(stars_rate=10, issues=5, prs=2, merge=0.5, commits=10, contributors=5, h={'7': 40, '30': 10, '90': 1})
        out = {r['id']: r for r in scoring.score_run(features(R), CFG)['repos']['30d']}
        self.assertGreater(out['o/steady']['score'], out['o/spike']['score'])
        self.assertIn('spike', out['o/spike']['flags'])

    def test_rate_proxy_counts_less(self):
        R = copy.deepcopy(self.R)
        R['o/m'] = repo(stars_rate=10, issues=5, contributors=4, kind='measured')
        R['o/p'] = repo(stars_rate=10, issues=5, contributors=4, kind='rate-proxy')
        out = {r['id']: r for r in scoring.score_run(features(R), CFG)['repos']['30d']}
        self.assertLess(out['o/p']['coverage'], out['o/m']['coverage'])

    def test_few_votes_count_less(self):
        # same upvote rate; 5 votes on a 1-day-old paper is a smaller sample than 200 votes on a 40-day-old one
        P = {str(i): dict(tag='agents', age=10, cands=['30d'], upvotes=20 + i, up_rate=2.0 + i / 10, up_kind='measured',
                          mentions=None, ment_rate=None, repo=None) for i in range(20)}
        P['few'] = dict(tag='agents', age=1, cands=['30d'], upvotes=5, up_rate=5.0, up_kind='since-release', mentions=None, ment_rate=None, repo=None)
        P['many'] = dict(tag='agents', age=40, cands=['30d'], upvotes=200, up_rate=5.0, up_kind='measured', mentions=None, ment_rate=None, repo=None)
        out = {r['id']: r for r in scoring.score_run(features(self.R, P), CFG)['papers']['30d']}
        self.assertLess(out['few']['coverage'], out['many']['coverage'])
        self.assertLess(out['few']['score'], out['many']['score'])
        self.assertIn('few-votes', out['few']['flags'])

    def test_v1_legacy_runs(self):
        out = scoring.score_run(features(self.R), version='1.0')
        self.assertEqual(out['repos']['30d'][0]['score'], 100.0)      # v1 divides by the window max


class TestHype(unittest.TestCase):
    def P(self):
        return {f'p{i}': dict(age=100, win={'30d': dict(mentions=i + 1, voices=i + 1,
                    platforms=['HN', 'X'][:1 + i % 2], days=30)},
                    evidence_in=dict(gh_trust=dict(v=10 * (i % 10), coverage=.9), paper=None,
                                     usage=[], discussion=dict(v=i * 3))) for i in range(12)}

    def test_discussion_is_discovery_not_usage_or_verification(self):
        P = self.P()
        P['thin'] = dict(age=100, win={'30d': dict(mentions=200, voices=150,
            platforms=['HN', 'X', 'Reddit', 'YouTube'], days=30)},
            evidence_in=dict(discussion=dict(v=10 ** 6)))
        discovery, prior = scoring.discovery_scores(P, CFG)
        thin = discovery['thin']
        self.assertEqual(thin['usage_missingness'], 'unobserved')
        self.assertEqual(thin['metrics'], [])
        self.assertIsNone(thin['verification'])
        self.assertEqual(thin['independence']['origin_ids'], [])
        self.assertIsNone(thin['freshness']['newest_evidence_at'])
        self.assertLessEqual(thin['score'], prior + thin['coverage'] * (100 - prior) + .1)
        rows, _ = scoring.hype_window(P, '30d', discovery, CFG)
        row = next(r for r in rows if r['id'] == 'thin')
        self.assertEqual(row['label'], 'insufficient')
        self.assertLessEqual(row['coverage'], .75 + 1e-9)

    def test_gap_label_coverage_boundary(self):
        for gap, attention, evidence, expected in [
                (20, .7, .6, 'attention_ahead'), (-20, .7, .6, 'evidence_ahead'),
                (3, .7, .6, 'similar'), (40, .7, .2, 'insufficient'),
                (None, .7, .7, 'insufficient'), (15, .5, .5, 'attention_ahead')]:
            with self.subTest(gap=gap, evidence=evidence):
                self.assertEqual(scoring.gap_label(gap, attention, evidence, CFG), expected)

    def test_single_platform_penalty(self):
        P = self.P()
        for pid, platforms in [('one', ['HN']), ('two', ['HN', 'X'])]:
            P[pid] = dict(age=100, win={'30d': dict(mentions=6, voices=6, platforms=platforms, days=30)},
                          evidence_in={})
        discovery, _ = scoring.discovery_scores(P, CFG)
        rows = {r['id']: r for r in scoring.hype_window(P, '30d', discovery, CFG)[0]}
        self.assertLess(rows['one']['score'], rows['two']['score'])
        self.assertIn('single-platform', rows['one']['flags'])


class TestMetricFamilies(unittest.TestCase):
    def metric(self, kind, value, **extra):
        return dict(type=kind, value=value, unit='operations' if kind == 'npm_downloads' else 'customers',
                    period=dict(start='2020-01-01T00:00:00Z', end='2020-02-01T00:00:00Z'),
                    scope='synthetic fixture', **extra)

    def test_source_selection_preserves_units_zero_and_unknown(self):
        sigs = [dict(type=t, value=v, unit=u, source_url='https://example.test/' + t)
                for t, v, u in [('npm_downloads', 1000000, 'downloads'),
                               ('reported_users', 0, 'users'), ('business_clients', None, 'customers')]]
        rows = hype_build.usage_signals(sigs)
        self.assertEqual([(r['value'], r['metric_family'], r['missingness']) for r in rows],
                         [(1000000, 'download_operations', 'observed'), (0, 'users', 'observed'),
                          (None, 'business_customers', 'unobserved')])

    def test_incompatible_customers_cannot_rescale_downloads(self):
        inputs = {'a': [self.metric('npm_downloads', 10)], 'b': [self.metric('npm_downloads', 100)],
                  'customer': [self.metric('business_clients', 10 ** 9)]}
        before = scoring.usage_metrics(inputs, CFG)
        inputs['customer'][0]['value'] = 10 ** 15
        after = scoring.usage_metrics(inputs, CFG)
        self.assertAlmostEqual(before['a'][0]['normalized'], 0.5195737065)
        self.assertEqual(before['a'][0]['normalized'], after['a'][0]['normalized'])
        self.assertNotEqual(before['a'][0]['cohort'], before['customer'][0]['cohort'])

    def test_unknown_or_different_period_scope_is_not_comparable(self):
        a = self.metric('npm_downloads', 10)
        b = self.metric('npm_downloads', 100)
        b['period']['end'] = '2020-03-01T00:00:00Z'
        c = self.metric('npm_downloads', 1000)
        c['scope'] = None
        rows = scoring.usage_metrics({'a': [a], 'b': [b], 'c': [c]}, CFG)
        self.assertEqual(rows['a'][0]['normalized'], 1.0)
        self.assertNotEqual(rows['a'][0]['cohort'], rows['b'][0]['cohort'])
        self.assertIsNone(rows['c'][0]['normalized'])
        self.assertIsNone(rows['c'][0]['cohort'])

    def test_closed_missing_usage_never_becomes_zero_or_low_value(self):
        P = {'closed': dict(evidence_in={}), 'observed': dict(evidence_in=dict(
             usage=[self.metric('business_clients', 0)]))}
        rows, _ = scoring.discovery_scores(P, CFG)
        self.assertIsNone(rows['closed']['score'])
        self.assertEqual(rows['closed']['usage_missingness'], 'unobserved')
        self.assertEqual(rows['closed']['metrics'], [])
        self.assertIsNone(rows['observed']['score'])  # Usage is not a discovery-composite magnitude.
        self.assertEqual(rows['observed']['metrics'][0]['value'], 0)
        self.assertEqual(rows['observed']['metrics'][0]['normalized'], 0)


class TestPRCohort(unittest.TestCase):
    def feature_activity(self, activity):
        with closing(sqlite3.connect(':memory:')) as con:
            con.executescript('CREATE TABLE paper_snap(arxiv_id,upvotes,upvotes_at,stars,stars_at,mentions,mentions_at);'
                              'CREATE TABLE repo_snap(full_name,stars,observed_at,contributors);')
            repos = {'o/x': dict(observed_at='2020-01-01T00:00:00Z', created_dt=None,
                      pushed_dt=None, age=100, stars=100, tag='agents', fav=False, url='https://github.com/o/x')}
            return run.build_features({}, repos, {}, {'o/x': activity}, con, CFG)['repos']['o/x']['act']

    def test_extraction_uses_created_and_merged_intersection_not_merge_events(self):
        # Ten created in-window, four of those merged; sixteen older PRs also merged in-window.
        since = (run.TODAY_LOCAL - run.timedelta(days=30)).isoformat()
        newer = run.TODAY_LOCAL.isoformat()
        older = (run.TODAY_LOCAL - run.timedelta(days=60)).isoformat()
        records = ([dict(created=newer, merged=newer) for _ in range(4)] +
                   [dict(created=newer, merged=None) for _ in range(6)] +
                   [dict(created=older, merged=newer) for _ in range(16)])

        def public_api(path, **kwargs):
            q = parse_qs(urlparse(path).query).get('q', [''])[0]
            if 'type:pr' not in q:
                return {'total_count': 0}, {}
            selected = records
            if 'created:>' in q:
                selected = [r for r in selected if r['created'] > since]
            if 'is:merged' in q:
                selected = [r for r in selected if r['merged'] is not None]
            if 'merged:>' in q:
                selected = [r for r in selected if r['merged'] and r['merged'] > since]
            return {'total_count': len(selected)}, {}

        with patch.object(run, 'gh_get', side_effect=public_api), patch.object(run, 'load_json', return_value={}), \
             patch.object(run, 'save_json'), patch.object(run, 'gh_core_remaining', return_value=(0, 0)), \
             patch.object(run, 'OFFLINE', False), patch.object(run, 'note'):
            activity = run.fetch_repo_activity({}, ['o/x'])['o/x']
        act = self.feature_activity(activity)
        self.assertEqual(act['prs_opened'], 10)
        self.assertEqual(act['prs_merged'], 20)
        self.assertEqual(act['merge'], .4)

    def test_unknown_empty_and_invalid_cohort_remain_missing(self):
        for activity in [dict(prs_opened=10, prs_merged=20),
                         dict(prs_opened=0, prs_merged=0, prs_merged_in_opened_cohort=0),
                         dict(prs_opened=10, prs_merged_in_opened_cohort=11)]:
            with self.subTest(activity=activity):
                act = self.feature_activity(activity)
                self.assertIsNone(act['merge'])
        act = self.feature_activity(dict(prs_opened=10, prs_merged=20, prs_merged_in_opened_cohort=4))
        self.assertEqual(act['merge'], .4)
        act['merge'] = 1.0  # Stale event ratio cannot override the observed compatible cohort.
        F = features({'o/x': repo(prs=1)})
        F['repos']['o/x']['act'] = act
        current = scoring.score_run(F, CFG)['repos']['30d'][0]
        self.assertEqual(current['raw'], 70.0)

    def test_partial_search_response_cannot_become_zero_observation(self):
        for payload in ({'total_count': 7, 'incomplete_results': True}, {}):
            with self.subTest(payload=payload), patch.object(run, 'gh_get', return_value=(payload, {})), \
                 patch.object(run, 'load_json', return_value={}), patch.object(run, 'save_json'), \
                 patch.object(run, 'gh_core_remaining', return_value=(0, 0)), \
                 patch.object(run, 'OFFLINE', False), patch.object(run, 'note'):
                activity = run.fetch_repo_activity({}, ['o/x'])['o/x']
                self.assertIsNone(activity['prs_opened'])
                self.assertIsNone(self.feature_activity(activity).get('merge'))


class TestMovement(unittest.TestCase):
    def test_hysteresis_new_and_reset(self):
        prev = {'a': (1, 80.0), 'b': (2, 79.5), 'c': (3, 60.0), 'd': (4, 50.0)}
        cur = [('b', 80.2), ('a', 80.0), ('d', 70.0), ('c', 60.0), ('e', 10.0)]
        mv = scoring.movement(cur, prev, CFG)
        self.assertEqual(mv[0]['s'], 'same')        # b moved 1 place, below min_rank_change
        self.assertEqual(mv[2]['s'], 'same')        # d moved 1 among common items
        self.assertEqual(mv[4]['s'], 'new')
        mv = scoring.movement([('d', 90.0), ('a', 80.0), ('b', 79.0), ('c', 60.0)], prev, CFG)
        self.assertEqual(mv[0], {'s': 'up', 'd': 3})
        self.assertEqual(scoring.movement(cur, prev, CFG, comparable=False)[0]['s'], 'reset')
        changed = scoring.movement([('x', 1.0), ('y', 2.0), ('z', 3.0), ('a', 80.0)], prev, CFG)
        self.assertTrue(all(m['s'] == 'new' for m in changed))
        self.assertTrue(all(m['s'] == 'new' for m in scoring.movement(cur, {}, CFG)))


class TestFixture(unittest.TestCase):
    """The committed fixture (a real subset of two runs) scores under v1 and v2 without errors."""
    def test_fixture_scores(self):
        fa = os.path.join(HERE, 'fixtures', 'features_a.json')
        if not os.path.exists(fa):
            self.skipTest('fixture missing')
        with open(fa) as f:
            F = json.load(f)
        for v in ('1.0', '2.0', scoring.SCORING_VERSION):
            out = scoring.score_run(F, CFG, v)
            for tab in ('papers', 'repos'):
                for rows in out[tab].values():
                    for r in rows:
                        self.assertTrue(r['score'] is None or 0 <= r['score'] <= 100)


if __name__ == '__main__':
    unittest.main()
