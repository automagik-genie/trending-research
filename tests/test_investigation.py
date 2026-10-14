"""Consumer-visible snapshot identity, unknown clocks and revision selection guards."""
import copy
from pathlib import Path
import unittest

from observatory.evidence.contracts import load_bundle, record_digest
from observatory.evidence.model import inspect_edge, project
from observatory.python_adapter import extract_snapshot, project_snapshot, METHOD


class TestInvestigation(unittest.TestCase):
    def test_snapshot_identity_unknown_clocks_and_changed_capture(self):
        snapshot = {"scoring_version": "2.0", "asof": "2020-02-01T00:00:00Z",
                    "repos": {"repo/a": {"stars": 7, "contributors": None}}, "papers": {}}
        clocks = {"ingested_at": "2020-02-03T00:00:00Z", "computed_at": "2020-02-03T00:00:01Z"}
        first = extract_snapshot(snapshot, **clocks)
        repeated = extract_snapshot(copy.deepcopy(snapshot), **clocks)
        self.assertEqual(record_digest(first), record_digest(repeated))
        rows = {o["metric"]: o for o in first["observations"]}
        self.assertEqual(rows["pipeline.v2.repos.stars"]["value"], 7)
        self.assertIsNone(rows["pipeline.v2.repos.contributors"]["value"])
        self.assertIsNone(first["source_revisions"][0]["observed_at"])
        self.assertIsNone(first["source_revisions"][0]["source_published_at"])
        self.assertEqual(rows["pipeline.v2.repos.stars"]["event_validity"], {"start": None, "end": None})
        changed = copy.deepcopy(snapshot)
        changed["repos"]["repo/a"]["stars"] = 8
        later = extract_snapshot(changed, **clocks)
        self.assertNotEqual(first["source_revisions"][0]["id"], later["source_revisions"][0]["id"])
        self.assertEqual(first["entities"], later["entities"])
        self.assertEqual(first["observations"][1]["value"], 7)
        with self.assertRaisesRegex(ValueError, "unsupported snapshot extraction method"):
            project_snapshot(snapshot, evidence_cutoff=clocks["ingested_at"], method_version="unqualified")

    def test_old_manifest_edge_never_redirects_to_later_correction(self):
        bundle = load_bundle(Path(__file__).parent / "fixtures/evidence_contracts.json")
        scene = bundle["scenes"][0]
        original = project(bundle, scene["id"])
        edge = next(e for e in original["claim_evidence_edges"] if e["claim_id"] == "claim:sustainable:1")
        evidence = inspect_edge(original, edge["id"])[0]
        self.assertEqual(evidence["span"]["source_revision_id"], "source:a:1")
        self.assertNotEqual(evidence["source_revision"]["id"], "source:a:2")
        self.assertEqual(project(copy.deepcopy(bundle), scene["id"]), original)
        tampered = copy.deepcopy(original)
        row = next(r for r in tampered["inspector"] if r["id"] == evidence["id"])
        row["span"]["quote"] = "later revision masquerading as old evidence"
        with self.assertRaisesRegex(ValueError, "stale span quote"):
            inspect_edge(tampered, edge["id"])
        with self.assertRaisesRegex(ValueError, "edge outside accepted Scene"):
            inspect_edge(original, "document-graph:unqualified-money-link")
        parties = [(r["transaction_id"], r["from_entity_id"]) for r in original["relationships"] if r["kind"] == "equity"]
        self.assertEqual(parties, [("transaction:one", "entity:investor-a"),
                                 ("transaction:two", "entity:investor-a"),
                                 ("transaction:one", "entity:investor-b")])
