"""Execute the B E8/E9 manual reference steps and save their actual evidence."""
import json
import hashlib
import shutil
import sys
from pathlib import Path

SOURCE_FILES = (".gitignore", "Makefile", "main.c", "helper.c", "config.h", "extra.h", "unused.h")
EXPECTED_FINDINGS = {
    ("MISSING", "main.o", "config.h"),
    ("REDUNDANT", "main.o", "unused.h"),
}
EXPECTED_EDIT = {"target": "main.o", "dependency": "config.h"}
STYLES = ("direct", "macro", "mixed")


def source_hashes(project):
    return {name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_report(report, project, run):
    assert report["commit"] == run(["git", "rev-parse", "HEAD"], project).strip(), "REPORT_COMMIT_MISMATCH"
    assert {(f["type"], f["target"], f["dependency"]) for f in report["findings"]} == EXPECTED_FINDINGS


def expected_makefile(before, style):
    old, new = {
        "direct": (b"main.o: main.c unused.h\n", b"main.o: main.c unused.h config.h\n"),
        "macro": (b"DEPS = main.c unused.h\n", b"DEPS = main.c unused.h config.h\n"),
        "mixed": (b"main.o: main.c $(HEADERS)\n", b"main.o: main.c $(HEADERS) config.h\n"),
    }[style]
    assert before.count(old) == 1
    return before.replace(old, new, 1)


def e8(out, action):
    from lab import fixture, scan, patch, save, run
    project = out / "project"
    if action == "create":
        save(out / "expected-results.json", {
            "findings": sorted(EXPECTED_FINDINGS),
            "patch_plan": [dict(EXPECTED_EDIT, style="direct")],
            "old_report_error": "STALE_REPORT",
            "source_bytes_unchanged": True,
            "scope": "E8 B reference steps 1-8; personal extension is not claimed here",
        })
        fixture(project)
        (out / "source-before.Makefile").write_bytes((project / "Makefile").read_bytes())
        save(out / "source-before.json", source_hashes(project))
        write_new(out / "fixture-commit.txt", run(["git", "rev-parse", "HEAD"], project))
        print("CREATED", project)
    elif action == "inspect":
        print("OUT", out)
        for name in ("Makefile", "main.c", "config.h", "helper.c"):
            print("INPUT", name, "\n" + (project / name).read_text())
        print("FIXTURE_COMMIT", (out / "fixture-commit.txt").read_text().strip())
        print("EXPECTED MISSING main.o/config.h; REDUNDANT main.o/unused.h; program output 1")
    elif action == "scan":
        report = scan(project)
        save(out / "fixed-md-report.json", report)
        print("REPORT_COMMIT", report["commit"])
        print("FINDINGS", report["findings"])
    elif action == "identity":
        report = load(out / "fixed-md-report.json")
        assert_report(report, project, run)
        print("COMMIT_MATCH", report["commit"])
        print("PRECISE_MD_RD_PASS")
    elif action == "patch":
        report = load(out / "fixed-md-report.json")
        assert_report(report, project, run)
        diff, edits = patch(project, report)
        assert edits == [dict(EXPECTED_EDIT, style="direct")]
        assert "+main.o: main.c unused.h config.h" in diff
        assert source_hashes(project) == load(out / "source-before.json")
        write_new(out / "candidate.patch", diff)
        save(out / "patch-plan.json", edits)
        print(diff)
        print("PATCH_GENERATED_SOURCE_UNCHANGED", edits)
    elif action == "apply-check":
        output = run(["git", "apply", "--check", str((out / "candidate.patch").resolve())], project)
        assert run(["git", "status", "--porcelain"], project).strip() == ""
        assert source_hashes(project) == load(out / "source-before.json")
        write_new(out / "apply-check.log", output + "APPLY_CHECK_PASS_SOURCE_CLEAN\n")
        print("APPLY_CHECK_PASS_SOURCE_CLEAN")
    elif action == "stale":
        report = load(out / "fixed-md-report.json")
        report["commit"] = "0" * 40
        save(out / "stale-report.json", report)
        try:
            patch(project, report)
        except ValueError as error:
            assert str(error) == "STALE_REPORT", str(error)
            save(out / "expected-failure.json", {"error": str(error)})
            print("EXPECTED_REJECTION", error)
        else:
            raise AssertionError("STALE_REPORT_NOT_REJECTED")
        assert source_hashes(project) == load(out / "source-before.json")
        print("SOURCE_BYTES_UNCHANGED")
    elif action == "conclude":
        report = load(out / "fixed-md-report.json")
        assert_report(report, project, run)
        assert load(out / "patch-plan.json") == [dict(EXPECTED_EDIT, style="direct")]
        assert load(out / "expected-failure.json") == {"error": "STALE_REPORT"}
        before = load(out / "source-before.json")
        after = source_hashes(project)
        assert before == after
        assert run(["git", "status", "--porcelain"], project).strip() == ""
        (out / "source-after.Makefile").write_bytes((project / "Makefile").read_bytes())
        save(out / "source-comparison.json", {"before": before, "after": after, "all_unchanged": True})
        write_new(out / "结论.txt", "B E8：候选仅增加config.h；保留RD和配方；旧报告拒绝；源文件原字节保持。候选生成不代替E10质量验证。\n")
        save(out / "checks.json", {"stage": "E8", "track": "B", "passed": True,
             "commit_match": True, "exact_md_rd": True, "plan_style": "direct",
             "apply_check": True, "stale_report_rejected": True,
             "source_files_unchanged": len(before), "fixture_commit": report["commit"]})
        print("E8_BASELINE_PASSED=true")
    else:
        raise ValueError("UNKNOWN_E8_ACTION " + action)


def e9(out, action):
    from lab import fixture, scan, patch, save, run
    if action in STYLES:
        style = action
        if style == "direct":
            save(out / "expected-results.json", {
                "direct": "add config.h to main.o prerequisite line",
                "macro": "add config.h to DEPS definition; preserve target variable reference",
                "mixed": "add config.h to main.o prerequisite line; preserve HEADERS reference",
                "source_bytes_unchanged": True,
                "apply_demo": "apply macro.patch only to an extra copy",
                "scope": "E9 B reference steps 1-6; personal extension is not claimed here",
            })
        project = out / style
        fixture(project, style)
        before = (project / "Makefile").read_bytes()
        before_hashes = source_hashes(project)
        (out / (style + "-source-before.Makefile")).write_bytes(before)
        save(out / (style + "-source-before.json"), before_hashes)
        write_new(out / (style + "-fixture-commit.txt"), run(["git", "rev-parse", "HEAD"], project))
        report = scan(project)
        save(out / (style + "-input.json"), report)
        assert_report(report, project, run)
        diff, edits = patch(project, report)
        assert edits == [dict(EXPECTED_EDIT, style=style)]
        expected = expected_makefile(before, style)
        added = [line[1:] for line in diff.splitlines(keepends=True) if line.startswith("+") and not line.startswith("+++")]
        assert len(added) == 1
        assert added[0].encode() in expected
        assert source_hashes(project) == before_hashes
        patch_path = out / (style + ".patch")
        write_new(patch_path, diff)
        save(out / (style + "-plan.json"), edits)
        result = run(["git", "apply", "--check", str(patch_path.resolve())], project)
        assert run(["git", "status", "--porcelain"], project).strip() == ""
        write_new(out / (style + "-apply-check.log"), result + "APPLY_CHECK_PASS_SOURCE_CLEAN\n")
        print("INPUT MAKEFILE\n" + before.decode())
        print("PATCH\n" + diff)
        print("PLAN", edits)
        print("STYLE_PASS", style)
    elif action == "compare":
        comparison = {}
        for style in STYLES:
            project = out / style
            before = load(out / (style + "-source-before.json"))
            after = source_hashes(project)
            assert before == after
            assert run(["git", "status", "--porcelain"], project).strip() == ""
            assert load(out / (style + "-plan.json")) == [dict(EXPECTED_EDIT, style=style)]
            (out / (style + "-source-after.Makefile")).write_bytes((project / "Makefile").read_bytes())
            comparison[style] = {"before": before, "after": after, "all_unchanged": True}
            print("STYLE", style, "\n" + (out / (style + ".patch")).read_text())
            print("PLAN", load(out / (style + "-plan.json")))
        save(out / "source-comparison.json", comparison)
        print("ALL_THREE_SOURCE_PROJECTS_CLEAN")
    elif action == "apply-demo":
        source = out / "macro"
        dest = out / "apply-demo"
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git"))
        run(["git", "init", "-b", "main"], dest)
        patch_path = str((out / "macro.patch").resolve())
        log = run(["git", "apply", "--check", patch_path], dest)
        log += run(["git", "apply", patch_path], dest)
        expected = expected_makefile((source / "Makefile").read_bytes(), "macro")
        assert (dest / "Makefile").read_bytes() == expected
        assert "main.o: $(DEPS)\n" in (dest / "Makefile").read_text()
        assert source_hashes(source) == load(out / "macro-source-before.json")
        write_new(out / "apply-demo.log", log + "APPLY_TO_COPY_PASS\n")
        print((dest / "Makefile").read_text())
        print("APPLY_TO_COPY_PASS")
    elif action == "conclude":
        commits = {}
        for style in STYLES:
            project = out / style
            report = load(out / (style + "-input.json"))
            assert_report(report, project, run)
            assert source_hashes(project) == load(out / (style + "-source-before.json"))
            assert run(["git", "status", "--porcelain"], project).strip() == ""
            commits[style] = report["commit"]
        assert (out / "apply-demo/Makefile").read_bytes() == expected_makefile((out / "macro/Makefile").read_bytes(), "macro")
        write_new(out / "结论.txt", "direct修改目标行；macro修改DEPS定义；mixed保留宏引用并修改目标行。三个原项目保持不变。共享变量的跨目标影响需要额外分析；本次基础运行不声明完成该扩展。\n")
        save(out / "checks.json", {"stage": "E9", "track": "B", "passed": True,
             "styles": list(STYLES), "commit_match_all": True, "apply_check_all": True,
             "source_projects_unchanged": True, "apply_demo_passed": True,
             "fixture_commits": commits})
        print("E9_BASELINE_PASSED=true")
    else:
        raise ValueError("UNKNOWN_E9_ACTION " + action)


def main():
    out = Path(sys.argv[1]).resolve()
    stage, action = sys.argv[2:4]
    if not out.is_dir():
        raise ValueError("OUT_MISSING")
    if (out / "student-source-commit.txt").read_text().strip() != "fb968b7e0d2b406905003d3956b3e177bea8e416":
        raise ValueError("OUT_SOURCE_MISMATCH")
    try:
        {"e8": e8, "e9": e9}[stage](out, action)
    except Exception as error:
        from lab import save
        save(out / "runner-failure.json", {"stage": stage, "action": action,
              "error_type": type(error).__name__, "error": str(error)})
        raise


if __name__ == "__main__":
    main()
