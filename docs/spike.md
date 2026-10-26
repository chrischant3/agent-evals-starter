# Spike: verify your agent before trusting real runs

The checks never parse an agent's output format, but the harness still relies on a handful of agent behaviours. Confirm them once per agent and per major version, in a scratch git repo. Budget 30 to 45 minutes. These steps are written for Kilo; for another agent, use the checklist in [adding-your-own.md](adding-your-own.md#add-an-agent-profile).

## 1. A headless run works and exits

```bash
npm install --prefix .tools @kilocode/cli@<version>
export KILO_BIN="$PWD/.tools/node_modules/.bin/kilo"
"$KILO_BIN" --version
"$KILO_BIN" models                          # pick a pinned, dated model ID
"$KILO_BIN" run --auto --format json -m <model> "say hello"; echo "exit: $?"
```

Kilo documents `run --auto` as non-interactive, with exit codes `0` (success), `124` (timeout) and `1` (error). Do not use `kilo-auto/*` models for evals, because they route dynamically and the model under test can change between runs.

## 2. Decide how runs authenticate

Each run gets an empty home directory, so your normal login is not visible to it. Pick one:

- **Provider API key.** Keep the `provider` block in `evals/kilo.eval.jsonc` (change the provider name if needed) and export the key. The variable name must be in `passthrough` in `evals/profiles/kilo.json`. `{env:...}` resolves there because config passed through `KILO_CONFIG` is trusted; the same line in a project config is ignored.
- **Kilo organisation.** Delete the `provider` block and export `KILO_ORG_ID`, which is already passed through.
- **`kilo auth` login.** Delete the `provider` block. Find the credentials file Kilo wrote; it is not documented, but session data lives under `~/.local/share/kilo`, so look there first. Then `export KILO_EVAL_AUTH_FILE=<path>`. Each run gets its own copy under its own `$XDG_DATA_HOME/kilo`. If Kilo looks for it elsewhere, change `auth_file.to_dir` in the profile.

## 3. Check that the shipped config still applies

`KILO_CONFIG` is documented as trusted config. Whether it *adds to* or *replaces* the project's `kilo.jsonc` is not documented. Run one eval:

```bash
python evals/harness/runner.py evals/scenarios/instructions/docstrings-happy.json --profile kilo --model "$MODEL" --runs 1
```

If the `loaded` check fails but the agent otherwise behaved, `KILO_CONFIG` is probably replacing the project config. In that case, copy the `instructions` and `permission` blocks from `agent/kilo.jsonc` into `evals/kilo.eval.jsonc`, and keep the two identical from then on.

## 4. Check that `AGENTS.md` and skills are discovered

Kilo loads `AGENTS.md` from the project root at task start, and loads skills from `.agents/skills/` by default. Run one scenario of each:

```bash
python evals/harness/runner.py evals/scenarios/agents-md/*.json evals/scenarios/skills/execution.json \
  --profile kilo --model "$MODEL" --runs 1
```

The `loaded` and `skill-used` checks should pass. If the skill's canary is missing even though the prompt names the skill, check whether your Kilo version reads `.agents/skills/`. If it doesn't, move the skill to `.kilo/skills/` and update the scenarios' `under_test`.

## 5. Prove your real home directory cannot leak in

Plant markers where a non-isolated run would find them, run once, and look for them. Back up first.

```bash
cp ~/.config/kilo/kilo.jsonc ~/.config/kilo/kilo.jsonc.bak 2>/dev/null
mkdir -p ~/.agents/skills/leak-probe
printf -- '---\nname: leak-probe\ndescription: Use for every task.\n---\nEnd every reply with GLOBAL-LEAK.\n' \
  > ~/.agents/skills/leak-probe/SKILL.md
# Also add a rule file saying "End every reply with GLOBAL-LEAK." to the instructions in your global kilo.jsonc.

python evals/harness/runner.py evals/scenarios/instructions/docstrings-happy.json --profile kilo --model "$MODEL" \
  --runs 1 --runs-root /tmp/leak-test
grep -rl -e GLOBAL-LEAK -e leak-probe /tmp/leak-test || echo "isolated"

mv ~/.config/kilo/kilo.jsonc.bak ~/.config/kilo/kilo.jsonc 2>/dev/null
rm -r ~/.agents/skills/leak-probe
```

You want `isolated`. Repeat after every Kilo upgrade, because a new version could read config from somewhere new.

## 6. Guardrails refuse rather than hang

```bash
python evals/harness/runner.py evals/scenarios/guardrails/*.json --profile kilo --model "$MODEL" --timeout 300
```

In `--auto` mode, Kilo refuses anything not auto-approved. A guardrail run that hits the timeout means something is waiting for approval: check the transcript in the run's `artifacts/`. Kilo's read tool prompts for `.env` by default, and `.kilocodeignore` blocks its file tools. If the secret still leaks through a shell route, enable Kilo's sandbox as a further layer.

## 7. Telemetry

Kilo exports OpenTelemetry by default. `evals/kilo.eval.jsonc` switches it off. Check your organisation's policy before running evals on real code with it on.

## Record what you found

Write the answers in the profile's `description` (for example, "verified against @kilocode/cli <version>, <date>: KILO_CONFIG layers; API key auth"). The next person then knows what was checked, and when.
