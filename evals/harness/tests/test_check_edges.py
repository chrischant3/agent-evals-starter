"""Edge cases the scenario matrix cannot reach."""
import shutil

import checks
import isolation
import runner

FIXTURE = runner.EVALS / "fixtures" / "calc"


def test_changelog_ignores_lines_that_were_already_there(tmp_path):
    fixture = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture)
    log = fixture / "CHANGELOG.md"
    log.write_text(log.read_text().replace("## Unreleased\n", "## Unreleased\n\n- Tidied `divide`.\n"))
    r = isolation.new_run(tmp_path / "runs", fixture)
    status, _ = checks.changelog_mentions(r, "", "CHANGELOG.md", "Unreleased", "divide")
    assert status == "FAIL"


def test_changelog_only_counts_the_named_section(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    log = r.work / "CHANGELOG.md"
    log.write_text(log.read_text() + "\n- Later note about `divide`.\n")   # lands under 1.0.0
    assert checks.changelog_mentions(r, "", "CHANGELOG.md", "Unreleased", "divide")[0] == "FAIL"


def test_tests_pass_fails_when_behaviour_breaks(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    calc = r.work / "src" / "calc.py"
    calc.write_text(calc.read_text().replace("return a / b", "return a * b"))
    assert checks.tests_pass(r, "")[0] == "FAIL"


def test_docstrings_judges_a_changed_existing_function(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    calc = r.work / "src" / "calc.py"
    calc.write_text(calc.read_text().replace("return a / b", "return a / b if b else None"))
    assert checks.docstrings(r, "", under="src/")[0] == "FAIL"


def test_unparseable_code_fails_rather_than_crashing(tmp_path):
    r = isolation.new_run(tmp_path, FIXTURE)
    (r.work / "src" / "calc.py").write_text("def broken(:\n")
    assert checks.function_defined(r, "", "src/calc.py", "add")[0] == "FAIL"
    assert checks.docstrings(r, "", under="src/")[0] == "FAIL"
