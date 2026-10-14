"""Explicit native Brain transport and immutable application bindings; no side store."""
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import threading

from .contracts import FIELDS, load_bundle, record_digest, require, validate_bundle

BINARY_SHA = "631de1401390e53ecccf643586879097e23b363a7afea56374e95188f63def78"
TOOLS_SHA = "387088e0c7c508bb2521a48635757887852f9f9a7fa3ff7c5d8844760325d76b"
CONTAINER = "845fa540c621ab48bba9d736718259fefc78e4a7888d67696d95444a1b5587af"
ROOT = Path(__file__).resolve().parents[2]
SANDBOX = ROOT / "integrations/brain/qualification/sandbox"
BASE = "/qualification/sandbox"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class NativeError(RuntimeError):
    def __init__(self, body):
        self.body = body
        super().__init__("Native Brain rejected call: " + record_digest(body))


def isolated_argv(*, denied=False):
    """Use only the parent-admitted stopped-runtime identity; never start it here."""
    info = json.loads(subprocess.check_output(["docker", "inspect", CONTAINER]))[0]
    require(info["Id"] == CONTAINER and info["State"]["Running"], "admitted runtime not running")
    require(info["Config"]["User"] == "1001:1001", "native OS principal drift")
    host = info["HostConfig"]
    require(host["NetworkMode"] == "none" and host["ReadonlyRootfs"] and not host["PortBindings"]
            and not host["Privileged"], "native isolation drift")
    require(info["Image"] == "sha256:cf134a767f474095eeba57e0117be8e568e011a63f33fbf252f14c9b760f8e6f", "native image drift")
    mounts = {m["Destination"]: m for m in info["Mounts"]}
    expected = {"/opt/brain": (Path("/home/genie/.brain/bin"), False), BASE: (SANDBOX, True),
                "/licensed-sources": (ROOT / "investigations/frontier-economics/licensed-sources", False),
                "/var/lib/postgresql/data": (SANDBOX / "pgdata", True)}
    require(len(info["Mounts"]) == len(expected) and set(mounts) == set(expected), "native mounts drift")
    for dest, (source, writable) in expected.items():
        require(mounts[dest]["Type"] == "bind" and Path(mounts[dest]["Source"]).resolve() == source.resolve()
                and mounts[dest]["RW"] == writable, "native bind drift")
    require(hashlib.sha256(Path("/home/genie/.brain/bin/brain").read_bytes()).hexdigest() == BINARY_SHA, "native binary drift")
    role = "oi5_denied" if denied else "oi5_owner"
    password = (SANDBOX / ("denied-password" if denied else "owner-password")).read_text().strip()
    dsn = f"postgresql://{role}:{password}@127.0.0.1:5432/brain"
    env = {"PATH": "/opt/brain:/usr/bin:/bin", "HOME": BASE + "/home", "BRAIN_HOME": BASE + "/home/.brain",
           "XDG_RUNTIME_DIR": BASE + "/socket", "TMPDIR": BASE + "/tmp", "DATABASE_URL": dsn,
           "BRAIN_CONTROL_DATABASE": "brain", "BRAIN_MEMORY_VECTORS": "off", "BRAIN_OMNI_GLOBAL_KILL": "1",
           "BRAIN_QUIET": "1", "BRAIN_ID": "brn_63n8pr"}
    return ["docker", "exec", "-i", "-u", "1001:1001", "-w", BASE + "/vault", CONTAINER,
            "env", "-i", *(f"{k}={v}" for k, v in env.items()), "/opt/brain/brain-mcp"]


