"""The command line, profiles, comparison report and skill lint."""
import json

import pytest

import compare
import lint_skills
import runner
from conftest import SCENARIO_FILES

ARGS = [str(p) for p in SCENARIO_FILES]


def test_kilo_profile_builds_the_documented_command(monkeypatch):
    monkeypatch.delenv("KILO_BIN", raising=False)
    cmd = runner.agent_command(runner.load_profile("kilo"), "command", "do it", "provider/model")
    assert cmd == ["kilo", "run", "--auto", "--format", "json", "-m", "provider/model", "do it"]


def test_kilo_profile_requires_a_pinned_model(tmp_path):
    with pytest.raises(SystemExit):
        runner.main([*ARGS, "--profile", "kilo", "--runs-root", str(tmp_path)])


def test_end_to_end_good_agent_meets_every_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "good")
    out = tmp_path / "report"
    code = runner.main([*ARGS, "--runs", "2", "--jobs", "4", "--runs-root", str(tmp_path / "runs"), "--out", str(out)])
    assert code == 0
    summary = (out / "summary.md").read_text()
    assert "FAIL" not in summary and "Harness errors" not in summary
    results = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
    assert len(results) == 7 * 2 + 3            # 7 evals x 2 runs, 3 guardrails once
    assert len({r["dir"] for r in results}) == len(results)   # never reused


def test_end_to_end_sloppy_agent_fails_the_report(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "sloppy")
    code = runner.main([*ARGS, "--runs", "1", "--runs-root", str(tmp_path / "runs"), "--out", str(tmp_path / "r")])
    assert code == 1


def test_seed_reproduces_run_order(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "good")
    orders = []
    for i in range(2):
        out = tmp_path / f"r{i}"
        runner.main([*ARGS, "--runs", "2", "--seed", "42", "--runs-root", str(tmp_path / f"runs{i}"), "--out", str(out)])
        orders.append([json.loads(line)["scenario"] for line in (out / "results.jsonl").read_text().splitlines()])
    assert orders[0] == orders[1]


def test_baseline_skips_guardrails_and_compare_reads_both(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_MODE", "good")
    on, off = tmp_path / "on", tmp_path / "off"
    runner.main([*ARGS, "--runs", "1", "--runs-root", str(tmp_path / "a"), "--out", str(on)])
    assert runner.main([*ARGS, "--runs", "1", "--baseline", "--runs-root", str(tmp_path / "b"), "--out", str(off)]) == 0
    kinds = {json.loads(line)["kind"] for line in (off / "results.jsonl").read_text().splitlines()}
    assert kinds == {"eval"}
    capsys.readouterr()
    compare.main(str(on), str(off))
    table = capsys.readouterr().out
    assert "WARNING" not in table and "| skill-execution | warns |" in table


def test_shipped_skills_pass_lint():
    errors, warnings = lint_skills.lint(runner.REPO / "agent" / ".agents" / "skills")
    assert errors == [] and warnings == []


def write_skill(root, folder, name, description="Does a thing. Use when asked to do the thing.", body=""):
    d = root / folder
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n{body}\n")


@pytest.mark.parametrize("name", ["Bad-Name", "-lead", "trail-", "double--hyphen", "x" * 65])
def test_lint_rejects_invalid_names(tmp_path, name):
    write_skill(tmp_path, name.lower().strip("-") or "x", name)
    errors, _ = lint_skills.lint(tmp_path)
    assert any("invalid name" in e for e in errors)


def test_lint_rejects_name_folder_mismatch_and_broken_references(tmp_path):
    write_skill(tmp_path, "folder-a", "other-name", body="See [guide](references/missing.md).")
    errors, _ = lint_skills.lint(tmp_path)
    assert any("must match its folder" in e for e in errors)
    assert any("broken reference" in e for e in errors)


def test_lint_warns_when_descriptions_compete(tmp_path):
    desc = "Deprecate a Python function so callers get a warning before removal."
    write_skill(tmp_path, "one", "one", desc)
    write_skill(tmp_path, "two", "two", desc + " Also for modules.")
    _, warnings = lint_skills.lint(tmp_path)
    assert any("compete" in w for w in warnings)
