"""Contract-specific stdlib checks, not a JSON Schema engine or storage runtime.

Run examples directly: python3 tests/test_evidence_contracts.py --smoke tests/fixtures/evidence_contracts.json
All fixture identities, statements and dates are synthetic; unknown amounts stay null.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from observatory.evidence.contracts import (
    instant, load_bundle, record_digest, require, validate_bundle,
)


FIXTURE = Path(__file__).parent / "fixtures" / "evidence_contracts.json"


def example_observations(bundle):
    """Exercise the named example, independently of generic bundle invariants."""
    validate_bundle(bundle)
    claims = {row["id"]: row for row in bundle["claims"]}
    opposed = ["claim:sustainable:1", "claim:unsustainable:1"]
    require(all(id_ in claims and claims[id_]["revision_of"] is None for id_ in opposed), "example lost independent contradictory claims")
    require([claims[id_]["proposition"] for id_ in opposed] == ["Synthetic Builder economics are sustainable.", "Synthetic Builder economics are not sustainable."], "example no longer contradicts")
    require(any(row["relation"] == "contradicts" and {row["from_claim_id"], row["to_claim_id"]} == set(opposed) for row in bundle["evidence_links"]), "example contradiction link missing")
    equity = [row for row in bundle["economic_relationships"] if row["kind"] == "equity"]
    pairs = {(row["transaction_id"], row["from_entity_id"]) for row in equity}
    require(pairs == {("transaction:one", "entity:investor-a"), ("transaction:one", "entity:investor-b"), ("transaction:two", "entity:investor-a")}, "example lost concurrent investor or repeated transaction")
    require(all(row["revision_of"] is None for row in equity), "example transaction accidentally superseded")
    require({row["kind"] for row in bundle["economic_relationships"]} == {"equity", "debt", "cloud_credit", "commitment", "recognized_revenue"}, "example conflated economic types")
    sources = {row["id"]: row for row in bundle["source_revisions"]}
    require(sources["source:a:2"]["revision_of"] == "source:a:1" and sources["source:a:2"]["change_kind"] == "correction", "example revision chain missing")
    manifest = bundle["replay_manifests"][0]
    require(manifest["evidence_cutoff"] == "2020-02-03T00:00:00Z" and manifest["method_version"] == "fixture-method/1", "example replay identity drift")
    members = {row["id"] for row in manifest["input_records"]}
    require({"source:a:1", "claim:sustainable:1", "claim:unsustainable:1"} <= members and not {"source:a:2", "span:a:2", "claim:unresolved:2"} & members, "example cannot replay pre-correction history")
    return {"opposed_claims": opposed, "equity_transaction_parties": sorted(pairs), "source_revision_chain": ["source:a:1", "source:a:2"], "evidence_cutoff": manifest["evidence_cutoff"], "method_version": manifest["method_version"], "later_correction_excluded": True}


class TestEvidenceContracts(unittest.TestCase):
    def setUp(self):
        self.bundle = load_bundle(FIXTURE)

    def rejected(self, pattern):
        return self.assertRaisesRegex(ValueError, pattern)

    def test_opposed_claims_transactions_and_historical_replay(self):
        observed = example_observations(self.bundle)
        self.assertEqual(observed["source_revision_chain"], ["source:a:1", "source:a:2"])
        self.assertEqual(observed["equity_transaction_parties"], [("transaction:one", "entity:investor-a"), ("transaction:one", "entity:investor-b"), ("transaction:two", "entity:investor-a")])
        original = copy.deepcopy(self.bundle)
        # Later correction text changes cannot alter the pre-cutoff input identity.
        correction = self.bundle["source_revisions"][2]
        correction["content_text"] = "Different synthetic correction."
        correction["content_sha256"] = hashlib.sha256(correction["content_text"].encode()).hexdigest()
        span = self.bundle["evidence_spans"][2]
        span["quote"] = correction["content_text"]
        span["selector"]["end"] = len(span["quote"].encode())
        validate_bundle(self.bundle)
        self.assertEqual(self.bundle["replay_manifests"], original["replay_manifests"])

    def test_claim_cannot_cite_evidence_acquired_after_its_ingestion(self):
        self.bundle["claims"][0]["evidence_span_ids"] = ["span:a:2"]
        with self.rejected("provenance known after record ingestion"):
            validate_bundle(self.bundle)

    def test_duplicate_identity_cannot_overwrite_prior_claim(self):
        self.bundle["claims"][1]["id"] = "claim:sustainable:1"
        with self.rejected("duplicate record identity"):
            validate_bundle(self.bundle)

    def test_dangling_provenance_fails_closed(self):
        self.bundle["claims"][0]["evidence_span_ids"] = ["span:absent"]
        with self.rejected("dangling reference"):
            validate_bundle(self.bundle)

    def test_transaction_pair_is_not_a_revision_key(self):
        self.bundle["economic_relationships"][2]["revision_of"] = "relationship:equity:a:1"
        with self.rejected("revision changes logical identity"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        self.bundle["economic_relationships"][1]["revision_of"] = "relationship:equity:a:1"
        with self.rejected("revision changes logical identity"):
            validate_bundle(self.bundle)

    def test_source_correction_cannot_cross_source_or_cycle(self):
        self.bundle["source_revisions"][2]["source_id"] = "source:b"
        with self.rejected("revision changes logical identity"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        self.bundle["source_revisions"][0]["revision_of"] = "source:a:2"
        self.bundle["source_revisions"][0]["ingested_at"] = self.bundle["source_revisions"][2]["ingested_at"]
        with self.rejected("cyclic revision chain"):
            validate_bundle(self.bundle)

    def test_byte_spans_and_raw_content_hash_guard_evidence(self):
        self.bundle["source_revisions"][0]["content_text"] += "tampered"
        with self.rejected("source content hash mismatch"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        self.bundle["evidence_spans"][0]["quote"] = "invented"
        with self.rejected("span quote mismatch"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        source = self.bundle["source_revisions"][0]
        source["content_text"] = "évidence"
        source["content_sha256"] = hashlib.sha256(source["content_text"].encode()).hexdigest()
        self.bundle["evidence_spans"][0]["selector"] = {"kind": "utf8_text", "start": 1, "end": 2}
        with self.rejected("span splits UTF-8 character"):
            validate_bundle(self.bundle)

    def test_replay_rejects_future_evidence_and_missing_dependencies(self):
        correction = self.bundle["source_revisions"][2]
        self.bundle["replay_manifests"][0]["input_records"].append({"collection": "source_revisions", "id": correction["id"], "sha256": record_digest(correction)})
        with self.rejected("post-cutoff evidence admitted"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        inputs = self.bundle["replay_manifests"][0]["input_records"]
        inputs[:] = [row for row in inputs if row["id"] != "span:a:1"]
        with self.rejected("replay dependency omitted"):
            validate_bundle(self.bundle)

    def test_replay_hash_and_method_are_not_optional(self):
        self.bundle["replay_manifests"][0]["input_records"][0]["sha256"] = "0" * 64
        with self.rejected("replay input hash mismatch"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        self.bundle["replay_manifests"][0]["method_version"] = "other-method/2"
        with self.rejected("publication replay identity mismatch"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        del self.bundle["replay_manifests"][0]["evidence_cutoff"]
        with self.rejected("required/unknown fields"):
            validate_bundle(self.bundle)

    def test_coverage_is_a_cohort_not_a_probability(self):
        coverage = self.bundle["assessments"][0]["confidence"]["coverage"]
        for n, d in [(3, 2), (0.8, 1), (0, 0), (None, 2), (True, 2)]:
            with self.subTest(n=n, d=d):
                coverage.update(numerator=n, denominator=d)
                with self.rejected("coverage|denominator"):
                    validate_bundle(self.bundle)
        coverage.update(numerator=0, denominator=2)
        validate_bundle(self.bundle)

    def test_financial_classification_cannot_invent_currency_or_recognition(self):
        relationship = self.bundle["economic_relationships"][0]
        relationship["amount"] = 10
        with self.rejected("known amount requires currency"):
            validate_bundle(self.bundle)
        relationship["amount"] = None
        relationship["status"] = "recognized"
        with self.rejected("recognized status requires revenue type"):
            validate_bundle(self.bundle)
        relationship["status"] = "unknown"
        self.bundle["economic_relationships"][-1]["status"] = "recognized"
        with self.rejected("recognized revenue requires period and reporting party"):
            validate_bundle(self.bundle)

    def test_publication_cannot_fabricate_attributed_approval(self):
        self.bundle["publication_revisions"][0]["status"] = "published"
        with self.rejected("publication requires attributed approval"):
            validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        self.bundle["publication_revisions"][0]["approved_at"] = "2020-02-03T02:00:00Z"
        with self.rejected("draft cannot claim publication approval"):
            validate_bundle(self.bundle)

    def test_scene_cannot_silently_change_method_or_evidence_cutoff(self):
        for key, value in [("method_version", "other/2"), ("evidence_cutoff", "2020-02-05T00:00:00Z")]:
            with self.subTest(key=key):
                self.bundle = load_bundle(FIXTURE)
                self.bundle["scenes"][0][key] = value
                with self.rejected("scene assessment identity mismatch"):
                    validate_bundle(self.bundle)

    def test_utc_interval_and_fractional_precision_boundaries(self):
        self.assertLess(instant("2020-02-03T00:00:00.0000001Z", "a"), instant("2020-02-03T00:00:00.0000002Z", "b"))
        for bad in ["2020-02-30T00:00:00Z", "2020-02-03", "2020-02-03T00:00:00+01:00"]:
            with self.subTest(bad=bad), self.rejected("instant"):
                instant(bad, "time")
        self.bundle["observations"][0]["period"]["end"] = "2020-01-01T00:00:00Z"
        with self.rejected("empty/reversed interval"):
            validate_bundle(self.bundle)

    def test_backdated_source_publication_cannot_bypass_ingestion_cutoff(self):
        self.bundle["source_revisions"][2]["source_published_at"] = "2019-01-01T00:00:00Z"
        self.bundle["assessments"][0]["claim_ids"].append("claim:unresolved:2")
        with self.rejected("assessment contains post-cutoff evidence"):
            validate_bundle(self.bundle)

    def test_deletion_appends_tombstone_without_erasing_prior_spans(self):
        prior = self.bundle["source_revisions"][2]
        tombstone = dict(prior, id="source:a:3", revision_of=prior["id"], change_kind="deletion", content_text=None, content_sha256=None, media_type=None, source_published_at=None, observed_at=None, ingested_at="2020-02-06T00:00:00Z", retention_status="unavailable", reason="Synthetic source removal, no authority to retain new content")
        self.bundle["source_revisions"].append(tombstone)
        validate_bundle(self.bundle)
        observed = example_observations(self.bundle)
        self.assertEqual(observed["opposed_claims"], ["claim:sustainable:1", "claim:unsustainable:1"])
        self.bundle["evidence_spans"].append(dict(self.bundle["evidence_spans"][0], id="span:a:3", source_revision_id=tombstone["id"]))
        with self.rejected("span content unavailable"):
            validate_bundle(self.bundle)

    def test_numeric_unknowns_and_independence_do_not_become_guesses(self):
        for value in [True, float("nan"), float("inf"), "unknown"]:
            with self.subTest(value=value):
                self.bundle["observations"][0]["value"] = value
                with self.rejected("finite number/null"):
                    validate_bundle(self.bundle)
        self.bundle = load_bundle(FIXTURE)
        self.bundle["assessments"][0]["confidence"]["independence"]["origin_ids"].append("invented-origin")
        with self.rejected("independence invents origins"):
            validate_bundle(self.bundle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", type=Path)
    args, remaining = parser.parse_known_args()
    if args.smoke:
        require(not remaining, "unexpected smoke arguments")
        observations = example_observations(load_bundle(args.smoke))
        observations["fixture_sha256"] = hashlib.sha256(args.smoke.read_bytes()).hexdigest()
        print(json.dumps(observations, indent=2))
    else:
        unittest.main(argv=[__file__, *remaining])
