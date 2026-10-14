"""Accepted v1 invariant verifier; not a general JSON Schema engine."""
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re

FIELDS = {
    "entities": "id kind name aliases",
    "source_revisions": "id source_id revision_of change_kind uri content_sha256 content_text media_type source_published_at observed_at ingested_at origin_id retention_status reason",
    "evidence_spans": "id source_revision_id selector quote",
    "observations": "id entity_id metric value unit scope period event_validity observed_at ingested_at evidence_span_ids revision_of",
    "claims": "id entity_ids proposition asserted_by_entity_id evidence_span_ids event_validity ingested_at revision_of status",
    "evidence_links": "id from_claim_id to_claim_id relation evidence_span_ids attributed_to_entity_id ingested_at",
    "economic_relationships": "id transaction_id kind from_entity_id to_entity_id amount currency period reporting_party_entity_id status evidence_span_ids event_validity ingested_at revision_of",
    "assessments": "id claim_ids conclusion confidence evidence_cutoff method_version computed_at attributed_to_entity_id revision_of",
    "publication_revisions": "id publication_id revision_of assessment_ids replay_manifest_id status editorial_actor_entity_id approved_at published_at",
    "replay_manifests": "id evidence_cutoff method_version input_records computed_at history_mode",
    "scenes": "id publication_revision_id assessment_ids entity_ids evidence_cutoff method_version",
}
EVIDENCE_COLLECTIONS = set(FIELDS) - {"assessments", "publication_revisions", "replay_manifests", "scenes"}
INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", re.ASCII)
DIGEST = re.compile(r"[a-f0-9]{64}", re.ASCII)
NULLABLE = set("revision_of uri content_sha256 content_text media_type source_published_at observed_at reason value amount currency asserted_by_entity_id attributed_to_entity_id reporting_party_entity_id editorial_actor_entity_id approved_at published_at publication_revision_id".split())
LIST_FIELDS = set("entity_ids evidence_span_ids claim_ids assessment_ids".split())
TEXT_FIELDS = set("id source_id origin_id source_revision_id entity_id metric unit scope proposition from_claim_id to_claim_id transaction_id from_entity_id to_entity_id conclusion method_version publication_id replay_manifest_id name".split())
TIME_FIELDS = set("source_published_at observed_at ingested_at evidence_cutoff computed_at approved_at published_at".split())
REF_FIELDS = {
    "entity_id": "entities", "entity_ids": "entities", "asserted_by_entity_id": "entities",
    "attributed_to_entity_id": "entities", "reporting_party_entity_id": "entities", "editorial_actor_entity_id": "entities",
    "from_entity_id": "entities", "to_entity_id": "entities", "source_revision_id": "source_revisions",
    "evidence_span_ids": "evidence_spans", "from_claim_id": "claims", "to_claim_id": "claims",
    "claim_ids": "claims", "assessment_ids": "assessments", "replay_manifest_id": "replay_manifests",
    "publication_revision_id": "publication_revisions",
}
ENUMS = {
    ("entities", "kind"): {"organization", "person", "product", "project"},
    ("source_revisions", "change_kind"): {"original", "revision", "correction", "deletion"},
    ("source_revisions", "retention_status"): {"retained", "redacted", "unavailable"},
    ("claims", "status"): {"asserted", "retracted"},
    ("evidence_links", "relation"): {"supports", "contradicts"},
    ("economic_relationships", "kind"): {"equity", "debt", "cloud_credit", "commitment", "recognized_revenue"},
    ("economic_relationships", "status"): {"announced", "committed", "completed", "recognized", "cancelled", "unknown"},
    ("publication_revisions", "status"): {"draft", "published", "corrected", "retracted"},
    ("replay_manifests", "history_mode"): {"known_at_cutoff"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def shape(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields.split()), f"{label}: required/unknown fields")


def text(value, label):
    require(isinstance(value, str) and bool(value), f"{label}: nonempty text required")


def instant(value, label):
    require(isinstance(value, str) and INSTANT.fullmatch(value) is not None, f"{label}: UTC instant required")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid calendar instant") from exc
    # Preserve arbitrary fractional precision; datetime alone truncates after microseconds.
    fraction = Decimal("0." + value.split(".")[1][:-1]) if "." in value else Decimal(0)
    return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second, fraction)


def interval(value, label):
    shape(value, "start end", label)
    points = [instant(v, label) if v is not None else None for v in (value["start"], value["end"])]
    if all(v is not None for v in points):
        require(points[0] < points[1], f"{label}: empty/reversed interval")


