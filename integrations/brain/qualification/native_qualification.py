"""Qualify the installed native Brain in an explicitly admitted isolated lab.

No host Brain configuration, provider credentials, shared PostgreSQL or network
routes are supplied. Bootstrap does not call evidence tools. Admission of the
actual native authority and live schemas is a separate coordinator gate.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import queue
import secrets
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"
CONTAINER = "oi5-ctx-ed2a28fd3625"
IMAGE = "pgvector/pgvector@sha256:cf134a767f474095eeba57e0117be8e568e011a63f33fbf252f14c9b760f8e6f"
BINARY = Path("/home/genie/.brain/bin/brain")
BINARY_SHA = "631de1401390e53ecccf643586879097e23b363a7afea56374e95188f63def78"
BASE = "/qualification/sandbox"
RECEIPTS = HERE / "native-receipts.json"


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, allow_nan=False,
                           sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def redact(text):
    for name in ("owner-password", "denied-password"):
        path = SANDBOX / name
        if path.exists():
            text = text.replace(path.read_text().strip(), "<isolated-lab-secret>")
    return text


def run(argv, *, stdin=None, timeout=60, check=True):
    proc = subprocess.run(argv, input=stdin, text=True, capture_output=True, timeout=timeout)
    result = {"command": redact(json.dumps(argv)), "exit_code": proc.returncode,
              "stdout": redact(proc.stdout), "stderr": redact(proc.stderr)}
    if check and proc.returncode:
        raise RuntimeError(json.dumps(result))
    return result


def pg(sql, *, database="brain", check=True):
    return run(["docker", "exec", "-i", "-u", "1001:1001", CONTAINER,
                "psql", "-X", "-v", "ON_ERROR_STOP=1", "-h", BASE + "/socket",
                "-U", "oi5_owner", "-d", database, "-At"], stdin=sql, check=check)


def native_env(*, denied=False, brain_id=None):
    role = "oi5_denied" if denied else "oi5_owner"
    password = (SANDBOX / ("denied-password" if denied else "owner-password")).read_text().strip()
    dsn = f"postgresql://{role}:{password}@127.0.0.1:5432/brain"
    env = {"PATH": "/opt/brain:/usr/bin:/bin", "HOME": BASE + "/home",
           "BRAIN_HOME": BASE + "/home/.brain", "XDG_RUNTIME_DIR": BASE + "/socket",
           "TMPDIR": BASE + "/tmp", "DATABASE_URL": dsn,
           "BRAIN_CONTROL_DATABASE": "brain", "BRAIN_MEMORY_VECTORS": "off",
           "BRAIN_OMNI_GLOBAL_KILL": "1", "BRAIN_QUIET": "1"}
    if not denied:
        env["BRAIN_ADMIN_DATABASE_URL"] = dsn.rsplit("/", 1)[0] + "/postgres"
    if brain_id is not None:
        env["BRAIN_ID"] = brain_id
    return env


def native_argv(command, *, denied=False, brain_id=None):
    env = native_env(denied=denied, brain_id=brain_id)
    return ["docker", "exec", "-i", "-u", "1001:1001", "-w", BASE + "/vault",
            CONTAINER, "env", "-i", *(f"{key}={value}" for key, value in env.items()), *command]


class NativeRpcError(RuntimeError):
    """An actual native JSON-RPC error, distinct from transport failure."""


class NativeMcp:
    def __init__(self, brain_id, *, denied=False):
        self.brain_id = brain_id
        self.pending = queue.Queue()
        self.sequence = 0
        self.process = subprocess.Popen(native_argv(["/opt/brain/brain-mcp"],
                                                    denied=denied, brain_id=brain_id),
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)
        self.stderr = []
        threading.Thread(target=self._stdout, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()
        try:
            self.identity = self.request("initialize", {
                "protocolVersion": "2026-07-28", "capabilities": {},
                "clientInfo": {"name": "oi5-native-qualification", "version": "1.0.0"}})
            self.notify("notifications/initialized", {})
            self.tools = self.request("tools/list", {})
        except BaseException:
            self.close()
            raise

    def _stdout(self):
        for line in self.process.stdout:
            try:
                self.pending.put(json.loads(line))
            except ValueError:
                self.pending.put({"fatal": redact(line)})
        self.pending.put({"fatal": "native MCP stdout closed"})

    def _stderr(self):
        for line in self.process.stderr:
            self.stderr.append(redact(line))

    def notify(self, method, params):
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.sequence += 1
        ident = self.sequence
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": ident,
                                            "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 30
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("native MCP timed out: " + method)
            try:
                response = self.pending.get(timeout=remaining)
            except queue.Empty as exc:
                raise RuntimeError("native MCP timed out: " + method) from exc
            if "fatal" in response:
                raise RuntimeError(response["fatal"] + "\n" + "".join(self.stderr))
            if response.get("id") != ident:
                continue
            if "error" in response:
                raise NativeRpcError(json.dumps(response["error"]))
            return response["result"]

    def call(self, name, arguments, receipts, *, expected_error=None):
        assert arguments.get("brain_id") == self.brain_id, "implicit/foreign authority"
        descriptor = next(tool for tool in self.tools["tools"] if tool["name"] == name)
        schema = descriptor["inputSchema"]
        assert set(arguments) <= set(schema["properties"]), "unadvertised argument"
        assert set(schema.get("required", [])) <= set(arguments), "missing native argument"
        try:
            wire = self.request("tools/call", {"name": name, "arguments": arguments})
        except NativeRpcError as exc:
            wire = {"rpc_error": json.loads(str(exc))}
        receipt = {"tool": name, "arguments": content_summary(arguments),
                   "response_sha256": digest(wire), "response": content_summary(wire)}
        receipts.append(receipt)
        if wire.get("isError") is True or "rpc_error" in wire:
            raw = json.dumps(wire, ensure_ascii=False, allow_nan=False, sort_keys=True)
            safe = redact(raw)
            receipt["error_body_capture"] = {
                "encoding": "redacted JSON of actual native response",
                "raw_response_sha256": digest(wire),
                "redacted_utf8_bytes": len(safe.encode()), "limit_utf8_bytes": 16384,
                "complete": len(safe.encode()) <= 16384,
                "body": safe.encode()[:16384].decode("utf-8", errors="ignore")}
            assert receipt["error_body_capture"]["complete"], "native error exceeds admitted capture bound"
        if expected_error is not None:
            assert wire.get("isError") is True or "rpc_error" in wire, "expected native rejection did not occur"
            choices = (expected_error,) if isinstance(expected_error, str) else expected_error
            assert any(choice.lower() in json.dumps(wire).lower() for choice in choices), "wrong rejection"
            return wire
        assert not wire.get("isError") and "rpc_error" not in wire, json.dumps(content_summary(wire))
        if "structuredContent" in wire:
            return wire["structuredContent"]
        text = "\n".join(item["text"] for item in wire.get("content", []) if item["type"] == "text")
        return json.loads(text)

    def close(self):
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()


def content_summary(value):
    """Keep response identities/metadata, not a second copy of canonical evidence."""
    if isinstance(value, list):
        return [content_summary(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "content" and isinstance(item, str):
            result[key + "_receipt"] = {"sha256": digest(item.encode()), "utf8_bytes": len(item.encode())}
        elif key == "text" and isinstance(item, str):
            # MCP text repeats structuredContent, sometimes containing whole source bytes.
            result[key + "_receipt"] = {"sha256": digest(item.encode()), "utf8_bytes": len(item.encode())}
        else:
            result[key] = content_summary(item)
    return result


def save_receipts(result):
    # One top-level value per line; all existing fields survive serialization.
    text = "{\n" + ",\n".join(
        "  " + json.dumps(key) + ": " + json.dumps(value, ensure_ascii=False, allow_nan=False,
                                                  separators=(",", ":"))
        for key, value in result.items()) + "\n}\n"
    RECEIPTS.write_text(text)

def inspect_container():
    info = json.loads(run(["docker", "inspect", CONTAINER])["stdout"])[0]
    assert info["HostConfig"]["NetworkMode"] == "none", "network isolation changed"
    assert not info["HostConfig"].get("PortBindings"), "ports published"
    assert info["HostConfig"]["ReadonlyRootfs"], "root is writable"
    assert info["Config"]["User"] == "1001:1001", "OS principal changed"
    assert not info["HostConfig"]["Privileged"], "privileged container"
    assert info["Image"] == IMAGE.split("@", 1)[1], "image drift"
    mounts = {item["Destination"]: item for item in info["Mounts"]}
    assert len(info["Mounts"]) == 4 and all(item["Type"] == "bind" for item in info["Mounts"])
    assert set(mounts) == {"/opt/brain", BASE, "/licensed-sources", "/var/lib/postgresql/data"}, "unexpected mount"
    assert not mounts["/opt/brain"]["RW"] and not mounts["/licensed-sources"]["RW"]
    assert mounts[BASE]["RW"] and Path(mounts[BASE]["Source"]).resolve() == SANDBOX
    assert mounts["/var/lib/postgresql/data"]["RW"]
    assert Path(mounts["/var/lib/postgresql/data"]["Source"]).resolve() == SANDBOX / "pgdata"
    return {"container_id": info["Id"], "image": info["Image"], "network": "none",
            "user": info["Config"]["User"], "mounts": [
                {"destination": dest, "writable": mount["RW"]} for dest, mount in mounts.items()],
            "ports_published": False, "root_readonly": True, "running": info["State"]["Running"]}


def repair_control_database():
    """Perform only the human-admitted repair on the preserved native cluster."""
    assert digest(BINARY.read_bytes()) == BINARY_SHA, "installed binary drift"
    assert (SANDBOX / ".gitignore").read_text() == "*\n!.gitignore\n"
    info = inspect_container()
    assert info["container_id"] == "845fa540c621ab48bba9d736718259fefc78e4a7888d67696d95444a1b5587af"
    assert not info["running"], "repair requires the admitted stopped container"
    history = json.loads(RECEIPTS.read_text())
    result = {"stage": "control_database_repair_3", "task": "task_1ee57daded7e",
              "dispatch": "ctx_ed2a28fd3625", "binary_sha256": BINARY_SHA, "commands": [],
              "brain_id": None, "live_schema_sha256": None, "evidence_tools_called": False,
              "paid_calls": 0, "provider": None,
              "acceptance": ["BLOCKED", "BLOCKED", "DOCUMENTED", "DOCUMENTED"],
              "bootstrap_history": [history]}
    diagnostic = []
    attached = None
    def capture(stream):
        for line in stream:
            diagnostic.append(redact(line))
    try:
        attached = subprocess.Popen(["docker", "start", "--attach", CONTAINER],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        reader = threading.Thread(target=capture, args=(attached.stdout,), daemon=True)
        reader.start()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            identity = pg("SELECT current_user,current_database(),version(),pg_postmaster_start_time();",
                          database="postgres", check=False)
            if identity["exit_code"] == 0:
                break
            if attached.poll() is not None:
                raise RuntimeError("isolated native PostgreSQL exited: " + "".join(diagnostic))
            time.sleep(0.25)
        else:
            raise RuntimeError("native maintenance database SQL readiness deadline exceeded")
        result["commands"].append(identity)
        existence = pg("SELECT datname,pg_get_userbyid(datdba) FROM pg_database WHERE datname='brain';",
                       database="postgres")
        result["commands"].append(existence)
        if not existence["stdout"].strip():
            result["commands"].append(pg("CREATE DATABASE brain OWNER oi5_owner;", database="postgres"))
        else:
            assert existence["stdout"].strip() == "brain|oi5_owner", "foreign control database owner"
        result["commands"].append(pg("SELECT current_user,current_database(),version(),pg_postmaster_start_time();"))
        result["container"] = inspect_container()
        result["commands"].append(run(native_argv(["/opt/brain/brain", "--version", "--capabilities"])))
        result["commands"].append(run(native_argv(["/opt/brain/brain", "init", "--name", "oi5-qualification",
                                                  "--path", BASE + "/vault"])))
        manifest = json.loads(run(["docker", "exec", CONTAINER, "cat", BASE + "/vault/brain.json"])["stdout"])
        result["native_manifest"] = manifest
        result["brain_id"] = manifest["id"]
        result["registry"] = pg("SELECT id, short_name, owner_type, owner_id, home_path FROM brains;")["stdout"]
        client = NativeMcp(result["brain_id"])
        try:
            result["mcp_identity"] = client.identity
            result["live_tools"] = client.tools
            result["live_schema_sha256"] = digest(client.tools)
        finally:
            client.close()
        result["status"] = "AWAITING_SECOND_NATIVE_AUTHORITY_AND_SCHEMA_FREEZE"
    except Exception as exc:
        result["status"] = "BLOCKED_BOOTSTRAP"
        result["blocker"] = redact(str(exc))
        result["commands"].append(run(["docker", "stop", "--time", "20", CONTAINER], check=False))
    finally:
        if attached is not None:
            if attached.poll() is None:
                attached.terminate()
            attached.wait(timeout=5)
            reader.join(timeout=5)
            attached.stdout.close()
        (SANDBOX / "bootstrap.log").write_text("".join(diagnostic))
        result["bootstrap_diagnostic"] = "".join(diagnostic)
    save_receipts(result)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"live_tools", "commands", "bootstrap_history"}}, indent=2))
    if result["status"] == "BLOCKED_BOOTSTRAP":
        raise SystemExit(1)


def evidence_records(*, ingested_at=None):
    fixture_path = ROOT / "tests/fixtures/evidence_contracts.json"
    assert digest(fixture_path.read_bytes()) == "48b857151ad0899a130b9f9cc7096bc96fcd59c865883fb887048d93593885b5"
    fixture = json.loads(fixture_path.read_text())
    records = [(collection, record, {"LAB": True, "fixture_sha256": digest(fixture_path.read_bytes())})
               for collection in ("entities", "source_revisions", "evidence_spans", "claims",
                                  "economic_relationships")
               for record in fixture[collection]]
    licensed = json.loads((ROOT / "investigations/frontier-economics/sources.json").read_text())["licensed_subset"]
    acquisition = next(item for item in licensed["acquisitions"] if item["entity_id"] == "Q2283")
    statement = next(item for item in licensed["financial_statements"]
                     if item["id"] == "Q2283$564CF0AD-3A7D-4250-AA0C-40518A8833D9")
    raw = (ROOT / acquisition["original_path"]).read_bytes()
    assert digest(raw) == acquisition["original_sha256"]
    decoded = gzip.decompress(raw)
    assert digest(decoded) == acquisition["decoded_utf8_sha256"]
    start, end = statement["selector"]["start"], statement["selector"]["end"]
    quote = decoded[start:end].decode("utf-8")
    assert digest(quote.encode()) == statement["quote_sha256"]
    parsed = json.loads(decoded)["entities"]["Q2283"]
    native_ingestion = ingested_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    source_id = "source:brain:Q2283:r2550576892:text:1"
    span_id = "span:brain:Q2283:P2139:1"
    claim_id = "claim:brain:Q2283:P2139:1"
    provenance = {"LAB": False, "verification": "unverified", "original_acquisition": acquisition,
                  "original_statement": statement,
                  "extraction_method": "identity-decode-gzip-utf8-json-as-text/1",
                  "extracted_text_sha256": digest(decoded), "quote_sha256": digest(quote.encode()),
                  "original_media_type": acquisition["content_type"],
                  "original_content_encoding": acquisition["content_encoding"]}
    real = [
        ("entities", {"id": "entity:microsoft", "kind": "organization",
                      "name": parsed["labels"]["en"]["value"], "aliases": []}),
        ("entities", {"id": "entity:wikidata", "kind": "organization", "name": "Wikidata", "aliases": []}),
        ("source_revisions", {"id": source_id, "source_id": acquisition["source_id"], "revision_of": None,
                             "change_kind": "original", "uri": acquisition["request_url"],
                             "content_sha256": digest(decoded), "content_text": decoded.decode("utf-8"),
                             "media_type": "text/plain; charset=utf-8", "source_published_at": None,
                             "observed_at": acquisition["request_finished_at"], "ingested_at": native_ingestion,
                             "origin_id": statement["origin_id"], "retention_status": "retained", "reason": None}),
        ("evidence_spans", {"id": span_id, "source_revision_id": source_id,
                           "selector": {"kind": "utf8_text", "start": start, "end": end}, "quote": quote}),
        ("claims", {"id": claim_id, "entity_ids": ["entity:microsoft"],
                    "proposition": "Unverified Wikidata P2139 assertion " + statement["id"] +
                                   ": amount " + statement["amount_decimal"] + " " + statement["currency"],
                    "asserted_by_entity_id": "entity:wikidata", "evidence_span_ids": [span_id],
                    "event_validity": {"start": None, "end": None}, "ingested_at": native_ingestion,
                    "revision_of": None, "status": "asserted"})]
    records.extend((collection, record, provenance) for collection, record in real)
    return records, claim_id, fixture


def verify_records(client, records, bindings, calls):
    restored = {}
    for collection, expected, provenance in records:
        bound = bindings[expected["id"]]
        observed = client.call("brain_get", {"brain_id": client.brain_id, "memory_id": bound["memory_id"]}, calls)
        assert observed["memory_id"] == bound["memory_id"] and observed["brain_id"] == client.brain_id
        assert observed["content"].encode() == canonical_bytes(expected)
        assert observed["metadata"]["canonical_sha256"] == bound["canonical_sha256"]
        assert observed["metadata"]["application_id"] == expected["id"]
        assert observed["metadata"]["collection"] == collection
        assert observed["metadata"]["provenance"] == provenance
        restored[expected["id"]] = json.loads(observed["content"])
    for collection, expected, _ in records:
        if collection != "claims":
            continue
        for span_id in restored[expected["id"]]["evidence_span_ids"]:
            span = restored[span_id]
            source = restored[span["source_revision_id"]]
            raw = source["content_text"].encode()
            assert digest(raw) == source["content_sha256"]
            assert raw[span["selector"]["start"]:span["selector"]["end"]].decode("utf-8") == span["quote"]
    return {"records": len(restored), "claim_span_source_equality": True}


def canonical_bytes(record):
    return json.dumps(record, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode()


def fact_query(client, subject, calls, *, as_of="2020-01-15"):
    return client.call("brain_fact_query", {"brain_id": client.brain_id, "subject": subject,
                                           "as_of": as_of}, calls)


def concurrent_facts(client, calls):
    rows = []
    scenarios = [
        ("entity:builder", "reported_claim", "claim:sustainable:1", "span:a:1"),
        ("entity:builder", "reported_claim", "claim:unsustainable:1", "span:b:1"),
        ("transaction:one", "has_investor", "entity:investor-a", "span:a:1"),
        ("transaction:one", "has_investor", "entity:investor-b", "span:a:1"),
        ("transaction:two", "has_investor", "entity:investor-a", "span:a:1")]
    for subject, predicate, obj, span in scenarios:
        response = client.call("brain_fact_assert", {
            "brain_id": client.brain_id, "subject": subject, "predicate": predicate, "object": obj,
            "supersede": False, "source": span, "valid_from": "2020-01-01", "valid_until": "2020-02-01",
            "metadata": {"LAB": True, "evidence_span_id": span,
                         "date_notice": "Synthetic projection dates, not inferred economic event dates"}}, calls)
        assert response["superseded"] == 0
        rows.append(response["triple"])
    expected = {}
    for subject in ("entity:builder", "transaction:one", "transaction:two"):
        observed = fact_query(client, subject, calls)["triples"]
        wanted = [row for row in rows if row["subject"] == subject]
        assert {row["id"] for row in observed} == {row["id"] for row in wanted}
        assert {(row["object"], row["provenance"]) for row in observed} == {
            (row["object"], row["provenance"]) for row in wanted}
        expected[subject] = wanted
    return expected


def verify_facts(client, expected, calls):
    for subject, wanted in expected.items():
        observed = fact_query(client, subject, calls)["triples"]
        fields = ("id", "subject", "predicate", "object", "valid_from", "valid_until", "provenance", "metadata")
        assert {digest({key: row[key] for key in fields}) for row in observed} == {
            digest({key: row[key] for key in fields}) for row in wanted}


def cited_recall(client, bindings, claim_id, calls):
    response = client.call("memory_recall", {
        "brain_id": client.brain_id, "query": claim_id, "limit": 100,
        "vec_weight": 0, "fts_weight": 1}, calls)
    target = bindings[claim_id]["memory_id"]
    assert any(hit["memory_id"] == target for hit in response["results"])
    assert any(citation["source"] == "khs_memory" and citation["id"] == target
               for citation in response["citations"])
    assert response["trace_id"] and "confidence" in response
    return {"target_memory_id": target, "trace_id": response["trace_id"],
            "citations": response["citations"], "confidence": response["confidence"]}


def qualify_document_graph(client, result, calls, *, resumed=False):
    vault = SANDBOX / "vault"
    if resumed:
        corpus = result["graph_corpus"]
        actual = {str(path.relative_to(vault)) for path in vault.rglob("*.md")}
        assert actual == set(corpus), "frozen graph corpus changed"
        assert not any(path.is_symlink() for path in vault.rglob("*")), "vault symlink"
        assert all(digest((vault / name).read_bytes()) == sha for name, sha in corpus.items())
    else:
        frozen_names = {"_index.md", "_Templates/daily.md", "_Templates/domain.md",
                        "_Templates/entity.md", "_Templates/intel.md", "_Templates/playbook.md"}
        actual = {str(path.relative_to(vault)) for path in vault.rglob("*.md")}
        assert actual == frozen_names, "unexpected corpus before graph sync"
        assert not any(path.is_symlink() for path in vault.rglob("*")), "vault symlink"
        corpus = {name: digest((vault / name).read_bytes()) for name in sorted(frozen_names)}
        for label in ("source", "target"):
            name = "lab-graph-" + label + ".md"
            body = "# OI5 LAB graph " + label + "\n\nOI5GRAPH" + label.upper() + " document-only qualification.\n"
            (vault / name).write_text(body)
            corpus[name] = digest(body.encode())
        help_receipt = run(native_argv(["/opt/brain/brain", "sync", "--help"], brain_id=client.brain_id))
        assert "--no-embed" in help_receipt["stdout"] and "--no-links" in help_receipt["stdout"]
        result["commands"].append(help_receipt)
        result["graph_corpus"] = corpus
        result["commands"].append(run(native_argv([
            "/opt/brain/brain", "sync", "--brain", client.brain_id, "--no-embed", "--no-links",
            "--path", BASE + "/vault"], brain_id=client.brain_id), timeout=120))
    docs = {}
    searches = {}
    for label in ("source", "target"):
        response = client.call("knowledge_search", {
            "brain_id": client.brain_id, "query": "OI5GRAPH" + label.upper()}, calls)
        name = "lab-graph-" + label + ".md"
        hits = [hit for hit in response["results"] if hit["path"] == name]
        assert len(hits) == 1, "exact LAB document not uniquely retrieved"
        hit = hits[0]
        assert hit["complete"] is True and hit["docid"], "incomplete document citation"
        assert hit["text"].encode() == (vault / name).read_bytes(), "document citation bytes differ"
        assert digest(hit["text"].encode()) == corpus[name], "document citation hash differs"
        assert "heading" in hit and isinstance(response["confidence"], dict)
        docs[label] = hit["docid"]
        searches[label] = {"citation": {key: hit[key] for key in ("path", "heading", "docid", "chunkIndex")},
                           "text_sha256": digest(hit["text"].encode()), "complete": hit["complete"],
                           "confidence": response["confidence"], "trace_id": None,
                           "trace_status": "Not exposed by the actual native search envelope"}
    client.call("brain_graph_link", {"brain_id": client.brain_id, "source_id": docs["source"],
                                    "target_id": docs["target"], "relationship": "lab_document_reference"}, calls)
    graph = client.call("brain_graph_query", {
        "brain_id": client.brain_id, "seed_id": docs["source"], "edge_type": "lab_document_reference"}, calls)
    assert any(node["path"].endswith("lab-graph-target.md") for node in graph["nodes"])
    assert graph["citations"] and all(cite["source"] == "brain_document" for cite in graph["citations"])
    return {"native_document_ids": docs, "searches": searches, "query": graph,
            "economic_relationships_emitted": [],
            "ruling": "Document references are not typed entity transactions or verified cash movements."}


def qualify_time(client, expected, calls):
    start = fact_query(client, "entity:builder", calls, as_of="2020-01-01")
    end = fact_query(client, "entity:builder", calls, as_of="2020-02-01")
    assert {row["id"] for row in start["triples"]} == {row["id"] for row in expected["entity:builder"]}
    assert end["triples"] == [], "valid_until not exclusive"
    client.call("brain_fact_query", {"brain_id": client.brain_id, "as_of": "2020-01-01T00:00:00Z"},
                calls, expected_error="Invalid")
    prior = client.call("brain_fact_assert", {
        "brain_id": client.brain_id, "subject": "LAB:single-valued", "predicate": "state", "object": "old",
        "valid_from": "2020-01-01", "metadata": {"LAB": True}}, calls)
    current = client.call("brain_fact_assert", {
        "brain_id": client.brain_id, "subject": "LAB:single-valued", "predicate": "state", "object": "new",
        "valid_from": "2020-01-10", "metadata": {"LAB": True}}, calls)
    assert prior["superseded"] == 0 and current["superseded"] == 1
    assert {row["object"] for row in fact_query(client, "LAB:single-valued", calls,
                                               as_of="2020-01-09")["triples"]} == {"old"}
    assert {row["object"] for row in fact_query(client, "LAB:single-valued", calls,
                                               as_of="2020-01-10")["triples"]} == {"new"}
    return {"date_only": True, "half_open": True, "default_supersedes": True,
            "instant_as_of_rejected": True, "bitemporal_replay": None,
            "bitemporal_status": "Unavailable: no native knowledge-time selector; history is not replay."}


def smoke():
    """Run once on the exact admitted native sandbox; stop on the next unexpected failure."""
    previous = json.loads(RECEIPTS.read_text())
    assert previous["status"] == "AWAITING_SECOND_NATIVE_AUTHORITY_AND_SCHEMA_FREEZE", "one-shot smoke already attempted"
    assert digest(BINARY.read_bytes()) == BINARY_SHA
    info = inspect_container()
    assert not info["running"] and info["container_id"] == "845fa540c621ab48bba9d736718259fefc78e4a7888d67696d95444a1b5587af"
    result = {"stage": "native_evidence_smoke", "task": "task_1ee57daded7e", "dispatch": "ctx_ed2a28fd3625",
              "binary_sha256": BINARY_SHA, "bootstrap_history": [previous], "commands": [], "tool_calls": [],
              "brain_id": previous["brain_id"], "provider": None, "paid_calls": 0,
              "budget_reservation_usd": 8, "budget_measured_spend_usd": 0,
              "acceptance": ["BLOCKED", "BLOCKED", "DOCUMENTED", "DOCUMENTED"],
              "status": "RUNNING", "bindings": {}}
    client = None
    calls = result["tool_calls"]
    try:
        result["commands"].append(run(["docker", "start", CONTAINER]))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            sql_ready = pg("SELECT current_user,current_database(),pg_postmaster_start_time();", check=False)
            if sql_ready["exit_code"] == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("actual control SQL readiness timed out")
        result["commands"].append(sql_ready)
        result["postmaster_before"] = sql_ready["stdout"]
        client = NativeMcp(result["brain_id"])
        assert digest(client.tools) == previous["live_schema_sha256"], "live native schemas changed"
        result["mcp_identity"] = client.identity
        result["live_schema_sha256"] = digest(client.tools)
        product = pg("SELECT datname,pg_get_userbyid(datdba) FROM pg_database WHERE datname='brain_oi5_qualification';")
        result["commands"].append(product)
        assert product["stdout"].strip() == "brain_oi5_qualification|oi5_owner"
        password = (SANDBOX / "denied-password").read_text().strip()
        assert password.isalnum(), "fresh lab password requires unambiguous SQL literal"
        result["commands"].append(pg(
            "CREATE ROLE oi5_denied LOGIN PASSWORD '" + password + "' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;\n"
            "GRANT CONNECT ON DATABASE brain TO oi5_denied;\n"
            "GRANT USAGE ON SCHEMA public TO oi5_denied;\n"
            "GRANT SELECT ON TABLE brains TO oi5_denied;\n"
            "REVOKE CONNECT ON DATABASE brain_oi5_qualification FROM PUBLIC;\n"
            "GRANT CONNECT ON DATABASE brain_oi5_qualification TO oi5_owner;\n"))
        records, claim_id, fixture = evidence_records()
        result["source_extraction"] = records[-1][2]
        bindings = result["bindings"]
        remembered = {}
        for collection, record, provenance in records:
            if record.get("revision_of") is not None:
                continue
            args = {"brain_id": client.brain_id, "content": canonical_bytes(record).decode(),
                    "scope": "global", "veracity": "imported", "source": record["id"],
                    "extract": False, "extract_entities": False, "operation_key": "oi5:" + record["id"],
                    "actor": "issue-5-engineer", "reason": "Approved isolated native evidence qualification",
                    "metadata": {"application_id": record["id"], "collection": collection,
                                 "canonical_sha256": digest(record), "provenance": provenance}}
            response = client.call("brain_remember", args, calls)
            assert response["brain_id"] == client.brain_id and response["action"] == "inserted"
            bindings[record["id"]] = {"collection": collection, "memory_id": response["memory_id"],
                                     "canonical_sha256": digest(record), "revision": response["revision"]}
            remembered[record["id"]] = args
        target_args = remembered[claim_id]
        replay = client.call("brain_remember", target_args, calls)
        assert replay["memory_id"] == bindings[claim_id]["memory_id"] and replay["revision"] == bindings[claim_id]["revision"]
        client.call("brain_remember", {**target_args, "content": target_args["content"] + " altered"},
                    calls, expected_error=("another digest", "IDEMPOTENCY_CONFLICT"))
        denied = NativeMcp(client.brain_id, denied=True)
        try:
            denied.call("brain_get", {"brain_id": client.brain_id, "memory_id": bindings[claim_id]["memory_id"]},
                        calls, expected_error="permission denied")
            denied.call("brain_remember", {**target_args, "content": "LAB denied write",
                                           "operation_key": "oi5:denied-write"},
                        calls, expected_error="permission denied")
        finally:
            denied.close()
        result["access_boundary"] = {"product_database": product["stdout"].strip(),
                                    "owner_role": "oi5_owner", "denied_role": "oi5_denied",
                                    "read_denied": True, "write_denied": True,
                                    "http_tenant_authentication": None, "server_rls": None}
        expected = concurrent_facts(client, calls)
        result["concurrent_before"] = expected
        for collection, record, provenance in records:
            if record.get("revision_of") is None:
                continue
            args = {"brain_id": client.brain_id, "content": canonical_bytes(record).decode(),
                    "scope": "global", "veracity": "imported", "source": record["id"],
                    "extract": False, "extract_entities": False, "operation_key": "oi5:" + record["id"],
                    "actor": "issue-5-engineer", "reason": "Append LAB correction without replacing accepted bytes",
                    "metadata": {"application_id": record["id"], "collection": collection,
                                 "canonical_sha256": digest(record), "provenance": provenance}}
            response = client.call("brain_remember", args, calls)
            bindings[record["id"]] = {"collection": collection, "memory_id": response["memory_id"],
                                     "canonical_sha256": digest(record), "revision": response["revision"]}
        mutable = client.call("brain_remember", {
            "brain_id": client.brain_id, "content": "OI5 LAB disposable revision old", "scope": "global",
            "extract": False, "extract_entities": False, "operation_key": "oi5:disposable",
            "actor": "issue-5-engineer", "reason": "Separate mutable LAB control", "metadata": {"LAB": True}}, calls)
        changed = client.call("brain_update", {
            "brain_id": client.brain_id, "memory_id": mutable["memory_id"],
            "content": "OI5 LAB disposable revision new", "expected_revision": mutable["revision"],
            "operation_key": "oi5:disposable-update", "actor": "issue-5-engineer", "reason": "LAB update control"}, calls)
        assert changed["revision"] == mutable["revision"] + 1
        client.call("brain_update", {
            "brain_id": client.brain_id, "memory_id": mutable["memory_id"], "content": "OI5 LAB stale",
            "expected_revision": mutable["revision"], "operation_key": "oi5:stale-update"},
                    calls, expected_error=("revision conflict", "REVISION_CONFLICT"))
        history_args = {"brain_id": client.brain_id, "memory_id": mutable["memory_id"], "limit": 20}
        history = client.call("brain_memory_history", history_args, calls)
        assert {row["content"] for row in history["revisions"]} == {
            "OI5 LAB disposable revision old", "OI5 LAB disposable revision new"}
        result["mutable_history_before"] = history
        result["readback_before"] = verify_records(client, records, bindings, calls)
        verify_facts(client, expected, calls)
        result["cited_recall_before"] = cited_recall(client, bindings, claim_id, calls)
        result["document_graph"] = qualify_document_graph(client, result, calls)
        result["acceptance"][2] = "PASS_ISOLATED_NATIVE_DOCUMENT_BOUNDARY"
        result["time"] = qualify_time(client, expected, calls)
        result["acceptance"][3] = "PASS_SUPPORTED_TIME_AND_DOCUMENTED_REPLAY_LIMIT"
        client.close()
        client = None
        result["commands"].append(run(["docker", "restart", "--time", "20", CONTAINER]))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            restart_sql = pg("SELECT current_user,current_database(),pg_postmaster_start_time();", check=False)
            if restart_sql["exit_code"] == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("actual SQL readiness after restart timed out")
        result["commands"].append(restart_sql)
        result["postmaster_after"] = restart_sql["stdout"]
        assert result["postmaster_after"] != result["postmaster_before"], "no PostgreSQL restart observed"
        client = NativeMcp(result["brain_id"])
        assert digest(client.tools) == result["live_schema_sha256"]
        result["readback_after"] = verify_records(client, records, bindings, calls)
        result["cited_recall_after"] = cited_recall(client, bindings, claim_id, calls)
        verify_facts(client, expected, calls)
        after_history = client.call("brain_memory_history", history_args, calls)
        assert after_history == history
        result["mutable_history_after"] = after_history
        result["concurrent_after"] = expected
        result["acceptance"][:2] = ["PASS_EXACT_SPAN_AFTER_NATIVE_RESTART", "PASS_CONCURRENT_INGEST_UPDATE_RESTART"]
        result["status"] = "PASS_ISOLATED_NATIVE_QUALIFICATION_NOT_DEPLOYMENT"
    except Exception as exc:
        result["status"] = "BLOCKED_NEXT_UNEXPECTED_FAILURE_REPAIR_CAP_EXHAUSTED"
        result["blocker"] = redact(str(exc))
    finally:
        if client is not None:
            client.close()
        result["commands"].append(run(["docker", "stop", "--time", "20", CONTAINER], check=False))
        result["custody"] = inspect_container()
        result["custody"]["pgdata_deleted"] = False
        result["custody"]["handoff_owner"] = "coordinator; stopped native sandbox and ignored PGDATA retained"
        save_receipts(result)
    print(json.dumps({key: result.get(key) for key in
                      ("stage", "status", "brain_id", "acceptance", "blocker", "paid_calls", "custody")}, indent=2))
    raise SystemExit(0 if result["status"].startswith("PASS") else 1)


def resume_smoke():
    """Continue only the human-admitted fourth repair, preserving every prior receipt."""
    raw = RECEIPTS.read_bytes()
    assert digest(raw) == "4b7cd8c3ee6e2d1267f4de2ca698683f552f932783feb913be77230e834ba019"
    previous = json.loads(raw)
    assert previous["status"] == "BLOCKED_NEXT_UNEXPECTED_FAILURE_REPAIR_CAP_EXHAUSTED"
    assert previous["blocker"] == "'citations'" and len(previous["tool_calls"]) == 73
    assert len(previous["bindings"]) == 26 and previous["brain_id"] == "brn_63n8pr"
    assert digest(BINARY.read_bytes()) == BINARY_SHA
    info = inspect_container()
    assert not info["running"] and info["container_id"] == "845fa540c621ab48bba9d736718259fefc78e4a7888d67696d95444a1b5587af"
    result = {**previous, "stage": "native_evidence_resume_smoke", "dispatch": "ctx_f79253ca87d2",
              "status": "RUNNING", "continuation_history": [previous],
              "prior_receipt_sha256": digest(raw), "repair_cap": 4, "repairs_used": 4,
              "commands": list(previous["commands"]), "tool_calls": list(previous["tool_calls"]),
              "acceptance": list(previous["acceptance"])}
    result.pop("blocker")
    client = None
    calls = result["tool_calls"]
    try:
        result["commands"].append(run(["docker", "start", CONTAINER]))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            sql_ready = pg("SELECT current_user,current_database(),pg_postmaster_start_time();", check=False)
            if sql_ready["exit_code"] == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("actual control SQL readiness timed out")
        result["commands"].append(sql_ready)
        result["postmaster_before"] = sql_ready["stdout"]
        client = NativeMcp(result["brain_id"])
        assert digest(client.tools) == previous["live_schema_sha256"], "live native schemas changed"
        assert client.identity == previous["mcp_identity"], "native MCP identity changed"
        bindings = previous["bindings"]
        claim_id = "claim:brain:Q2283:P2139:1"
        original = client.call("brain_get", {
            "brain_id": client.brain_id, "memory_id": bindings[claim_id]["memory_id"]}, calls)
        assert digest(original["content"].encode()) == bindings[claim_id]["canonical_sha256"]
        records, rebuilt_claim_id, _ = evidence_records(ingested_at=json.loads(original["content"])["ingested_at"])
        assert rebuilt_claim_id == claim_id and {record["id"] for _, record, _ in records} == set(bindings)
        assert all(digest(record) == bindings[record["id"]]["canonical_sha256"] for _, record, _ in records)
        result["readback_resume_before"] = verify_records(client, records, bindings, calls)
        expected = previous["concurrent_before"]
        verify_facts(client, expected, calls)
        history = previous["mutable_history_before"]
        history_args = {"brain_id": client.brain_id, "memory_id": history["memory_id"], "limit": 20}
        assert client.call("brain_memory_history", history_args, calls) == history
        negatives = [call for call in previous["tool_calls"]
                     if call["response"].get("isError") is True or "rpc_error" in call["response"]]
        assert len(negatives) == 4
        denied = NativeMcp(client.brain_id, denied=True)
        try:
            for index, control in enumerate(negatives):
                args = dict(control["arguments"])
                content = args.pop("content_receipt", None)
                if content is not None:
                    args["content"] = (original["content"] + " altered" if index == 0 else
                                       "LAB denied write" if index == 2 else "OI5 LAB stale")
                    assert digest(args["content"].encode()) == content["sha256"]
                    assert len(args["content"].encode()) == content["utf8_bytes"]
                assert content_summary(args) == control["arguments"], "negative-control arguments changed"
                target = denied if index in (1, 2) else client
                error = ("another digest", "IDEMPOTENCY_CONFLICT") if index == 0 else (
                    ("revision conflict", "REVISION_CONFLICT") if index == 3 else "permission denied")
                target.call(control["tool"], args, calls, expected_error=error)
        finally:
            denied.close()
        result["negative_controls_direct"] = calls[-4:]
        result["document_graph"] = qualify_document_graph(client, result, calls, resumed=True)
        result["acceptance"][2] = "PASS_ISOLATED_NATIVE_DOCUMENT_BOUNDARY"
        result["time"] = qualify_time(client, expected, calls)
        result["acceptance"][3] = "PASS_SUPPORTED_TIME_AND_DOCUMENTED_REPLAY_LIMIT"
        client.close()
        client = None
        result["commands"].append(run(["docker", "restart", "--time", "20", CONTAINER]))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            restart_sql = pg("SELECT current_user,current_database(),pg_postmaster_start_time();", check=False)
            if restart_sql["exit_code"] == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("actual SQL readiness after restart timed out")
        result["commands"].append(restart_sql)
        result["postmaster_after"] = restart_sql["stdout"]
        assert result["postmaster_after"] != result["postmaster_before"], "no PostgreSQL restart observed"
        client = NativeMcp(result["brain_id"])
        assert digest(client.tools) == result["live_schema_sha256"]
        assert client.identity == previous["mcp_identity"]
        result["readback_after"] = verify_records(client, records, bindings, calls)
        result["cited_recall_after"] = cited_recall(client, bindings, claim_id, calls)
        verify_facts(client, expected, calls)
        after_history = client.call("brain_memory_history", history_args, calls)
        assert after_history == history
        result["mutable_history_after"] = after_history
        result["concurrent_after"] = expected
        result["acceptance"][:2] = ["PASS_EXACT_SPAN_AFTER_NATIVE_RESTART", "PASS_CONCURRENT_INGEST_UPDATE_RESTART"]
        result["status"] = "PASS_ISOLATED_NATIVE_QUALIFICATION_NOT_DEPLOYMENT"
    except Exception as exc:
        result["status"] = "BLOCKED_NEXT_UNEXPECTED_FAILURE_REPAIR_CAP_EXHAUSTED"
        result["blocker"] = redact(str(exc))
    finally:
        if client is not None:
            client.close()
        result["commands"].append(run(["docker", "stop", "--time", "20", CONTAINER], check=False))
        result["custody"] = inspect_container()
        result["custody"]["pgdata_deleted"] = False
        result["custody"]["handoff_owner"] = "coordinator; stopped native sandbox and ignored PGDATA retained"
        result["preserved_prior_calls_equal"] = calls[:73] == previous["tool_calls"]
        result["preserved_prior_bindings_equal"] = result["bindings"] == previous["bindings"]
        save_receipts(result)
    print(json.dumps({key: result.get(key) for key in
                      ("stage", "status", "brain_id", "acceptance", "blocker", "paid_calls", "custody")}, indent=2))
    raise SystemExit(0 if result["status"].startswith("PASS") else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--repair-control-db", action="store_true")
    actions.add_argument("--smoke", action="store_true")
    actions.add_argument("--resume-smoke", action="store_true")
    args = parser.parse_args()
    if args.resume_smoke:
        resume_smoke()
    elif args.smoke:
        smoke()
    else:
        repair_control_database()
