"""Inspect baseline evidence or preserve the actual member-3 negative case."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = "fb968b7e0d2b406905003d3956b3e177bea8e416"
TEST_SHA256 = "680b975276aaae9eff7700347f54e413036f01c54ce0b61e1944cbcded8875f5"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_baseline(root):
    assert (root / "student-source-commit.txt").read_text().strip() == BASE
    gate = read_json(root / "gate.json")
    assert gate == {"track": "B", "passed": True, "rows": 3}
    rejected = read_json(root / "reject-test/validation.json")
    accepted = read_json(root / "accept/validation.json")
    broken = read_json(root / "reject-patch/validation.json")
    for report in (rejected, broken):
        assert not report["accepted"] and report["rollback"] and report["source_unchanged"]
    assert rejected["checks"]["test"] is False
    assert rejected["error"] is None
    assert broken["error"] and not broken["checks"].get("patch_applies", False)
    required = ("patch_applies", "build", "test", "header_change", "no_missing")
    assert accepted["accepted"] and all(accepted["checks"].get(k) is True for k in required)
    assert accepted["error"] is None
    assert not accepted["rollback"] and not accepted["source_unchanged"]
    before = (root / "source-before.Makefile").read_bytes()
    after = (root / "source-after-accept.Makefile").read_bytes()
    assert before != after == (root / "project/Makefile").read_bytes()
    dynamic = read_json(root / "recheck-buildchecker/findings.json")
    assert dynamic["status"] == "SUCCEEDED"
    assert not any(f["type"] == "MISSING" for f in dynamic["findings"])
    print("BASELINE_EVIDENCE_REVIEW_PASSED=true", flush=True)


def record_case(out):
    from lab import save
    import test_profile

    assert out.resolve().parent == Path("/course/work")
    assert out.name.startswith("e10-B-member3.")
    assert (out / "source-base-commit.txt").read_text().strip() == BASE
    assert hashlib.sha256(Path(test_profile.__file__).read_bytes()).hexdigest() == TEST_SHA256
    for filename, count in (("targeted-tests.log", 1), ("full-suite.log", 22)):
        text = (out / filename).read_text()
        matches = re.findall(r"Ran (\d+) tests? in", text)
        assert matches and int(matches[-1]) == count, filename
        assert "OK" in text.splitlines(), filename
    assert (out / "targeted-tests.exit").read_text().strip() == "0"
    assert (out / "full-suite.exit").read_text().strip() == "0"

    root = out / "compile-failure"
    assert not root.exists(), "Preserve any existing case instead of overwriting it."
    save(out / "compile-failure-expected.json", {
        "candidate": "Valid unified diff with config.h and an invalid compiler flag",
        "patch_applies": True, "build_succeeded": False,
        "accepted": False, "rollback": True, "source_unchanged": True,
        "required_error_marker": "-fmember3-reject-probe",
    })
    case = test_profile.Student241880546E10Tests(
        "test_compile_failure_rejected_without_source_changes")
    result = case.check_compile_failure(root)
    project = root / "project"
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=project).split(b"\0")
    comparisons = {}
    for raw in paths:
        if not raw:
            continue
        name = raw.decode("utf-8")
        before = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=project)
        after = (project / name).read_bytes()
        assert before == after, name
        comparisons[name] = {
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "identical": True,
        }
    assert (root / "source-before.Makefile").read_bytes() == (root / "source-after.Makefile").read_bytes()
    save(root / "source-comparison.json", comparisons)
    fixture_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=project, text=True).strip()
    (root / "fixture-commit.txt").write_text(fixture_commit + "\n")
    save(out / "personal-test-gate.json", {
        "passed": True, "targeted_tests": 1, "full_suite_tests": 22,
        "scenario": "applicable-candidate-compilation-failure",
        "source_base_commit": BASE, "test_file_sha256": TEST_SHA256,
        "test_patch_committed": False, "fixture_commit": fixture_commit,
    })
    print("PERSONAL_TESTS_PASSED=true", flush=True)
    print("TARGETED_TESTS=1\nFULL_SUITE_TESTS=22", flush=True)
    print("VALIDATION=" + json.dumps(result), flush=True)
    print("SOURCE_BASE_COMMIT=" + BASE, flush=True)
    print("TEST_FILE_SHA256=" + TEST_SHA256, flush=True)
    print("TEST_PATCH_COMMITTED=false", flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--check-baseline":
        inspect_baseline(Path(sys.argv[2]))
    elif len(sys.argv) == 2:
        record_case(Path(sys.argv[1]))
    else:
        raise SystemExit("Use --check-baseline PATH or provide a personal OUT.")
