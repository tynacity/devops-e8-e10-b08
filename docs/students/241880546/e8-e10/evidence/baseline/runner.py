"""Run the E10 B reference matrix in the student's existing, fresh OUT."""
import csv
import json
import sys
from pathlib import Path

EXPECTED_SOURCE = "fb968b7e0d2b406905003d3956b3e177bea8e416"
EXPECTED_OUT = Path("/course/work/e10-B-manual.1jq7NB")
OUTPUT_NAMES = (
    "project", "fixed-md-report.json", "candidate.patch", "patch-plan.json",
    "source-before.Makefile", "source-after-accept.Makefile", "broken.patch",
    "reject-test", "accept", "reject-patch", "recheck-buildchecker",
    "expected-results.json", "results.csv", "gate.json", "baseline-failure.json",
    "accepted-source.diff", "结论.txt",
)


def validate_out(out, expected_out=EXPECTED_OUT, expected_source=EXPECTED_SOURCE):
    out = Path(out).resolve()
    if out != Path(expected_out).resolve() or not out.is_dir():
        raise ValueError("Unexpected evidence directory; nothing was written.")
    if (out / "student-source-commit.txt").read_text().strip() != expected_source:
        raise ValueError("OUT belongs to another source commit; preserve it.")
    for name in OUTPUT_NAMES:
        candidate = out / name
        if candidate.exists() or candidate.is_symlink():
            raise FileExistsError("Existing experiment artifact preserved: " + name)
    return out


def run_baseline(out):
    out = validate_out(out)
    from lab import fixture, scan, patch, validate, buildchecker, save, run

    stage = "inputs"
    try:
        save(out / "expected-results.json", {
            "test-rejection": {
                "accepted": False, "test": False, "rollback": True,
                "source_unchanged": True,
            },
            "accepted": {
                "accepted": True,
                "required_checks": ["patch_applies", "build", "test", "header_change", "no_missing"],
                "rollback": False, "source_unchanged": False,
            },
            "patch-rejection": {
                "accepted": False, "patch_applies": False,
                "rollback": True, "source_unchanged": True,
            },
        })
        project = out / "project"
        fixture(project)
        original_makefile = (project / "Makefile").read_bytes()
        original_header = (project / "config.h").read_bytes()
        (out / "source-before.Makefile").write_bytes(original_makefile)
        report = scan(project)
        assert report["commit"] == run(["git", "rev-parse", "HEAD"], project).strip()
        findings = {(f["type"], f["target"], f["dependency"]) for f in report["findings"]}
        assert findings == {
            ("MISSING", "main.o", "config.h"),
            ("REDUNDANT", "main.o", "unused.h"),
        }
        save(out / "fixed-md-report.json", report)
        diff, plan = patch(project, report)
        assert "+main.o: main.c unused.h config.h" in diff
        assert plan == [{"target": "main.o", "dependency": "config.h", "style": "direct"}]
        assert (project / "Makefile").read_bytes() == original_makefile
        candidate = out / "candidate.patch"
        candidate.write_text(diff, encoding="utf-8")
        save(out / "patch-plan.json", plan)
        print("INPUTS_AND_CANDIDATE_READY", flush=True)
        print(diff, flush=True)

        stage = "test-rejection"
        rejected = validate(project, candidate, out / "reject-test", fail_test=True)
        assert rejected["accepted"] is False
        assert rejected["checks"]["test"] is False
        assert all(rejected["checks"].get(k) is True for k in
                   ("patch_applies", "build", "header_change", "no_missing"))
        assert rejected["error"] is None
        assert rejected["rollback"] is True and rejected["source_unchanged"] is True
        assert (project / "Makefile").read_bytes() == original_makefile
        print("TEST_REJECTION_PASS", json.dumps(rejected), flush=True)

        stage = "accepted"
        accepted = validate(project, candidate, out / "accept")
        required = ("patch_applies", "build", "test", "header_change", "no_missing")
        assert accepted["accepted"] is True
        assert all(accepted["checks"].get(k) is True for k in required)
        assert accepted["error"] is None
        assert accepted["rollback"] is False and accepted["source_unchanged"] is False
        accepted_makefile = (project / "Makefile").read_bytes()
        assert accepted_makefile != original_makefile
        assert b"main.o: main.c unused.h config.h" in accepted_makefile
        assert (project / "config.h").read_bytes() == original_header
        assert (out / "accept/sandbox/config.h").read_text().strip() == "#define VALUE 2"
        incremental = (out / "accept/incremental.log").read_text()
        assert "-c main.c -o main.o" in incremental
        assert "main.o helper.o -o app" in incremental
        (out / "source-after-accept.Makefile").write_bytes(accepted_makefile)
        (out / "accepted-source.diff").write_text(
            run(["git", "diff", "--", "Makefile"], project), encoding="utf-8")
        print("ACCEPTANCE_PASS", json.dumps(accepted), flush=True)

        stage = "patch-rejection"
        broken = out / "broken.patch"
        broken.write_text("invalid patch\n", encoding="utf-8")
        patch_rejected = validate(project, broken, out / "reject-patch")
        assert patch_rejected["accepted"] is False
        assert not patch_rejected["checks"].get("patch_applies", False)
        assert patch_rejected["error"]
        assert patch_rejected["rollback"] is True
        assert patch_rejected["source_unchanged"] is True
        assert (project / "Makefile").read_bytes() == accepted_makefile
        print("PATCH_REJECTION_PASS", json.dumps(patch_rejected), flush=True)

        stage = "dynamic-recheck"
        dynamic = buildchecker(project, out / "recheck-buildchecker")
        assert dynamic["status"] == "SUCCEEDED"
        assert not any(f["type"] == "MISSING" for f in dynamic["findings"])
        assert (project / "Makefile").read_bytes() == accepted_makefile
        assert (project / "config.h").read_bytes() == original_header
        status = run(["git", "status", "--porcelain"], project).splitlines()
        assert status == [" M Makefile"], status
        print("DYNAMIC_RECHECK_PASS", flush=True)

        stage = "summary"
        rows = []
        for case, folder in (
            ("test-rejection", "reject-test"),
            ("accepted", "accept"),
            ("patch-rejection", "reject-patch"),
        ):
            actual = json.loads((out / folder / "validation.json").read_text())
            if case == "accepted":
                passed = actual["accepted"] and all(
                    actual["checks"].get(k) is True for k in required)
            else:
                passed = (not actual["accepted"] and actual["rollback"]
                          and actual["source_unchanged"])
            assert passed, case
            rows.append({"case": case, "passed": bool(passed)})
        with (out / "results.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["case", "passed"])
            writer.writeheader()
            writer.writerows(rows)
        (out / "结论.txt").write_text(
            "B E10 基础验证：错误测试拒绝、正常候选接受、坏Patch拒绝均符合预期；"
            "拒绝保持源Makefile字节；头文件变化触发重编译，真实动态重检无MISSING。"
            "本次仅运行参考基础矩阵，个人新增拒绝测试尚未执行。\n", encoding="utf-8")
        save(out / "gate.json", {"track": "B", "passed": True, "rows": len(rows)})
        print("E10_BASELINE_PASSED=true", flush=True)
        print("GATE=" + json.dumps({"track": "B", "passed": True, "rows": 3}), flush=True)
        print("OUT=" + str(out), flush=True)
        print("FIXTURE_COMMIT=" + report["commit"], flush=True)
    except Exception as error:
        save(out / "baseline-failure.json", {"stage": stage, "error": repr(error)})
        raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected exactly one OUT argument.")
    run_baseline(Path(sys.argv[1]))
