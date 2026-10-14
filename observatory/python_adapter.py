"""Numeric-only snapshot extraction. Never imports collection or rescoring code."""
from collections.abc import Mapping
import hashlib
import math

from observatory.evidence.brain import canonical
from observatory.evidence.contracts import FIELDS, EVIDENCE_COLLECTIONS, instant, record_digest, require, validate_bundle

METHOD = "python-snapshot/numeric/1.0.0"
# Names/units are retained artifact outputs, not inferred empirical/financial meaning.
UNITS = {"days": "source-reported age-days", "age": "source-reported age-days", "gspan": "source-reported span-days",
         "score": "historical pipeline score", "raw": "historical pipeline raw-score", "rank": "historical cohort rank",
         "prev": "historical prior cohort rank", "coverage": "historical coverage indicator",
         "historical_merge_event_ratio": "historical event ratio", "merge_rate": "legacy ratio",
         "up_rate": "source-reported rate", "ment_rate": "source-reported rate", "repo_star_rate": "source-reported rate"}


def numeric_fields(row):
    return {k: v for k, v in sorted(row.items()) if v is None or type(v) in (int, float)}


def snapshot_identity(snapshot):
    require(isinstance(snapshot, Mapping), "snapshot mapping required")
    require(snapshot.get("scoring_version") == "2.0", "unsupported upstream snapshot method")
    return record_digest(snapshot)


def entity_id(kind, key):
    return "entity:research:" + kind + ":" + hashlib.sha256(key.encode()).hexdigest()


def project_snapshot(feature_snapshot: Mapping, *, evidence_cutoff: str, method_version: str) -> dict:
    require(method_version == METHOD, "unsupported snapshot extraction method")
    instant(evidence_cutoff, "snapshot cutoff")
    digest = snapshot_identity(feature_snapshot)
    entities = []
    for kind in ("repos", "papers"):
        section = feature_snapshot[kind]
        items = section["items"] if "items" in section else section
        entities.extend(entity_id(kind, key) for key in sorted(items))
    require(bool(entities), "empty snapshot unavailable")
    return {"id": "scene:snapshot:" + digest, "publication_revision_id": None,
            "assessment_ids": ["assessment:snapshot:" + digest], "entity_ids": entities,
            "evidence_cutoff": evidence_cutoff, "method_version": method_version}