class BrainEvidence:
    def __init__(self, argv, *, brain_id):
        require(re.fullmatch(r"brn_[a-z0-9_]+", brain_id) is not None, "explicit Brain authority required")
        self.brain_id, self.sequence, self.calls = brain_id, 0, []
        self.pending = queue.Queue()
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.identity = self.request("initialize", {"protocolVersion": "2026-07-28", "capabilities": {},
                        "clientInfo": {"name": "observatory-evidence", "version": "1.0.0"}})
            require(self.identity["serverInfo"] == {"name": "brain", "version": "0.0"}
                    and self.identity["protocolVersion"] == "2025-11-25", "native identity drift")
            self.send("notifications/initialized", {})
            self.tools = self.request("tools/list", {})
            require(record_digest(self.tools) == TOOLS_SHA, "native tool schema drift")
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self.pending.put(json.loads(line))
        except (ValueError, OSError):
            self.pending.put({"fatal": "invalid native transport"})
        finally:
            self.pending.put({"fatal": "native transport closed"})

    def send(self, method, params, ident=None):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if ident is not None:
            message["id"] = ident
        self.process.stdin.write(canonical(message) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.sequence += 1
        self.send(method, params, self.sequence)
        while True:
            try:
                response = self.pending.get(timeout=30)
            except queue.Empty as exc:
                raise RuntimeError("native request timeout") from exc
            require("fatal" not in response, response.get("fatal", "native transport error"))
            if response.get("id") != self.sequence:
                continue
            if "error" in response:
                raise NativeError(response["error"])
            return response["result"]

    def call(self, name, arguments):
        require(arguments.get("brain_id") == self.brain_id, "foreign or implicit authority")
        require(name in {"brain_remember", "brain_get"}, "unadmitted native operation")
        schema = next(t["inputSchema"] for t in self.tools["tools"] if t["name"] == name)
        require(set(arguments) <= set(schema["properties"]) and set(schema.get("required", [])) <= set(arguments), "native arguments drift")
        wire = self.request("tools/call", {"name": name, "arguments": arguments})
        self.calls.append({"tool": name, "arguments_sha256": record_digest(arguments), "response_sha256": record_digest(wire)})
        if wire.get("isError"):
            raise NativeError(wire)
        if "structuredContent" in wire:
            return wire["structuredContent"]
        return json.loads("\n".join(c["text"] for c in wire["content"] if c["type"] == "text"))

    def remember(self, collection, record, *, provenance=None):
        ident, digest = record["id"], record_digest(record)
        result = self.call("brain_remember", {"brain_id": self.brain_id, "content": canonical(record),
            "scope": "global", "veracity": "imported", "source": ident, "extract": False, "extract_entities": False,
            "operation_key": "oi7:" + hashlib.sha256(ident.encode()).hexdigest(), "actor": "issue-7-engineer",
            "reason": "Admitted isolated investigation evidence import", "metadata": {"application_id": ident,
            "collection": collection, "canonical_sha256": digest, "provenance": provenance}})
        require(result["brain_id"] == self.brain_id, "native write authority mismatch")
        binding = {"brain_id": self.brain_id, "application_id": ident, "collection": collection,
                   "canonical_sha256": digest, "memory_id": result["memory_id"], "revision": result["revision"]}
        self.get(binding)
        return binding

    def get(self, binding):
        require(binding["brain_id"] == self.brain_id, "foreign binding authority")
        result = self.call("brain_get", {"brain_id": self.brain_id, "memory_id": binding["memory_id"]})
        require(result["brain_id"] == self.brain_id and result["memory_id"] == binding["memory_id"]
                and result["revision"] == binding["revision"], "native binding identity/revision mismatch")
        require(hashlib.sha256(result["content"].encode()).hexdigest() == binding["canonical_sha256"], "native canonical bytes mismatch")
        record = json.loads(result["content"])
        require(record["id"] == binding["application_id"] and canonical(record) == result["content"], "native application identity mismatch")
        for key in ("application_id", "collection", "canonical_sha256"):
            require(result["metadata"][key] == binding[key], "native binding metadata mismatch")
        return record

    def import_bundle(self, bundle, *, protected_bindings=(), existing_manifest_binding=None):
        validate_bundle(bundle)
        if existing_manifest_binding is not None:
            accepted, _ = self.restore(existing_manifest_binding)
            require(canonical(accepted) == canonical(bundle), "existing manifest input conflict")
            return existing_manifest_binding
        protected = {b["application_id"]: b for b in protected_bindings}
        bindings = []
        for collection in FIELDS:
            for record in bundle[collection]:
                prior = protected.get(record["id"])
                if prior is not None:
                    require(prior["collection"] == collection and prior["canonical_sha256"] == record_digest(record), "protected application identity conflict")
                    self.get(prior)  # Never reimport or change the original qualification records.
                    bindings.append(prior)
                else:
                    bindings.append(self.remember(collection, record))
        root = {"id": "brain-manifest:oi7:2:" + record_digest(bundle), "manifest_version": "2",
                "canonical_bundle": canonical(bundle), "bundle_sha256": record_digest(bundle), "bindings": bindings}
        return self.remember("accepted_manifest", root)

    def restore(self, manifest_binding):
        require(manifest_binding["collection"] == "accepted_manifest", "not an accepted manifest binding")
        root = self.get(manifest_binding)
        require(set(root) == {"id", "manifest_version", "canonical_bundle", "bundle_sha256", "bindings"}
                and root["manifest_version"] == "2", "unsupported native manifest version")
        bundle = json.loads(root["canonical_bundle"])
        require(canonical(bundle) == root["canonical_bundle"] and record_digest(bundle) == root["bundle_sha256"],
                "durable bundle digest mismatch")
        require(root["id"] == "brain-manifest:oi7:2:" + root["bundle_sha256"], "manifest application identity mismatch")
        validate_bundle(bundle)
        expected = {(c, r["id"]): record_digest(r) for c in FIELDS for r in bundle[c]}
        bound = {}
        for binding in root["bindings"]:
            key = (binding["collection"], binding["application_id"])
            require(binding["brain_id"] == self.brain_id and key not in bound, "foreign or duplicate manifest binding")
            require(expected.get(key) == binding["canonical_sha256"], "manifest record binding mismatch")
            bound[key] = binding
        require(set(bound) == set(expected), "manifest binding closure mismatch")
        return bundle, root["bindings"]

    def inspect_view(self, view, bindings, edge_id):
        from .model import inspect_edge
        rows = inspect_edge(view, edge_id)
        bound = {b["application_id"]: b for b in bindings}
        edges = view["claim_evidence_edges"] + view["observation_evidence_edges"] + view["relationships"]
        edge = next(e for e in edges if e["id"] == edge_id)
        target = edge.get("claim_id", edge.get("observation_id", edge["id"]))
        self.get(bound[target])
        for row in rows:
            require(self.get(bound[row["span"]["id"]]) == row["span"], "native span differs from accepted manifest")
            require(self.get(bound[row["source_revision"]["id"]]) == row["source_revision"],
                    "native source differs from accepted manifest")
        return rows

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
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
                raise RuntimeError("native reader required forced termination")
        self.reader.join(timeout=5)
        require(not self.reader.is_alive(), "native reader cleanup incomplete")
        self.process.stdout.close()
        require(self.process.returncode == 0, "native reader exited unsuccessfully")