def id_list(value, label, nonempty=True):
    require(isinstance(value, list), f"{label}: list required")
    for item in value:
        text(item, label)
    require(len(value) == len(set(value)), f"{label}: duplicate references")
    require(bool(value) or not nonempty, f"{label}: references required")


def record_digest(record):
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_bundle(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f"nonfinite JSON number: {value}")
    with Path(path).open(encoding="utf-8") as source:
        return json.load(source, object_pairs_hook=unique_object, parse_constant=reject_constant)


def references(collection, record):
    result = []
    for field, target in REF_FIELDS.items():
        if field in record and record[field] is not None:
            values = record[field] if isinstance(record[field], list) else [record[field]]
            result.extend((target, value) for value in values)
    if record.get("revision_of") is not None:
        result.append((collection, record["revision_of"]))
    if collection == "entities":
        result.extend(("source_revisions", alias["source_revision_id"]) for alias in record["aliases"] if alias["source_revision_id"] is not None)
    return result


def validate_bundle(bundle):
    """Validate the frozen v1 domain invariants; deliberately not generic Schema validation."""
    shape(bundle, "contract_version fixture_notice " + " ".join(FIELDS), "bundle")
    require(bundle["contract_version"] == "1.0.0", "unsupported contract version")
    require(bundle["fixture_notice"] is None or isinstance(bundle["fixture_notice"], str), "fixture notice must be text/null")
    index = {}
    identities = set()
    for collection, fields in FIELDS.items():
        require(isinstance(bundle[collection], list), f"{collection}: array required")
        index[collection] = {}
        for record in bundle[collection]:
            shape(record, fields, collection)
            text(record["id"], collection)
            require(record["id"] not in identities, f"duplicate record identity: {record['id']}")
            identities.add(record["id"])
            index[collection][record["id"]] = record
            for field, value in record.items():
                label = f"{record['id']}.{field}"
                if value is None:
                    require(field in NULLABLE, f"{label}: null is not permitted")
                    continue
                if field in TIME_FIELDS:
                    instant(value, label)
                elif field in TEXT_FIELDS or field in NULLABLE - {"value", "amount", "currency", "content_text"}:
                    text(value, label)
                elif field in LIST_FIELDS:
                    id_list(value, label)
                elif field in {"value", "amount"}:
                    require(type(value) in (int, float) and math.isfinite(value), f"{label}: finite number/null required")
                elif field in {"period", "event_validity"}:
                    interval(value, label)
                elif field == "currency":
                    require(isinstance(value, str) and re.fullmatch(r"[A-Z]{3}", value), f"{label}: currency code/null required")
                elif field == "content_text":
                    require(isinstance(value, str), f"{label}: text/null required")
                if (collection, field) in ENUMS:
                    require(isinstance(value, str) and value in ENUMS[collection, field], f"{label}: invalid enum")
            if "observed_at" in record and record["observed_at"] is not None:
                require(instant(record["observed_at"], "observation") <= instant(record["ingested_at"], "ingestion"), "observation after ingestion")
            if collection == "entities":
                require(isinstance(record["aliases"], list), "aliases: array required")
                alias_keys = set()
                for alias in record["aliases"]:
                    shape(alias, "value scheme source_revision_id", "alias")
                    text(alias["value"], "alias value")
                    text(alias["scheme"], "alias scheme")
                    if alias["source_revision_id"] is not None:
                        text(alias["source_revision_id"], "alias provenance")
                    key = (alias["scheme"], alias["value"], alias["source_revision_id"])
                    require(key not in alias_keys, "duplicate alias")
                    alias_keys.add(key)

    for collection, records in index.items():
        for record in records.values():
            for target, id_ in references(collection, record):
                require(id_ in index[target], f"dangling reference: {record['id']} -> {target}/{id_}")
            if record.get("revision_of") is not None:
                prior = records[record["revision_of"]]
                require(prior["id"] != record["id"], "self revision")
                if "ingested_at" in record:
                    require(instant(prior["ingested_at"], "prior ingestion") <= instant(record["ingested_at"], "revision ingestion"), "revision precedes prior ingestion")
                stable = {
                    "source_revisions": ("source_id", "origin_id"),
                    "observations": ("entity_id", "metric", "unit", "scope"),
                    "claims": ("entity_ids", "asserted_by_entity_id"),
                    "economic_relationships": ("transaction_id", "kind", "from_entity_id", "to_entity_id"),
                    "publication_revisions": ("publication_id",),
                }.get(collection, ())
                require(all(record[key] == prior[key] for key in stable), f"{collection}: revision changes logical identity")
            seen = set()
            cursor = record
            while cursor.get("revision_of") is not None:
                require(cursor["id"] not in seen, "cyclic revision chain")
                seen.add(cursor["id"])
                cursor = records[cursor["revision_of"]]

    for collection, records in index.items():
        for record in records.values():
            if "ingested_at" not in record:
                continue
            for target, id_ in references(collection, record):
                dependency = index[target][id_]
                if target == "evidence_spans":
                    dependency = index["source_revisions"][dependency["source_revision_id"]]
                if "ingested_at" in dependency:
                    require(instant(dependency["ingested_at"], "dependency") <= instant(record["ingested_at"], "record"), "provenance known after record ingestion")

    for source in bundle["source_revisions"]:
        kind, prior = source["change_kind"], source["revision_of"]
        require((kind == "original") == (prior is None), "source revision requires prior record")
        if kind != "original" or source["retention_status"] != "retained":
            text(source["reason"], "revision/retention reason")
        if source["content_sha256"] is not None:
            require(DIGEST.fullmatch(source["content_sha256"]) is not None, "invalid content digest")
        if source["content_text"] is not None:
            require(source["retention_status"] == "retained", "unretained source cannot expose content")
            require(source["media_type"] == "text/plain; charset=utf-8", "unsupported text representation")
            require(hashlib.sha256(source["content_text"].encode("utf-8")).hexdigest() == source["content_sha256"], "source content hash mismatch")
        elif source["retention_status"] == "retained":
            require(source["content_sha256"] is not None, "retained external content requires hash")
        if kind == "deletion":
            require(source["content_text"] is None and source["retention_status"] != "retained", "deletion must be a tombstone")

    for span in bundle["evidence_spans"]:
        selector = span["selector"]
        shape(selector, "kind start end", "span selector")
        start, end = selector["start"], selector["end"]
        require(selector["kind"] == "utf8_text" and type(start) is int and type(end) is int and 0 <= start < end, "invalid byte span")
        source = index["source_revisions"][span["source_revision_id"]]
        require(source["content_text"] is not None, "span content unavailable; exact replay cannot be certified")
        raw = source["content_text"].encode("utf-8")
        require(end <= len(raw), "span exceeds source bytes")
        try:
            quote = raw[start:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("span splits UTF-8 character") from exc
        text(span["quote"], "span quote")
        require(quote == span["quote"], "span quote mismatch")

    for record in bundle["claims"]:
        require(record["status"] != "retracted" or record["revision_of"] is not None, "retraction must preserve prior claim")
    for link in bundle["evidence_links"]:
        require(link["from_claim_id"] != link["to_claim_id"], "self evidence link")
        claims = [index["claims"][link[key]] for key in ("from_claim_id", "to_claim_id")]
        require(set(claims[0]["entity_ids"]) & set(claims[1]["entity_ids"]), "evidence link has no shared subject")
    for relationship in bundle["economic_relationships"]:
        require(relationship["amount"] is None or relationship["currency"] is not None, "known amount requires currency")
        require(relationship["status"] != "recognized" or relationship["kind"] == "recognized_revenue", "recognized status requires revenue type")
        if relationship["kind"] == "recognized_revenue":
            require(relationship["status"] in {"recognized", "unknown", "cancelled"}, "revenue cannot encode an unrecognized commitment")
            if relationship["status"] == "recognized":
                require(all(relationship["period"].values()) and relationship["reporting_party_entity_id"] is not None, "recognized revenue requires period and reporting party")

    def available_at(collection, record):
        if collection == "entities":
            return None  # Entity identity has no knowledge clock; only explicit manifest membership applies.
        if collection == "evidence_spans":
            record = index["source_revisions"][record["source_revision_id"]]
        return instant(record["ingested_at"], "evidence ingestion")

    manifest_members = {}
    for manifest in bundle["replay_manifests"]:
        cutoff = instant(manifest["evidence_cutoff"], "cutoff")
        require(cutoff <= instant(manifest["computed_at"], "computation"), "computation before cutoff")
        require(isinstance(manifest["input_records"], list) and manifest["input_records"], "replay inputs required")
        members = set()
        for entry in manifest["input_records"]:
            shape(entry, "collection id sha256", "manifest input")
            require(isinstance(entry["collection"], str) and entry["collection"] in EVIDENCE_COLLECTIONS, "invalid input collection")
            text(entry["id"], "input identity")
            key = (entry["collection"], entry["id"])
            require(key not in members, "duplicate replay input")
            members.add(key)
            require(entry["id"] in index[entry["collection"]], "missing replay input")
            record = index[entry["collection"]][entry["id"]]
            require(entry["sha256"] == record_digest(record), "replay input hash mismatch")
            when = available_at(entry["collection"], record)
            require(when is None or when <= cutoff, "post-cutoff evidence admitted")
        for collection, id_ in members:
            require(set(references(collection, index[collection][id_])) <= members, "replay dependency omitted")
        manifest_members[manifest["id"]] = members

    for assessment in bundle["assessments"]:
        cutoff = instant(assessment["evidence_cutoff"], "assessment cutoff")
        computed = instant(assessment["computed_at"], "assessment computation")
        require(cutoff <= computed, "assessment computation before cutoff")
        # A bound claim brings its complete provenance and revision ancestors, not just a claim timestamp.
        pending = [("claims", id_) for id_ in assessment["claim_ids"]]
        visited = set()
        origins = set()
        while pending:
            key = pending.pop()
            if key in visited:
                continue
            visited.add(key)
            record = index[key[0]][key[1]]
            when = available_at(key[0], record)
            require(when is None or when <= cutoff, "assessment contains post-cutoff evidence")
            if key[0] == "source_revisions":
                origins.add(record["origin_id"])
            pending.extend(references(key[0], record))
        confidence = assessment["confidence"]
        shape(confidence, "coverage verification freshness independence", "confidence")
        coverage = confidence["coverage"]
        shape(coverage, "numerator denominator scope", "coverage")
        text(coverage["scope"], "coverage scope")
        n, d = coverage["numerator"], coverage["denominator"]
        require((n is None) == (d is None), "partial coverage denominator")
        require(n is None or (type(n) is int and type(d) is int and 0 <= n <= d and d > 0), "invalid coverage cohort ratio")
        require(isinstance(confidence["verification"], str) and confidence["verification"] in {"unverified", "source_checked", "independently_replicated", "disputed"}, "invalid verification dimension")
        fresh = confidence["freshness"]
        shape(fresh, "assessed_at newest_evidence_at", "freshness")
        for key in fresh:
            if fresh[key] is not None:
                require(instant(fresh[key], key) <= computed, "freshness after computation")
        if fresh["newest_evidence_at"] is not None:
            require(instant(fresh["newest_evidence_at"], "freshness evidence") <= cutoff, "freshness evidence after cutoff")
        if all(fresh.values()):
            require(instant(fresh["newest_evidence_at"], "freshness evidence") <= instant(fresh["assessed_at"], "freshness assessment"), "freshness evidence after assessment")
        independence = confidence["independence"]
        shape(independence, "origin_ids rationale", "independence")
        id_list(independence["origin_ids"], "origin groups", nonempty=False)
        require(set(independence["origin_ids"]) <= origins, "independence invents origins")
        require(independence["rationale"] is None or isinstance(independence["rationale"], str), "independence rationale must be text/null")

    for publication in bundle["publication_revisions"]:
        manifest = index["replay_manifests"][publication["replay_manifest_id"]]
        for id_ in publication["assessment_ids"]:
            assessment = index["assessments"][id_]
            require(all(assessment[key] == manifest[key] for key in ("evidence_cutoff", "method_version", "computed_at")), "publication replay identity mismatch")
            require({("claims", claim) for claim in assessment["claim_ids"]} <= manifest_members[manifest["id"]], "published assessment absent from replay")
        approved = publication["approved_at"]
        published = publication["published_at"]
        actor = publication["editorial_actor_entity_id"]
        if publication["status"] == "draft":
            require(approved is None and published is None, "draft cannot claim publication approval")
        else:
            require(actor is not None and approved is not None and published is not None, "publication requires attributed approval")
            require(instant(manifest["computed_at"], "manifest") <= instant(approved, "approval") <= instant(published, "publication"), "publication approval chronology")
        if publication["status"] in {"corrected", "retracted"}:
            require(publication["revision_of"] is not None, "publication correction/retraction requires prior revision")
        if publication["revision_of"] is not None and published is not None:
            prior = index["publication_revisions"][publication["revision_of"]]
            if prior["published_at"] is not None:
                require(instant(prior["published_at"], "prior publication") <= instant(published, "publication"), "publication revision chronology")

    for scene in bundle["scenes"]:
        for id_ in scene["assessment_ids"]:
            require(all(scene[key] == index["assessments"][id_][key] for key in ("evidence_cutoff", "method_version")), "scene assessment identity mismatch")
        if scene["publication_revision_id"] is not None:
            publication = index["publication_revisions"][scene["publication_revision_id"]]
            require(set(scene["assessment_ids"]) <= set(publication["assessment_ids"]), "scene escapes publication assessments")
            members = manifest_members[publication["replay_manifest_id"]]
            require({("entities", id_) for id_ in scene["entity_ids"]} <= members, "scene entity absent from replay")
