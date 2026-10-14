"""Pure projections of accepted inputs. Text is evidence data, never executable."""
from .contracts import instant, record_digest, require, validate_bundle

PROJECTION_METHOD = "investigation-read-model/1.0.0"


def project(bundle, scene_id, *, projection_method=PROJECTION_METHOD):
    require(projection_method == PROJECTION_METHOD, "unsupported projection method")
    validate_bundle(bundle)
    scene = next((s for s in bundle["scenes"] if s["id"] == scene_id), None)
    require(scene is not None, "Scene unavailable")
    publication = next((p for p in bundle["publication_revisions"] if p["id"] == scene["publication_revision_id"]), None)
    manifests = [m for m in bundle["replay_manifests"] if m["evidence_cutoff"] == scene["evidence_cutoff"]
                 and m["method_version"] == scene["method_version"]
                 and (publication is None or m["id"] == publication["replay_manifest_id"])]
    require(len(manifests) == 1, "ambiguous or unavailable Scene input manifest")
    manifest = manifests[0]
    selected = {(e["collection"], e["id"]) for e in manifest["input_records"]}
    index = {c: {r["id"]: r for r in bundle[c] if (c, r["id"]) in selected}
             for c in ("entities", "source_revisions", "evidence_spans", "observations", "claims", "evidence_links", "economic_relationships")}
    entities = set(scene["entity_ids"])
    require({("entities", i) for i in entities} <= selected, "Scene entity outside manifest")
    inspector = []
    for span in sorted(index["evidence_spans"].values(), key=lambda r: r["id"]):
        source = index["source_revisions"][span["source_revision_id"]]
        inspector.append({"id": span["id"], "span": span, "source_revision": source,
                          "untrusted_data": True})
    relationships = sorted((r for r in index["economic_relationships"].values()
                            if r["from_entity_id"] in entities or r["to_entity_id"] in entities), key=lambda r: r["id"])
    claims = sorted((r for r in index["claims"].values() if entities.intersection(r["entity_ids"])), key=lambda r: r["id"])
    observations = sorted((r for r in index["observations"].values() if r["entity_id"] in entities), key=lambda r: r["id"])
    edges = [{"id": "evidence-edge:" + record_digest([c["id"], span]), "claim_id": c["id"],
              "evidence_span_id": span, "kind": "reported_claim_evidence", "money_proof": False}
             for c in claims for span in c["evidence_span_ids"]]
    observation_edges = [{"id": "observation-edge:" + record_digest([o["id"], span]), "observation_id": o["id"],
                          "evidence_span_id": span, "kind": "observed_artifact_evidence", "money_proof": False}
                         for o in observations for span in o["evidence_span_ids"]]
    timeline = []
    for collection, rows in (("claims", claims), ("observations", observations), ("economic_relationships", relationships)):
        for record in rows:
            sources = [index["source_revisions"][index["evidence_spans"][s]["source_revision_id"]]
                       for s in record["evidence_span_ids"]]
            timeline.append({"id": record["id"], "collection": collection, "event_validity": record["event_validity"],
                "ingested_at": record["ingested_at"], "observed_at": record.get("observed_at"),
                "source_clocks": [{"source_revision_id": s["id"], "source_published_at": s["source_published_at"],
                                   "observed_at": s["observed_at"], "ingested_at": s["ingested_at"]} for s in sources]})
    timeline.sort(key=lambda r: (r["event_validity"]["start"] is None,
                                 instant(r["event_validity"]["start"], "event") if r["event_validity"]["start"] else (), r["id"]))
    assessments = sorted((a for a in bundle["assessments"] if a["id"] in scene["assessment_ids"]), key=lambda a: a["id"])
    return {"projection_method": projection_method, "scene": scene, "input_manifest": manifest,
            "relationships": relationships, "claim_evidence_edges": edges,
            "observation_evidence_edges": observation_edges,
            "evidence_links": sorted(index["evidence_links"].values(), key=lambda r: r["id"]),
            "observations": observations, "timeline": timeline, "inspector": inspector,
            "interpretations": assessments, "computed_at": manifest["computed_at"]}


def inspect_edge(view, edge_id):
    edge = next((e for e in view["claim_evidence_edges"] + view["observation_evidence_edges"] if e["id"] == edge_id), None)
    if edge is not None:
        spans = [edge["evidence_span_id"]]
    else:
        edge = next((e for e in view["relationships"] if e["id"] == edge_id), None)
        require(edge is not None, "edge outside accepted Scene")
        spans = edge["evidence_span_ids"]
    rows = {r["id"]: r for r in view["inspector"]}
    result = []
    for ident in spans:
        require(ident in rows, "edge evidence unavailable")
        row = rows[ident]
        span, source = row["span"], row["source_revision"]
        import hashlib
        require(span["id"] == ident and span["source_revision_id"] == source["id"], "span source identity mismatch")
        selector = span["selector"]
        require(selector["kind"] == "utf8_text" and type(selector["start"]) is int and type(selector["end"]) is int
                and 0 <= selector["start"] < selector["end"], "invalid evidence selector")
        require(source["content_text"] is not None, "source content unavailable")
        raw = source["content_text"].encode()
        require(selector["end"] <= len(raw), "evidence selector exceeds source")
        require(hashlib.sha256(raw).hexdigest() == source["content_sha256"], "source content hash mismatch")
        require(raw[span["selector"]["start"]:span["selector"]["end"]].decode() == span["quote"], "stale span quote")
        result.append(row)
    return result
