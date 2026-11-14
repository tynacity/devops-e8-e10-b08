#!/bin/sh
# Run from the experiment repository root after restoring the TinyExpr bundle.
set -eu
out=${1:?Provide a fresh output directory under work/}
PYTHONPATH=labs/e11e12/vendor python3 - "$out" <<'PY'
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from draft.autobuild import auto_build

manifest = json.loads(Path("data/tinyexpr-input.json").read_text())
repo = "data/real-project"
target = manifest["target_commit"]
subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor",
                manifest["base_commit"], target], check=True)
with tempfile.TemporaryDirectory() as directory:
    project = Path(directory) / "project"
    subprocess.run(["git", "clone", "--quiet", "--no-checkout", repo, project], check=True)
    subprocess.run(["git", "-C", project, "checkout", "--quiet", "--detach", target], check=True)
    result = auto_build(project, "data/real-candidate.Dockerfile", sys.argv[1],
                        manifest["expected_output"], timeout=600)
    print(result["status"], result.get("error", ""))
    raise SystemExit(result["status"] != "SUCCEEDED")
PY
