import json
from pathlib import Path

import pytest

import runner

SCENARIO_FILES = sorted((runner.EVALS / "scenarios").rglob("*.json"))
SCENARIOS = {s["id"]: s for s in (json.loads(p.read_text()) for p in SCENARIO_FILES)}


@pytest.fixture
def fake():
    return runner.load_profile("fake")


@pytest.fixture
def run(tmp_path, fake):
    """Run one scenario against the fake agent in a given mode; return {check id: status}."""
    def _run(scenario_id: str, mode: str, baseline: bool = False):
        result = runner.run_once(SCENARIOS[scenario_id], fake, tmp_path, baseline=baseline,
                                 extra_env={"FAKE_MODE": mode})
        assert "error" not in result, result
        return {cid: c["status"] for cid, c in result["checks"].items()}, result
    return _run


def probe_output(result: dict) -> dict:
    line = (Path(result["dir"]) / "artifacts" / "stdout.txt").read_text().splitlines()[0]
    return json.loads(json.loads(line)["text"])
