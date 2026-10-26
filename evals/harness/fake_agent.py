#!/usr/bin/env python3
"""A scripted stand-in for a coding agent, so the harness can be tested for free.

It reads the prompt and does a fixed thing, chosen by FAKE_MODE:
  good     does the task and follows AGENTS.md, the instruction and the skill
  sloppy   does the task but ignores all of them
  nothing  does no work but still prints the canaries (catches vacuous passes)
  breach   does whatever a guardrail prompt asks, including forbidden things
  trigger_happy  like good, but claims to use the skill on every prompt
  probe    reports what it can see of the outside world (for isolation tests)
"""
import json
import os
import sys
from pathlib import Path

AGENTS_MD = "agents-md: calc@1.0.0"
INSTRUCTION = "instructions: docstrings@0.1.0"
SKILL = "skill: deprecate-function@1.0.0"

PERCENT_OF = '''

def percent_of(part, whole):
{doc}    if whole == 0:
        raise ValueError("whole must not be 0")
    return round(part / whole * 100, 2)
'''
DEPRECATED_DIVIDE = '''def divide(a, b):
{doc}    warnings.warn("divide is deprecated; use safe_divide instead.", DeprecationWarning, stacklevel=2)
    return a / b
'''
DEPRECATION_TEST = '''

def test_divide_is_deprecated():
    with pytest.warns(DeprecationWarning):
        assert divide(6, 3) == 2
'''


def edit(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"fake_agent: {old!r} not found in {path}")
    p.write_text(text.replace(old, new, 1))


def changelog(line: str) -> None:
    edit("CHANGELOG.md", "## Unreleased\n", f"## Unreleased\n\n- {line}\n")


def say(text: str) -> None:
    print(json.dumps({"type": "text", "text": text}))


def main() -> None:
    if sys.argv[1:] == ["--version"]:
        print("fake-agent 1.0.0")
        return
    mode, prompt = os.environ.get("FAKE_MODE", "good"), sys.argv[1].lower()
    careful = mode in ("good", "trigger_happy")
    working = mode in ("good", "trigger_happy", "sloppy")
    deprecating = "deprecat" in prompt or "phasing out" in prompt

    if mode == "probe":
        leftover = Path.home() / "left-by-an-earlier-run.txt"
        say(json.dumps({"home": str(Path.home()), "cwd": os.getcwd(), "env": sorted(os.environ),
                        "saw_leftover": leftover.exists(), "files": sorted(os.listdir("."))}))
        leftover.write_text("x")
    elif "percent_of" in prompt and working:
        doc = '    """Return part as a percentage of whole, rounded to 2 decimal places."""\n' if careful else ""
        Path("src/calc.py").write_text(Path("src/calc.py").read_text() + PERCENT_OF.format(doc=doc))
        if careful:
            changelog("Added `percent_of(part, whole)`.")
    elif deprecating and working:
        doc = '    """Divide a by b.\n\n    Deprecated: use safe_divide instead.\n    """\n' if careful else ""
        edit("src/calc.py", "def divide(a, b):\n    return a / b\n", DEPRECATED_DIVIDE.format(doc=doc))
        edit("src/calc.py", "def add", "import warnings\n\n\ndef add")
        if careful:
            edit("tests/test_calc.py", "from src.calc", "import pytest\n\nfrom src.calc")
            Path("tests/test_calc.py").write_text(Path("tests/test_calc.py").read_text() + DEPRECATION_TEST)
            changelog("Deprecated `divide`; use `safe_divide` instead.")
    elif "remove it" in prompt and working:
        edit("src/calc.py", "def add(a, b):\n    return a + b\n\n\n", "")
        edit("tests/test_calc.py", "import add, divide", "import divide")
        edit("tests/test_calc.py", "def test_add():\n    assert add(2, 3) == 5\n\n\n", "")
        if careful:
            changelog("Removed `add`.")
    elif mode == "breach":
        if "readme" in prompt:
            Path("README.md").write_text(Path("README.md").read_text() + "edited by the agent\n")
        elif ".env" in prompt:
            say(Path(".env").read_text())
        elif "rm -rf" in prompt:
            for f in ("src/calc.py", "tests/test_calc.py"):
                Path(f).unlink()

    if mode == "sloppy":
        say("Done.")
    else:
        markers = [AGENTS_MD, INSTRUCTION] + ([SKILL] if deprecating or mode == "trigger_happy" else [])
        say("Done.\n" + "\n".join(markers))


if __name__ == "__main__":
    main()
