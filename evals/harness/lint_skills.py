#!/usr/bin/env python3
"""Static checks for SKILL.md files, against the Agent Skills specification.

  python evals/harness/lint_skills.py [skills-dir]     (default: agent/.agents/skills)

Catches skills that would silently never load, and skills whose descriptions compete.
The specification's own validator, skills-ref, is the authority; run it as well.
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

import yaml

# 1-64 chars of a-z, 0-9 and hyphens; no leading, trailing or consecutive hyphens.
# The spec allows unicode lowercase alphanumerics; this is deliberately ASCII-only.
NAME = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
EMBEDDED_SHELL = re.compile(r"!`[^`]+`")  # Kilo's embedded-command syntax
SIMILARITY_WARN = 0.6


def frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("no YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter is not a mapping")
    return meta, m.group(2)


def lint(root: Path) -> tuple[list[str], list[str]]:
    errors, warnings, descriptions = [], [], {}
    skills = sorted(root.glob("*/SKILL.md"))
    if not skills:
        errors.append(f"no skills found under {root}")
    for skill_md in skills:
        folder = skill_md.parent.name
        try:
            meta, body = frontmatter(skill_md.read_text())
        except (ValueError, yaml.YAMLError) as e:
            errors.append(f"{folder}: {e}")
            continue
        name, desc = str(meta.get("name", "")), str(meta.get("description", "") or "")
        if not NAME.match(name):
            errors.append(f"{folder}: invalid name {name!r}")
        if name != folder:
            errors.append(f"{folder}: name {name!r} must match its folder")
        if not desc.strip() or len(desc) > 1024:
            errors.append(f"{folder}: description must be 1-1024 characters")
        if EMBEDDED_SHELL.search(re.sub(r"```.*?```", "", body, flags=re.S)):
            warnings.append(f"{folder}: embedded shell commands never run in project skills (Kilo)")
        for ref in re.findall(r"\]\(((?:references|scripts|assets)/[^)]+)\)", body):
            if not (skill_md.parent / ref).exists():
                errors.append(f"{folder}: broken reference {ref}")
        descriptions[folder] = desc
    names = sorted(descriptions)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ratio = difflib.SequenceMatcher(None, descriptions[a], descriptions[b]).ratio()
            if ratio > SIMILARITY_WARN:
                warnings.append(f"{a} / {b}: descriptions {ratio:.0%} similar; they will compete")
    return errors, warnings


def main(root: Path) -> int:
    errors, warnings = lint(root)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if not errors:
        print(f"ok: {len(list(root.glob('*/SKILL.md')))} skill(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    default = Path(__file__).resolve().parents[2] / "agent" / ".agents" / "skills"
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else default))
