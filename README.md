# agent-evals-starter

**Guardrails and evals for your `AGENTS.md`, skills and agent instructions, with every run isolated so the results mean something.**

You've written an `AGENTS.md`, a skill and a few instruction files for your coding agent. How do you know the agent follows them? How do you know they keep working after a model or tool update? How do you show a team that they're worth adopting?

This repo is a small, working example of the answer. It contains:

- **Three things to test**, one of each kind: an `AGENTS.md`, an instruction file and a skill.
- **Three guardrails** that stop the agent editing outside its lane, leaking a secret, or running destructive shell commands.
- **A harness** that runs each scenario many times. Every run gets a fresh workspace, a fresh home directory and an environment built from nothing.
- **A fake agent and 78 tests**, so you can prove the harness works for free before you spend a single token.

It ships with a profile for [Kilo Code](https://kilo.ai/docs/code-with-ai/platforms/cli). The harness, the checks and the approach are agent-agnostic: adding another agent means writing one small JSON profile ([guide](docs/adding-your-own.md#add-an-agent-profile)).

> [!NOTE]
> The harness is tested against the bundled fake agent: 78 tests, and 14 deliberate bugs, each one caught. It has not been run against every agent, model or version, because a result only holds for the combination that produced it. [docs/spike.md](docs/spike.md) is a short checklist for confirming the few agent behaviours the harness relies on, before you trust a real run.

## The idea in one paragraph

An **instruction** (an `AGENTS.md` rule, a skill, a rule file) only *asks* the model to do something. Whether it does is probabilistic, so you can't prove it works. You run it many times, measure a pass rate and compare against a run without the instruction. That's an **eval**. A **guardrail** is enforced by the agent tool itself (permissions, ignore files), so it should behave the same every time. You test it once per case and expect 100%. Anything that must never happen belongs in a guardrail; instructions are for judgement and style. More in [docs/concepts.md](docs/concepts.md).

## Quickstart: no API key, two minutes

```bash
git clone <this repo> && cd agent-evals-starter
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python -m pytest                                          # 78 passed: the harness works
python evals/harness/runner.py evals/scenarios/*/*.json   # every scenario, against the fake agent
```

With the default fake agent, every check passes. Now make the agent ignore all its instructions and watch the report catch it:

```bash
FAKE_MODE=sloppy python evals/harness/runner.py evals/scenarios/*/*.json --runs 3
```

```
| Scenario            | Kind  | Check      | Pass | Fail | N/A | Pass rate | Threshold | Result |
|---------------------|-------|------------|------|------|-----|-----------|-----------|--------|
| agents-md-changelog | eval  | loaded     | 0    | 3    | 0   | 0%        | 90%       | FAIL   |
| agents-md-changelog | eval  | did-task   | 3    | 0    | 0   | 100%      | 90%       | PASS   |
| agents-md-changelog | eval  | changelog  | 0    | 3    | 0   | 0%        | 90%       | FAIL   |
| docstrings-happy    | eval  | docstrings | 0    | 3    | 0   | 0%        | 90%       | FAIL   |
| skill-execution     | eval  | warns      | 3    | 0    | 0   | 100%      | 90%       | PASS   |
| skill-execution     | eval  | test-added | 0    | 3    | 0   | 0%        | 90%       | FAIL   |
| ...                 |       |            |      |      |     |           |           |        |
```

Other modes: `nothing` (does no work: catches vacuous passes), `trigger_happy` (uses the skill when it shouldn't), and `breach` (does whatever a guardrail prompt asks).

## Running against a real agent (Kilo)

```bash
# 1. Pin the agent version. A result only holds for the version that produced it.
npm install --prefix .tools @kilocode/cli@<version>
export KILO_BIN="$PWD/.tools/node_modules/.bin/kilo"

# 2. Authenticate (API key shown; for organisations or `kilo auth`, see docs/spike.md)
export ANTHROPIC_API_KEY=...
MODEL=<provider/model-id>      # a pinned, dated model, never an auto-router

# 3. Spike: confirm the agent behaves as the harness assumes (30 minutes, once)
#    -> docs/spike.md

# 4. Guardrails first. Every one must pass; a failure is a config bug, not bad luck.
python evals/harness/runner.py evals/scenarios/guardrails/*.json --profile kilo --model "$MODEL"

# 5. Evals: a few runs, then read every transcript and check each PASS and FAIL by eye
python evals/harness/runner.py evals/scenarios/*/*.json --profile kilo --model "$MODEL" --runs 3

# 6. Enough runs to mean something, then a baseline without the artefacts under test
python evals/harness/runner.py evals/scenarios/*/*.json --profile kilo --model "$MODEL" --runs 20 --jobs 2
python evals/harness/runner.py evals/scenarios/*/*.json --profile kilo --model "$MODEL" --runs 20 --jobs 2 --baseline

# 7. Did the artefacts actually change behaviour?
python evals/harness/compare.py evals/results/<with> evals/results/<baseline>
```

Each report directory holds `summary.md`, `results.jsonl` (with the path to every run's workspace and transcript) and `fingerprint.json`. The fingerprint records the agent version, model, seed, run count and hashes of every file that could change a result.

## What's being tested

| Artefact | File | Scenarios | What the checks look at |
|---|---|---|---|
| `AGENTS.md` | [`agent/AGENTS.md`](agent/AGENTS.md) | [`agents-md/`](evals/scenarios/agents-md) | A new `CHANGELOG.md` line names the changed function |
| Instruction | [`agent/instructions/docstrings.md`](agent/instructions/docstrings.md) | [`instructions/`](evals/scenarios/instructions): happy path, and a prompt that pushes against it | Every added or changed function has a docstring (parsed with `ast`); tests still pass |
| Skill | [`agent/.agents/skills/deprecate-function/`](agent/.agents/skills/deprecate-function/SKILL.md) | [`skills/`](evals/scenarios/skills): explicit trigger, paraphrased trigger, near miss that must *not* trigger, execution | Trigger: the skill's marker appears (or doesn't). Execution: the warning, docstring note, test and changelog entry all exist, and the tests still pass |
| Guardrails | [`agent/kilo.jsonc`](agent/kilo.jsonc), [`agent/.kilocodeignore`](agent/.kilocodeignore) | [`guardrails/`](evals/scenarios/guardrails) | Protected files are byte-for-byte unchanged; a planted secret appears nowhere |

Each artefact ends its instructions with a **canary** line such as `agents-md: calc@1.0.0`. If the canary is missing, the artefact probably never loaded, and that run tells you nothing about whether it was followed. For skills, the canary doubles as evidence of triggering.

## How runs are kept independent

| Risk | Control |
|---|---|
| Your global config, skills, agents and saved approvals leak in | Each run gets an empty `$HOME` and its own `XDG_*` directories |
| An earlier run leaves something behind | A new directory tree per run, with a random ID, never reused or resumed |
| Your shell environment changes behaviour | The environment is built from scratch; only named variables pass through |
| The agent finds this repo's config or `AGENTS.md` by walking up parent directories | Runs live outside the repo, and each workspace is its own git repo |
| The agent reads or edits the evidence | Transcripts and results are stored outside the workspace |
| Your git hooks and aliases interfere | Global and system git config are shut out |
| Run order biases results | Runs are shuffled with a recorded seed (`--seed` reproduces it) |
| The baseline differs in more than the artefact | `--baseline` removes only each scenario's `under_test` paths |

Each control has a test in [`evals/harness/tests/test_isolation.py`](evals/harness/tests/test_isolation.py). The model provider and the network are still shared; pin the model and record it. Background in [docs/concepts.md](docs/concepts.md#run-independence).

## Layout

```
agent/                      what you ship, overlaid onto every run's workspace
  AGENTS.md
  instructions/docstrings.md
  .agents/skills/deprecate-function/SKILL.md
  kilo.jsonc                instruction wiring + permission guardrails
  .kilocodeignore           file-access guardrail
evals/
  profiles/                 how to run each agent (kilo.json, fake.json)
  kilo.eval.jsonc           eval-only Kilo settings: how to reach the model, nothing else
  fixtures/calc/            the tiny project the agent works on
  scenarios/                one JSON file per scenario: prompt, checks, thresholds
  harness/
    isolation.py            fresh workspace, home and environment per run
    checks.py               judge results on disk, never the agent's account of them
    runner.py               runs scenarios, writes the report
    compare.py              with-versus-baseline comparison
    lint_skills.py          static checks against the Agent Skills spec
    fake_agent.py           scripted stand-in agent
    tests/                  78 tests for all of the above
docs/
  concepts.md               why it's built this way
  walkthrough.md            build it yourself, step by step
  adding-your-own.md        your own instructions, skills, checks and agents
  spike.md                  verify your agent before trusting real runs
  sources.md                references
```

## Use it for your own work

Replace the contents of `agent/` with your own `AGENTS.md`, skills and instructions. Replace the fixture with a small, safe copy of the kind of project they're for. Then write scenarios. [docs/adding-your-own.md](docs/adding-your-own.md) covers each piece, including writing new checks and adding a profile for a different agent.

## Before you rely on a result

- **The checks only look at results.** They read files, git, test outcomes and raw output text, and never parse an agent's session format. That makes them portable and hard to fool, but it limits what they can see. Ordering ("wrote the test before the code") needs evidence in git, or a session parser for your agent.
- **Pass rates need volume.** With zero failures in *n* runs, the true failure rate is probably below 3/*n* (the "rule of three"). Ten clean runs bound it at about 30%, not 0%. The report prints the bound.
- **Thresholds are a team decision.** The ones in `scenarios/` are placeholders. If a team needs 100%, the behaviour belongs in a guardrail or CI, not in an instruction.
- **Isolation is not a security sandbox.** Runs are isolated from each other and from your config, but the agent and `tests_pass` still execute code on your machine. Use a disposable VM or container for anything you would not run yourself.
- **Results are per agent, per version, per model.** Re-run after any of them changes. The fingerprint tells you whether two reports are comparable.

## Licence

MIT. See [LICENSE](LICENSE).
