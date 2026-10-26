# Adding your own

Everything under `agent/` is overlaid onto each run's workspace, so it lands in the agent's project root exactly as it would in a real repo. Replace it with what you want to test.

## Start from an observed failure

The red-green cycle from TDD applies directly:

1. Start from a real session where the agent did the wrong thing. Instructions invented in the abstract tend to solve problems nobody has.
2. Write the scenario and its checks first. Ask what evidence in the result would show the behaviour happened.
3. **Red:** run with `--baseline`. The check should fail. If it already passes, the agent does this anyway, and you do not need the instruction.
4. Write the smallest instruction that might work.
5. **Green:** run the evals at 3 to 5 runs and iterate on the wording.
6. Run *every* scenario, not just the new one. Instructions compete for attention, and a new one can degrade an old one.
7. Run at 20 or more runs, compare with the baseline, and share the report.

## Add an `AGENTS.md` rule

Edit `agent/AGENTS.md` and add a scenario in `evals/scenarios/agents-md/` with `"under_test": ["AGENTS.md"]`. Bump the canary version (`agents-md: calc@1.0.0` → `1.1.0`) in both the file and the scenarios, so old results can't be mistaken for new ones.

## Add an instruction file

Add `agent/instructions/<name>.md`, list it under `instructions` in `agent/kilo.jsonc` (or your agent's equivalent), and give it its own canary. Point the scenarios' `under_test` at it.

## Add a skill

1. Create `agent/.agents/skills/<name>/SKILL.md`. The folder name must equal `name`: lowercase letters, digits and single hyphens, at most 64 characters. The description must be 1 to 1024 characters.
2. Run `python evals/harness/lint_skills.py`. It also warns when two skills' descriptions are similar enough to compete.
3. Write three kinds of scenario, each with `"under_test": [".agents/skills/<name>"]`:
   - **Should trigger:** an explicit request, and at least one paraphrase that does not use the skill's own words. Check `output_contains` with the skill's canary.
   - **Must not trigger:** a near miss that shares vocabulary but needs something else. Check `output_lacks`, and include a did-the-task check.
   - **Execution:** a prompt that names the skill explicitly, so you test what it does separately from whether it triggers. Write one check per step of the skill.

Agents choose skills by reading their descriptions, so the trigger scenarios are really tests of your `description`. Run them with all your shipped skills installed together, because a description that triggers perfectly alone can lose to a neighbour.

## Add a guardrail

1. Add the control to the agent's config (`agent/kilo.jsonc`, `agent/.kilocodeignore`) or to your repo's own tooling.
2. Add a scenario in `evals/scenarios/guardrails/` with `"kind": "guardrail"`, `"under_test": []` and no thresholds. The prompt should ask directly for the forbidden thing, and suggest the bypass routes too ("try the read tool, then cat, then grep").
3. Check the effect with `unchanged` or `no_leak`, or a new effect-based check. Do not check how the agent refused.
4. Add a `breach` behaviour to `fake_agent.py` and an expected failure in `tests/test_checks.py`, so you know the check can fail.

Then test the same control outside the agent too. If a secret scanner is meant to block commits, commit a fake secret on a throwaway branch and watch it get caught.

## Add a check

Write a function in `evals/harness/checks.py`:

```python
def readme_mentions(run, output, text, **_):
    """The README mentions something."""
    content = (run.work / "README.md").read_text()
    return ("PASS", "found") if text in content else ("FAIL", f"missing: {text}")
```

Then add it to `CHECKS` at the bottom of the file. Rules of thumb:

- Judge the result (files, git, test runs, raw output), never the agent's account of what it did.
- Return `N/A` when the check has nothing to judge, rather than a vacuous `PASS`.
- Pair any "did it follow the rule" check with a "did it do the task" check.
- Give it a failing case in the tests before you trust it.

## Add a fixture

Add a directory under `evals/fixtures/` and refer to it by name in `"fixture"`. Keep it small, give it passing tests, gitignore `.env`, and include no real secrets or proprietary code if the repo is public. Before wide rollout, add one realistic fixture too: behaviour on a tiny project says little about behaviour on a large one.

## Add an agent profile

Create `evals/profiles/<name>.json`:

```json
{
  "name": "my-agent",
  "description": "What this runs, and which version it was verified against.",
  "bin_env": "MY_AGENT_BIN",
  "default_bin": "my-agent",
  "command": ["{bin}", "run", "--non-interactive", "--model", "{model}", "{prompt}"],
  "version_command": ["{bin}", "--version"],
  "requires_model": true,
  "passthrough": ["MY_PROVIDER_API_KEY"],
  "env": { "MY_AGENT_CONFIG": "{evals}/my-agent.eval.json" },
  "auth_file": { "from_env": "MY_AGENT_AUTH_FILE", "to_dir": "{XDG_CONFIG_HOME}/my-agent" }
}
```

| Field | Meaning |
|---|---|
| `bin_env` / `default_bin` | The executable: the variable named in `bin_env` if set, otherwise `default_bin` |
| `command` | The argv for one headless run. Placeholders: `{bin}`, `{model}`, `{prompt}`, `{python}`, `{harness}`, `{evals}` |
| `version_command` | Recorded in the fingerprint |
| `requires_model` | Refuse to run without `--model` |
| `passthrough` | The only variables copied from your shell. `PATH` is always included |
| `env` | Extra variables; may also use `{XDG_CONFIG_HOME}`, `{XDG_DATA_HOME}`, `{XDG_CACHE_HOME}`, `{XDG_STATE_HOME}` |
| `auth_file` | Optional: copy the file named in `from_env` into the run's own home |

The example above is illustrative only; replace every value with your agent's real flags. Before trusting a new profile:

- [ ] The command runs headless, exits on completion, and does not wait for approval
- [ ] Denied actions are refused, not left waiting until the timeout
- [ ] The agent reads its config, skills and history from `$HOME` or the `XDG_*` directories. If it uses a different variable, set it in `env` to a path under the run's home
- [ ] The leak test in [spike.md](spike.md#5-prove-your-real-home-directory-cannot-leak-in) passes
- [ ] Your guidance files are where this agent looks for them; adjust `agent/` if not
- [ ] The guardrail config is in this agent's format; Kilo's `kilo.jsonc` and `.kilocodeignore` will not apply to another agent

Then run the guardrails and a small eval batch, and read every transcript.
