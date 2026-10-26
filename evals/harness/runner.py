#!/usr/bin/env python3
"""Run eval and guardrail scenarios against an agent, each run in its own isolated environment.

Examples:
  python evals/harness/runner.py evals/scenarios/*/*.json --profile fake
  python evals/harness/runner.py evals/scenarios/*/*.json --profile kilo --model <provider/model> --runs 20
  python evals/harness/runner.py evals/scenarios/*/*.json --profile kilo --model <provider/model> --baseline
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from checks import CHECKS  # noqa: E402
from isolation import AGENT, EVALS, HARNESS, REPO, expand, new_run, run_env  # noqa: E402

META_KEYS = {"id", "check", "threshold"}


def load_profile(name: str) -> dict:
    profile = json.loads((EVALS / "profiles" / f"{name}.json").read_text())
    base = {"python": sys.executable, "harness": str(HARNESS), "evals": str(EVALS)}
    profile["bin"] = expand(os.environ.get(profile["bin_env"]) or profile["default_bin"], base)
    return profile


def agent_command(profile: dict, key: str, prompt: str = "", model: str = "") -> list[str]:
    mapping = {"bin": profile["bin"], "python": sys.executable, "harness": str(HARNESS),
               "evals": str(EVALS), "model": model or "", "prompt": prompt}
    return [expand(part, mapping) for part in profile[key]]


def run_once(scenario: dict, profile: dict, runs_root: Path, model: str = "",
             baseline: bool = False, timeout: int = 900, extra_env: dict | None = None) -> dict:
    """One completely fresh run: new workspace, new home, new environment. Never resumes a session."""
    under_test = scenario.get("under_test", []) if baseline else []
    run = new_run(runs_root, EVALS / "fixtures" / scenario["fixture"], under_test)
    result = {"scenario": scenario["id"], "kind": scenario["kind"], "run_id": run.id,
              "dir": str(run.root), "baseline": baseline}
    started = time.time()
    try:
        proc = subprocess.run(agent_command(profile, "command", scenario["prompt"], model),
                              cwd=run.work, env=run_env(run, profile, extra_env),
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        result.update(error="timeout", seconds=timeout)
        return result
    except OSError as e:
        result.update(error=f"could not start agent: {e}")
        return result
    output = proc.stdout + proc.stderr
    (run.artifacts / "stdout.txt").write_text(proc.stdout)
    (run.artifacts / "stderr.txt").write_text(proc.stderr)
    result.update(exit=proc.returncode, seconds=round(time.time() - started, 1), checks={})
    for spec in scenario["checks"]:
        params = {k: v for k, v in spec.items() if k not in META_KEYS}
        try:
            status, detail = CHECKS[spec["check"]](run, output, **params)
        except Exception as e:  # a broken check is a harness bug, not an agent failure
            status, detail = "ERROR", f"{type(e).__name__}: {e}"
        result["checks"][spec["id"]] = {"status": status, "detail": detail}
    (run.artifacts / "result.json").write_text(json.dumps(result, indent=2))
    return result


def _tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    files = [path] if path.is_file() else sorted(
        f for f in path.rglob("*") if f.is_file() and "__pycache__" not in f.parts)
    for f in files:
        h.update(str(f.relative_to(REPO)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def fingerprint(profile: dict, model: str, seed: int, baseline: bool, runs: int) -> dict:
    """Everything that could change a result, so two reports can be compared honestly."""
    try:
        version = subprocess.run(agent_command(profile, "version_command"),
                                 capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        version = f"unknown ({e})"
    tracked = [AGENT, EVALS / "kilo.eval.jsonc", EVALS / "profiles" / f"{profile['name']}.json",
               EVALS / "fixtures", EVALS / "scenarios", HARNESS]
    return {"profile": profile["name"], "agent_bin": profile["bin"], "agent_version": version,
            "model": model, "seed": seed, "baseline": baseline, "runs_per_eval": runs,
            "python": platform.python_version(), "platform": platform.platform(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hashes": {str(p.relative_to(REPO)): _tree_hash(p) for p in tracked if p.exists()}}


def tally(results: list[dict]) -> tuple[dict, dict]:
    counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    errors = defaultdict(list)
    for r in results:
        if "error" in r:
            errors[r["scenario"]].append(r["error"])
            continue
        for cid, c in r["checks"].items():
            counts[r["scenario"]][cid][c["status"]] += 1
            if c["status"] == "ERROR":
                errors[r["scenario"]].append(f"{cid}: {c['detail']}")
    return counts, errors


def summarise(results: list[dict], scenarios: dict, fp: dict) -> tuple[str, bool]:
    counts, errors = tally(results)
    baseline = fp["baseline"]
    lines = ["# Eval report", "",
             f"Agent `{fp['profile']}` `{fp['agent_version']}` · model `{fp['model'] or '-'}` · "
             f"seed {fp['seed']} · {'BASELINE (artefacts under test removed)' if baseline else 'artefacts ON'} · "
             f"{fp['started']}", "",
             "| Scenario | Kind | Check | Pass | Fail | N/A | Pass rate | Threshold | Result |",
             "|---|---|---|---|---|---|---|---|---|"]
    ok = True
    for sid in sorted(counts):
        sc = scenarios[sid]
        specs = {c["id"]: c for c in sc["checks"]}
        for cid, c in counts[sid].items():
            n = c["PASS"] + c["FAIL"]
            rate = c["PASS"] / n if n else None
            threshold = 1.0 if sc["kind"] == "guardrail" else specs[cid].get("threshold")
            if baseline:
                verdict = "baseline"
            elif rate is None or threshold is None:
                verdict = "-"
            else:
                verdict = "PASS" if rate >= threshold else "FAIL"
                ok &= verdict == "PASS"
            rate_s = "-" if rate is None else f"{rate:.0%}"
            if rate == 1.0 and sc["kind"] == "eval" and n >= 4:  # rule of three
                rate_s += f" (failure rate likely < {3 / n:.0%})"
            th_s = "-" if threshold is None else f"{threshold:.0%}"
            lines.append(f"| {sid} | {sc['kind']} | {cid} | {c['PASS']} | {c['FAIL']} | {c['N/A']} "
                         f"| {rate_s} | {th_s} | {verdict} |")
    if errors:
        ok = False
        lines += ["", "## Harness errors (not counted as agent failures)", ""]
        lines += [f"- {sid}: {e}" for sid, errs in sorted(errors.items()) for e in errs]
    lines += ["", "Run directories are listed in `results.jsonl`. Read some transcripts before trusting this table."]
    return "\n".join(lines) + "\n", ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="+", type=Path)
    ap.add_argument("--profile", default="fake", help="agent profile in evals/profiles/ (default: fake)")
    ap.add_argument("--model", default="", help="pinned provider/model id; never an auto-router")
    ap.add_argument("--runs", type=int, default=5, help="runs per eval scenario; guardrails always run once")
    ap.add_argument("--jobs", type=int, default=1, help="parallel runs; safe because runs share nothing")
    ap.add_argument("--seed", type=int, default=None, help="reuse a seed to reproduce a run order")
    ap.add_argument("--baseline", action="store_true", help="remove each scenario's under_test artefacts")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per run")
    ap.add_argument("--runs-root", type=Path, default=None, help="default: a temp dir outside the repo")
    ap.add_argument("--out", type=Path, default=None, help="report directory (default: evals/results/<stamp>)")
    a = ap.parse_args(argv)

    profile = load_profile(a.profile)
    if profile.get("requires_model") and not a.model:
        ap.error(f"--model is required for the {a.profile} profile")
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(10**6)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    # Outside the repo, so the agent cannot find this repo's config or AGENTS.md by walking upwards.
    runs_root = a.runs_root or Path(tempfile.gettempdir()) / "agent-evals" / stamp
    runs_root.mkdir(parents=True, exist_ok=True)

    scenarios = {s["id"]: s for s in (json.loads(p.read_text()) for p in a.scenarios)}
    plan = []
    for s in scenarios.values():
        if a.baseline and (s["kind"] == "guardrail" or not s.get("under_test")):
            continue  # baselines compare artefacts; guardrails always test the shipped config
        plan += [s] * (1 if s["kind"] == "guardrail" else a.runs)
    random.Random(seed).shuffle(plan)  # no scenario always runs first

    fp = fingerprint(profile, a.model, seed, a.baseline, a.runs)
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        results = list(pool.map(
            lambda s: run_once(s, profile, runs_root, a.model, a.baseline, a.timeout), plan))
    for r in results:
        print(f"{r['scenario']}: " + (r.get("error") or " ".join(f"{k}={v['status']}" for k, v in r["checks"].items())))

    out = a.out or EVALS / "results" / stamp
    out.mkdir(parents=True, exist_ok=True)
    (out / "fingerprint.json").write_text(json.dumps(fp, indent=2))
    (out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results))
    report, ok = summarise(results, scenarios, fp)
    (out / "summary.md").write_text(report)
    print(f"\n{report}\nReport: {out}\nRun directories: {runs_root}")
    return 0 if ok or a.baseline else 1


if __name__ == "__main__":
    sys.exit(main())
