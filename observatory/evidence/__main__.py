"""Explicit isolated native import/read CLI; collection is not a supported action."""
import argparse
import json
import sys

from .brain import BrainEvidence, canonical, isolated_argv
from .contracts import load_bundle, require
from .model import inspect_edge, project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("import", "view", "serve"))
    parser.add_argument("--bundle")
    parser.add_argument("--manifest")
    parser.add_argument("--scene")
    args = parser.parse_args()
    brain = BrainEvidence(isolated_argv(), brain_id="brn_63n8pr")
    try:
        if args.action == "import":
            require(args.bundle is not None, "explicit bundle required")
            # Parent-custodied original application identities may only be read/reused.
            receipt = load_bundle("integrations/brain/qualification/native-receipts.json")
            protected = [{**b, "application_id": ident, "brain_id": brain.brain_id}
                         for ident, b in receipt["bindings"].items()]
            print(canonical(brain.import_bundle(load_bundle(args.bundle), protected_bindings=protected)))
            return
        if args.action == "serve":
            config = json.loads(sys.stdin.readline())
            binding, scene = config["binding"], config["scene_id"]
        else:
            require(args.manifest is not None and args.scene is not None, "explicit manifest and Scene required")
            binding, scene = load_bundle(args.manifest)["binding"], args.scene
        bundle, bindings = brain.restore(binding)
        view = project(bundle, scene)
        view["native_references"] = bindings
        if args.action == "view":
            print(canonical(view))
            return
        print(canonical({"ready": True}), flush=True)
        for line in sys.stdin:
            request = json.loads(line)
            require(set(request) <= {"id", "action", "edge_id"}, "unexpected reader request")
            require(request["action"] in {"view", "inspect"}, "unadmitted reader action")
            result = view if request["action"] == "view" else brain.inspect_view(view, bindings, request["edge_id"])
            print(canonical({"id": request["id"], "result": result}), flush=True)
    finally:
        brain.close()


if __name__ == "__main__":
    main()
