"""Check the known source state and compare existing E10 evidence before/after."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BASE = "fb968b7e0d2b406905003d3956b3e177bea8e416"
LAB_SHA = "90c61fb18bcdd904fb03ade5553a2c599b4a983113175a506c2f5836b741e026"
TEST_BLOBS = {"a9d871fdf6b6f7f3b99d0a00b8c043a9c3beaf56", "e4f0fa3d6f756c70fe6091556b7f8338b7dee256"}
E10_DIRS = ("work/e10-B-manual.1jq7NB", "work/e10-B-member3.JsgLLh")
E10_MARKERS = ("work/last-e10-B.path", "work/last-e10-B-member3.path")


def command(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo).decode("utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def check(repo):
    if command(repo, "rev-parse", "HEAD").strip() != BASE:
        raise ValueError("SOURCE_HEAD_CHANGED")
    changed = set(command(repo, "diff", "--name-only", "HEAD", "--").splitlines())
    if not changed.issubset({"labs/e8e10/test_profile.py"}):
        raise ValueError("UNEXPECTED_TRACKED_CHANGES; preserved")
    if command(repo, "ls-files", "--others", "--exclude-standard", "--", "labs/e8e10").strip():
        raise ValueError("UNTRACKED_LAB_SOURCE; preserved")
    if digest(repo / "labs/e8e10/lab.py") != LAB_SHA:
        raise ValueError("LAB_SOURCE_CHANGED")
    if command(repo, "hash-object", "--no-filters", "labs/e8e10/test_profile.py").strip() not in TEST_BLOBS:
        raise ValueError("TEST_SOURCE_CHANGED; preserved")
    for name in (*E10_DIRS, *E10_MARKERS):
        path = repo / name
        if not path.exists() or path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
            raise ValueError("EXISTING_E10_PATH_MISSING_OR_UNEXPECTED " + name)


def snapshot(repo):
    check(repo)
    files = {}
    for name in E10_DIRS:
        for path in sorted((repo / name).rglob("*")):
            if path.is_symlink():
                raise ValueError("E10_EVIDENCE_SYMLINK " + str(path.relative_to(repo)))
            if path.is_file():
                files[path.relative_to(repo).as_posix()] = digest(path)
    for name in E10_MARKERS:
        files[name] = digest(repo / name)
    return {"source_sha": command(repo, "rev-parse", "HEAD").strip(),
            "source_status": command(repo, "status", "--porcelain", "--untracked-files=all"),
            "lab_sha256": digest(repo / "labs/e8e10/lab.py"),
            "test_sha256": digest(repo / "labs/e8e10/test_profile.py"),
            "protected_file_sha256": files}


def main():
    mode = sys.argv[1]
    repo = Path(sys.argv[2]).resolve()
    if mode == "check":
        check(repo)
        print("SOURCE_AND_EXISTING_E10_PREFLIGHT_PASSED=true")
        return
    meta = Path(sys.argv[3]).resolve()
    state = snapshot(repo)
    if mode == "before":
        save(meta / "protected-before.json", state)
        return
    if mode != "after":
        raise ValueError("UNKNOWN_MODE")
    save(meta / "protected-after.json", state)
    before = json.loads((meta / "protected-before.json").read_text(encoding="utf-8"))
    same = state == before
    save(meta / "protection-check.json", {"passed": same,
         "protected_file_count": len(state["protected_file_sha256"]),
         "source_and_e10_evidence_unchanged": same})
    if not same:
        raise ValueError("EXISTING_SOURCE_OR_E10_EVIDENCE_CHANGED; inspect before/after hashes")
    e8_out, e9_out = sys.argv[4:6]
    gates = []
    for name in (e8_out, e9_out):
        out = repo / name
        gate = json.loads((out / "checks.json").read_text(encoding="utf-8"))
        if gate.get("passed") is not True:
            raise ValueError("STAGE_CHECKS_NOT_PASSED " + name)
        gates.append(gate)
    save(meta / "summary.json", {"passed": True, "scope": "E8/E9 B reference steps",
         "source_sha": BASE, "e8_out": e8_out, "e9_out": e9_out,
         "e8": gates[0], "e9": gates[1], "e10_evidence_unchanged": True,
         "protected_file_count": len(state["protected_file_sha256"]),
         "personal_extension": "Existing E10 compile-failure test; no E8/E9 extension claimed by this run",
         "commit_push_pr_performed": False})


if __name__ == "__main__":
    main()
