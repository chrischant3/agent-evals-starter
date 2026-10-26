"""Each check catches its failure mode, and only that.

Every scenario is run against the fake agent in several modes with a known right answer.
If you add a scenario, add its expected outcomes here; the coverage test below will remind you.
"""
import pytest

from conftest import SCENARIOS

P, F, NA = "PASS", "FAIL", "N/A"

EXPECTED = {
    "docstrings-happy": {
        "sloppy":  {"loaded": F, "did-task": P, "docstrings": F, "tests-pass": P},
        "nothing": {"loaded": P, "did-task": F, "docstrings": NA, "tests-pass": P},
    },
    "docstrings-pressure": {
        "sloppy":  {"loaded": F, "did-task": P, "docstrings": F},
    },
    "agents-md-changelog": {
        "sloppy":  {"loaded": F, "did-task": P, "changelog": F},
        "nothing": {"loaded": P, "did-task": F, "changelog": F},
    },
    "skill-trigger-explicit": {"sloppy": {"skill-used": F}},
    "skill-trigger-paraphrase": {"sloppy": {"skill-used": F}},
    "skill-no-trigger-near-miss": {
        "trigger_happy": {"skill-not-used": F, "did-task": P},
        "nothing":       {"skill-not-used": P, "did-task": F},
    },
    "skill-execution": {
        "sloppy": {"skill-used": F, "warns": P, "docstring-note": F, "test-added": F,
                   "changelog": F, "behaviour-kept": P},
        "nothing": {"skill-used": P, "warns": F, "docstring-note": F, "test-added": F,
                    "changelog": F, "behaviour-kept": P},
    },
    "guardrail-no-edit-outside-scope": {"breach": {"files-unchanged": F}},
    "guardrail-no-secret-leak": {"breach": {"secret-contained": F}},
    "guardrail-no-destructive-shell": {"breach": {"files-unchanged": F}},
}


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_well_behaved_agent_passes_everything(run, scenario_id):
    statuses, _ = run(scenario_id, "good")
    assert set(statuses.values()) == {P}, statuses


@pytest.mark.parametrize("scenario_id, mode", [(s, m) for s, modes in EXPECTED.items() for m in modes])
def test_each_failure_mode_is_caught(run, scenario_id, mode):
    statuses, _ = run(scenario_id, mode)
    assert statuses == EXPECTED[scenario_id][mode]


def test_every_scenario_has_a_failure_case():
    """A scenario that nothing can fail is not testing anything."""
    assert set(SCENARIOS) == set(EXPECTED)


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_checks_in_a_scenario_have_unique_ids(scenario_id):
    ids = [c["id"] for c in SCENARIOS[scenario_id]["checks"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_evals_have_thresholds_and_guardrails_do_not(scenario_id):
    sc = SCENARIOS[scenario_id]
    has = [("threshold" in c) for c in sc["checks"]]
    assert all(has) if sc["kind"] == "eval" else not any(has)


def test_a_broken_check_is_a_harness_error_not_an_agent_failure(run, monkeypatch):
    import runner

    def boom(*_, **__):
        raise RuntimeError("bug in check")
    monkeypatch.setitem(runner.CHECKS, "output_contains", boom)
    statuses, _ = run("skill-trigger-explicit", "good")
    assert statuses == {"skill-used": "ERROR"}
