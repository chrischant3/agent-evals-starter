#!/usr/bin/env python3
"""Compare two reports, typically with and without the artefacts under test.

  python evals/harness/compare.py evals/results/<with> evals/results/<baseline>

Warns when the two runs differ in anything other than the baseline flag, seed or start time,
because then a difference in pass rates may not be caused by the artefact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from runner import tally  # noqa: E402

EXPECTED_TO_DIFFER = {"baseline", "seed", "started"}


def rates(report: Path) -> tuple[dict, dict]:
    results = [json.loads(line) for line in (report / "results.jsonl").read_text().splitlines() if line]
    counts, _ = tally(results)
    out = {}
    for sid, checks in counts.items():
        for cid, c in checks.items():
            n = c["PASS"] + c["FAIL"]
            out[(sid, cid)] = (c["PASS"] / n if n else None, n)
    return out, json.loads((report / "fingerprint.json").read_text())


def main(a: str, b: str) -> int:
    (ra, fa), (rb, fb) = rates(Path(a)), rates(Path(b))
    differs = sorted(k for k in fa.keys() | fb.keys() if k not in EXPECTED_TO_DIFFER and fa.get(k) != fb.get(k))
    if differs:
        print(f"WARNING: the runs also differ in {differs}. Differences below may not be caused by the artefacts.\n")
    label = lambda f: "baseline" if f["baseline"] else "with artefacts"
    print(f"| Scenario | Check | A: {label(fa)} | B: {label(fb)} | A - B |")
    print("|---|---|---|---|---|")
    for key in sorted(ra.keys() | rb.keys()):
        (pa, na), (pb, nb) = ra.get(key, (None, 0)), rb.get(key, (None, 0))
        fmt = lambda p, n: "-" if p is None else f"{p:.0%} (n={n})"
        delta = "-" if pa is None or pb is None else f"{(pa - pb) * 100:+.0f} pts"
        print(f"| {key[0]} | {key[1]} | {fmt(pa, na)} | {fmt(pb, nb)} | {delta} |")
    print("\nIgnore differences smaller than the gap between two runs of the same configuration.")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]) if len(sys.argv) == 3 else print(__doc__) or 2)
