"""Unit tests for scoring.py: shrinkage bounds, monotonicity, missing-data handling, gap labels, movement.

Run:  python -m unittest discover tests
All numbers below are synthetic test inputs, not data.
"""
import copy, json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import scoring

CFG = scoring.load_config()


def repo(stars_rate=None, issues=None, prs=None, merge=None, commits=None, contributors=None, kind='measured', cands=('30d',), h=None):
    act = {k: v for k, v in dict(issues=issues, prs=prs, merge=merge, commits=commits).items() if v is not None}
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

    def test_missing_data_lowers_confidence_and_is_shrunk(self):
        R = copy.deepcopy(self.R)
        R['o/thin'] = repo(stars_rate=10 ** 6)                       # one huge signal, nothing else
        R['o/none'] = repo()                                          # no signal at all
        out = {r['id']: r for r in scoring.score_run(features(R), CFG)['repos']['30d']}
        thin = out['o/thin']
        self.assertLessEqual(thin['conf'], CFG['repos']['weights']['stars'] + 1e-9)
        prior = scoring.score_run(features(R), CFG)['priors']['repos']
        self.assertLessEqual(thin['score'], prior + thin['conf'] * (100 - prior) + 0.1)
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
        self.assertLess(out['o/p']['conf'], out['o/m']['conf'])

    def test_few_votes_count_less(self):
        # same upvote rate; 5 votes on a 1-day-old paper is a smaller sample than 200 votes on a 40-day-old one
        P = {str(i): dict(tag='agents', age=10, cands=['30d'], upvotes=20 + i, up_rate=2.0 + i / 10, up_kind='measured',
                          mentions=None, ment_rate=None, repo=None) for i in range(20)}
        P['few'] = dict(tag='agents', age=1, cands=['30d'], upvotes=5, up_rate=5.0, up_kind='since-release', mentions=None, ment_rate=None, repo=None)
        P['many'] = dict(tag='agents', age=40, cands=['30d'], upvotes=200, up_rate=5.0, up_kind='measured', mentions=None, ment_rate=None, repo=None)
        out = {r['id']: r for r in scoring.score_run(features(self.R, P), CFG)['papers']['30d']}
        self.assertLess(out['few']['conf'], out['many']['conf'])
        self.assertLess(out['few']['score'], out['many']['score'])
        self.assertIn('few-votes', out['few']['flags'])

    def test_v1_legacy_runs(self):
        out = scoring.score_run(features(self.R), version='1.0')
        self.assertEqual(out['repos']['30d'][0]['score'], 100.0)      # v1 divides by the window max


class TestHype(unittest.TestCase):
    def P(self):
        P = {}
        for i in range(12):
            P[f'p{i}'] = dict(age=100, win={'30d': dict(mentions=i + 1, voices=i + 1, platforms=['HN', 'X'][: 1 + i % 2], days=30)},
                              real_in=dict(gh_trust=dict(v=10 * (i % 10), conf=0.9), paper=None,
                                           usage=dict(value=1000 * (i + 1), vendor=False), discussion=dict(v=i * 3)))
        P['thin'] = dict(age=100, win={'30d': dict(mentions=200, voices=150, platforms=['HN', 'X', 'Reddit', 'YouTube'], days=30)},
                         real_in=dict(gh_trust=None, paper=None, usage=None, discussion=dict(v=10 ** 6)))
        return P

    def test_low_confidence_real_is_not_extreme_and_gap_unlabelled(self):
        P = self.P()
        real, prior = scoring.real_scores(P, CFG)
        self.assertAlmostEqual(real['thin']['conf'], CFG['real']['weights']['discussion'])
        self.assertLessEqual(real['thin']['score'], prior + real['thin']['conf'] * (100 - prior) + 0.1)
        rows, _ = scoring.hype_window(P, '30d', real, CFG)
        r = next(x for x in rows if x['id'] == 'thin')
        self.assertEqual(r['label'], 'insufficient')
        self.assertLessEqual(r['conf'], 0.75 + 1e-9)                 # acceleration missing caps confidence

    def test_gap_label(self):
        self.assertEqual(scoring.gap_label(20, 0.7, 0.6, CFG), 'hype')
        self.assertEqual(scoring.gap_label(-20, 0.7, 0.6, CFG), 'sleeper')
        self.assertEqual(scoring.gap_label(3, 0.7, 0.6, CFG), 'earned')
        self.assertEqual(scoring.gap_label(40, 0.7, 0.2, CFG), 'insufficient')
        self.assertEqual(scoring.gap_label(None, 0.7, 0.7, CFG), 'insufficient')

    def test_single_platform_penalty(self):
        P = self.P()
        P['one'] = dict(age=100, win={'30d': dict(mentions=6, voices=6, platforms=['HN'], days=30)}, real_in={})
        P['two'] = dict(age=100, win={'30d': dict(mentions=6, voices=6, platforms=['HN', 'X'], days=30)}, real_in={})
        real, _ = scoring.real_scores(P, CFG)
        rows = {r['id']: r for r in scoring.hype_window(P, '30d', real, CFG)[0]}
        self.assertLess(rows['one']['score'], rows['two']['score'])
        self.assertIn('single-platform', rows['one']['flags'])


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
        F = json.load(open(fa))
        for v in ('1.0', scoring.SCORING_VERSION):
            out = scoring.score_run(F, CFG, v)
            for tab in ('papers', 'repos'):
                for rows in out[tab].values():
                    for r in rows:
                        self.assertTrue(r['score'] is None or 0 <= r['score'] <= 100)


if __name__ == '__main__':
    unittest.main()