def extract_snapshot(snapshot: Mapping, *, ingested_at: str, computed_at: str, observed_at=None) -> dict:
    """Caller supplies real accepted clocks once; absent collection time remains unknown."""
    instant(ingested_at, "snapshot ingestion")
    require(instant(computed_at, "snapshot computation") >= instant(ingested_at, "snapshot cutoff"), "computation before ingestion")
    if observed_at is not None:
        require(instant(observed_at, "snapshot observation") <= instant(ingested_at, "snapshot ingestion"), "observation after ingestion")
    digest = snapshot_identity(snapshot)
    bundle = {"contract_version": "1.0.0", "fixture_notice": None, **{c: [] for c in FIELDS}}
    archive = snapshot.get("artifact_kind") == "historical_v2_archive"
    require(archive or "asof" in snapshot, "unsupported snapshot shape")
    unknown = {"start": None, "end": None}
    for kind in ("repos", "papers"):
        section = snapshot[kind]
        items = section["items"] if archive else section
        extra = {key: {} for key in items}
        if archive:
            for window in snapshot["windows"]:
                for cohort in snapshot["views"]:
                    for row in section[window][cohort]["rows"]:
                        require(row["id"] in extra, "window entity missing from retained snapshot items")
                        require(window + ":" + cohort not in extra[row["id"]], "duplicate snapshot cohort row")
                        extra[row["id"]][window + ":" + cohort] = numeric_fields(row)
        for key, item in sorted(items.items()):
            ident = entity_id(kind, key)
            bundle["entities"].append({"id": ident, "kind": "project" if kind == "repos" else "product", "name": key, "aliases": []})
            # Never retain scraped prose, titles/authors, executable source instructions or inferred clocks.
            extraction = {"item": numeric_fields(item), "windows": extra[key]}
            raw = canonical(extraction)
            source_id = "source:snapshot:" + digest + ":" + hashlib.sha256((kind + ":" + key).encode()).hexdigest()
            span_id = "span:" + source_id
            provenance = {"snapshot_sha256": digest, "extraction_method": METHOD, "upstream_method": "2.0",
                "artifact_kind": snapshot.get("artifact_kind", "retained-feature-snapshot"),
                "upstream_computed_at": snapshot.get("generated_at"), "upstream_reference_asof": snapshot.get("asof"),
                "declared_tracked": snapshot.get("tracked"), "collection_time": observed_at,
                "disposition": "numeric/null extraction only; all retained item entities and all archive cohorts; historical outputs not rescored"}
            bundle["source_revisions"].append({"id": source_id, "source_id": source_id, "revision_of": None,
                "change_kind": "original", "uri": None, "content_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "content_text": raw, "media_type": "text/plain; charset=utf-8", "source_published_at": None,
                "observed_at": observed_at, "ingested_at": ingested_at, "origin_id": "origin:python-pipeline",
                "retention_status": "retained", "reason": canonical(provenance)})
            bundle["evidence_spans"].append({"id": span_id, "source_revision_id": source_id,
                "selector": {"kind": "utf8_text", "start": 0, "end": len(raw.encode())}, "quote": raw})
            groups = [("item", extraction["item"])]
            groups.extend((scope, values) for scope, values in extraction["windows"].items() if scope.endswith(":all"))
            for scope, values in groups:
                for metric, value in values.items():
                    require(value is None or math.isfinite(value), "nonfinite snapshot scalar")
                    # Null nonnumeric metadata is excluded from observations, but remains in extraction.
                    if metric in {"paper", "paper_title", "lab", "code", "flags", "verification", "ment_kind", "up_kind", "repo"}:
                        continue
                    observation_id = "observation:snapshot:" + record_digest([source_id, scope, metric])
                    bundle["observations"].append({"id": observation_id, "entity_id": ident,
                        "metric": "pipeline.v2." + kind + "." + metric, "value": value,
                        "unit": UNITS.get(metric, "source-reported count/indicator"),
                        "scope": "retained snapshot " + kind + "; " + scope + "; upstream method 2.0; unknown measurement boundaries",
                        "period": dict(unknown), "event_validity": dict(unknown), "observed_at": observed_at,
                        "ingested_at": ingested_at, "evidence_span_ids": [span_id], "revision_of": None})
    claim_id = "claim:snapshot-inventory:" + digest
    bundle["claims"].append({"id": claim_id, "entity_ids": [bundle["entities"][0]["id"]],
        "proposition": "Technical extraction inventory only: retained numeric/null snapshot outputs, not verified empirical or financial conclusions.",
        "asserted_by_entity_id": None, "evidence_span_ids": [bundle["evidence_spans"][0]["id"]],
        "event_validity": dict(unknown), "ingested_at": ingested_at, "revision_of": None, "status": "asserted"})
    bundle["assessments"].append({"id": "assessment:snapshot:" + digest, "claim_ids": [claim_id],
        "conclusion": "Unverified technical inventory; extraction is separate from analyst interpretation and historical scoring.",
        "confidence": {"coverage": {"numerator": None, "denominator": None, "scope": "retained snapshot only; population denominator unknown"},
            "verification": "unverified", "freshness": {"assessed_at": computed_at, "newest_evidence_at": None},
            "independence": {"origin_ids": ["origin:python-pipeline"], "rationale": "One pipeline artifact, not independent upstream sources"}},
        "evidence_cutoff": ingested_at, "method_version": METHOD, "computed_at": computed_at,
        "attributed_to_entity_id": None, "revision_of": None})
    bundle["replay_manifests"].append({"id": "manifest:snapshot:" + digest, "evidence_cutoff": ingested_at,
        "method_version": METHOD, "computed_at": computed_at, "history_mode": "known_at_cutoff",
        "input_records": [{"collection": c, "id": r["id"], "sha256": record_digest(r)}
                          for c in FIELDS if c in EVIDENCE_COLLECTIONS for r in bundle[c]]})
    bundle["scenes"].append(project_snapshot(snapshot, evidence_cutoff=ingested_at, method_version=METHOD))
    validate_bundle(bundle)
    return bundle
