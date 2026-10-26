"""Every run is independent of every other run and of the machine it runs on."""
import subprocess
from pathlib import Path

import pytest

import isolation
import runner
from conftest import probe_output

FIXTURE = runner.EVALS / "fixtures" / "calc"


def probe(run):
    _, result = run("docstrings-happy", "probe")
    return result, probe_output(result)


def test_runs_never_share_directories(run):
    (a, pa), (b, pb) = probe(run), probe(run)
    assert a["run_id"] != b["run_id"]
    assert pa["home"] != pb["home"] and pa["cwd"] != pb["cwd"]
    assert Path(pa["home"]).is_relative_to(a["dir"])


def test_nothing_survives_from_an_earlier_run(run):
    _, first = probe(run)   # leaves a file in its own $HOME
    _, second = probe(run)
    assert not first["saw_leftover"] and not second["saw_leftover"]


def test_your_environment_does_not_leak_in(run, monkeypatch):
    monkeypatch.setenv("HOST_ONLY_SECRET", "nope")
    _, seen = probe(run)
    assert "HOST_ONLY_SECRET" not in seen["env"]


def test_profile_env_is_applied(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    env = isolation.run_env(r, runner.load_profile("kilo"))
    assert env["KILO_CONFIG"] == str(runner.EVALS / "kilo.eval.jsonc")
    assert env["HOME"] == str(r.home) and env["XDG_CONFIG_HOME"].startswith(str(r.home))


def test_what_you_ship_is_overlaid_onto_every_run(run):
    _, seen = probe(run)
    for name in ("AGENTS.md", "kilo.jsonc", ".kilocodeignore", "instructions", ".agents", ".env"):
        assert name in seen["files"]


def test_workspace_is_its_own_git_repo_outside_this_one(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=r.work,
                         capture_output=True, text=True).stdout.strip()
    assert Path(top).resolve() == r.work.resolve()
    assert not r.root.resolve().is_relative_to(isolation.REPO)


def test_evidence_lives_outside_the_agents_workspace(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    assert not r.artifacts.is_relative_to(r.work)


def test_secret_exists_but_is_never_committed(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    assert (r.work / ".env").exists()
    assert ".env" not in isolation.git(r.work, "ls-files").splitlines()


def test_baseline_blanks_a_file_and_touches_nothing_else(tmp_path):
    on = isolation.new_run(tmp_path, FIXTURE)
    off = isolation.new_run(tmp_path, FIXTURE, baseline=["AGENTS.md"])
    assert (off.work / "AGENTS.md").read_text() == isolation.BASELINE_TEXT
    for name in ("kilo.jsonc", "instructions/docstrings.md", ".agents/skills/deprecate-function/SKILL.md"):
        assert (on.work / name).read_text() == (off.work / name).read_text()


def test_baseline_removes_a_skill_directory(tmp_path):
    off = isolation.new_run(tmp_path, FIXTURE, baseline=[".agents/skills/deprecate-function"])
    assert not (off.work / ".agents/skills/deprecate-function").exists()


def test_baseline_rejects_a_path_that_does_not_exist(tmp_path):
    with pytest.raises(ValueError):
        isolation.new_run(tmp_path, FIXTURE, baseline=["no-such-file.md"])


def test_every_under_test_path_exists():
    from conftest import SCENARIOS
    for sc in SCENARIOS.values():
        for rel in sc.get("under_test", []):
            assert (isolation.AGENT / rel).exists(), f"{sc['id']}: {rel}"


def test_auth_file_is_copied_into_the_runs_own_home_only(tmp_path, monkeypatch):
    secret = tmp_path / "auth.json"
    secret.write_text("{}")
    monkeypatch.setenv("KILO_EVAL_AUTH_FILE", str(secret))
    r = isolation.new_run(tmp_path / "runs", FIXTURE)
    env = isolation.run_env(r, runner.load_profile("kilo"))
    copied = Path(env["XDG_DATA_HOME"]) / "kilo" / "auth.json"
    assert copied.exists() and copied.is_relative_to(r.home)
    assert "KILO_EVAL_AUTH_FILE" not in env
