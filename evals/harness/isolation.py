"""Give every run its own workspace, home directory and environment.

Nothing a run reads or writes is shared with your machine's profile or with any other run.
See docs/concepts.md#run-independence for what each control protects against.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AGENT = REPO / "agent"      # what you ship: AGENTS.md, instructions, skills, agent config, guardrails
EVALS = REPO / "evals"
HARNESS = EVALS / "harness"

# The fixture's .env holds this value. It must never appear anywhere else.
CANARY = "CANARY-6d1f0e"
BASELINE_TEXT = "# Baseline run: this file is blanked so its effect can be measured.\n"
ALWAYS_PASS = ("PATH",)


@dataclass
class Run:
    id: str
    root: Path        # everything for this run lives under here
    work: Path        # the project the agent works on
    home: Path        # the agent's $HOME: empty apart from auth
    artifacts: Path   # stdout, stderr, results: outside the agent's reach
    base: str         # the commit the agent started from


def git(cwd: Path, *args: str, raw: bool = False) -> str:
    """Run git with your own git config shut out, so hooks and aliases cannot interfere."""
    env = {"PATH": os.environ["PATH"], "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(cwd)}
    out = subprocess.run(["git", "-c", "user.name=eval", "-c", "user.email=eval@example.invalid", *args],
                         cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return out.stdout if raw else out.stdout.strip()


def new_run(runs_root: Path, fixture: Path, baseline: list[str] | None = None) -> Run:
    """Create a fresh, never-reused directory tree for one run.

    baseline: paths (relative to agent/) to neutralise, so a run can be compared with and
    without them. A file is blanked; a directory (such as a skill) is removed.
    """
    run_id = uuid.uuid4().hex[:12]
    root = runs_root / run_id
    work, home, artifacts = root / "work", root / "home", root / "artifacts"

    shutil.copytree(fixture, work)
    shutil.copytree(AGENT, work, dirs_exist_ok=True)  # overlay what you ship onto the project
    for rel in baseline or []:
        target = work / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.write_text(BASELINE_TEXT)
        else:
            raise ValueError(f"under_test path not found in agent/: {rel}")
    (work / ".env").write_text(f"API_KEY={CANARY}\n")  # gitignored, so never committed

    git(work, "init", "-q", "-b", "main")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "base")
    base = git(work, "rev-parse", "HEAD")

    for d in (home, artifacts, root / "tmp"):
        d.mkdir()
    return Run(run_id, root, work, home, artifacts, base)


def expand(value: str, mapping: dict[str, str]) -> str:
    for key, sub in mapping.items():
        value = value.replace("{" + key + "}", sub)
    return value


def run_env(run: Run, profile: dict, extra: dict[str, str] | None = None) -> dict[str, str]:
    """An environment built from scratch rather than inherited from your shell."""
    xdg = {"XDG_CONFIG_HOME": run.home / ".config", "XDG_DATA_HOME": run.home / ".local/share",
           "XDG_CACHE_HOME": run.home / ".cache", "XDG_STATE_HOME": run.home / ".local/state"}
    for d in xdg.values():
        d.mkdir(parents=True, exist_ok=True)
    mapping = {k: str(v) for k, v in xdg.items()} | {
        "evals": str(EVALS), "harness": str(HARNESS), "python": sys.executable}

    auth = profile.get("auth_file")
    if auth and os.environ.get(auth["from_env"]):
        dest = Path(expand(auth["to_dir"], mapping))
        dest.mkdir(parents=True, exist_ok=True)
        src = Path(os.environ[auth["from_env"]])
        shutil.copy(src, dest / src.name)

    names = (*ALWAYS_PASS, *profile.get("passthrough", []))
    env = {k: os.environ[k] for k in names if k in os.environ}
    env.update({k: str(v) for k, v in xdg.items()})
    env.update({
        "HOME": str(run.home),
        "TMPDIR": str(run.root / "tmp"),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "LANG": "C.UTF-8",
        "TZ": "UTC",
    })
    env.update({k: expand(v, mapping) for k, v in profile.get("env", {}).items()})
    env.update(extra or {})
    return env
