# Concepts

Why the harness is built the way it is. References are in [sources.md](sources.md).

## Two kinds of test

Treating every kind of agent guidance as the same problem is where most confusion comes from. The Cynefin framework helps separate them.

**Clear: deterministic controls.** These are permissions, ignore files, sandboxes, CI checks, pre-commit hooks and skill linting. The same input gives the same output. Test each case once, expect 100%, and gate on it. If one of these varies between runs, that is a bug.

**Complex: agent behaviour.** This covers whether the model follows an `AGENTS.md` rule, triggers a skill at the right moment, or writes the docstring it was asked for. The same input gives different outputs. You cannot prove these work. You probe them repeatedly, measure a rate, and decide whether the rate is good enough. That is what evals are for.

The design rule that follows: **anything whose failure is costly or hard to undo belongs in the clear domain.** A rule saying "never read `.env`" is a hope. A permission rule plus an ignore file plus a secret scanner is a control. The instruction can still explain why to the agent, but it is not what protects you.

| Artefact | Domain | How it is tested here | Gate |
|---|---|---|---|
| Permissions, ignore files | Clear | Guardrail scenarios, one run each, checked by effect | 100% |
| Skill file validity | Clear | `lint_skills.py` | No errors |
| The harness itself | Clear | `pytest` against the fake agent | All pass |
| `AGENTS.md`, instructions | Complex | Eval scenarios, N runs, pass rate | Threshold per check |
| Skill triggering | Complex | Should-trigger and must-not-trigger scenarios | Threshold per check |
| Skill execution | Complex | Explicitly invoked scenario; checks on each step | Threshold per check |

## Run independence

An eval result is evidence only if the run measured your artefact and nothing else. Coding agents read configuration, skills, agents and rules from your home directory. Some save "always allow" approvals there. Some find config by walking up parent directories, and most keep session history on disk. Any of these can make run 7 behave differently from run 1 for reasons unrelated to what you are testing.

The aim is the property of a hermetic build: the same inputs give the same result, because the run is isolated from the host. A model never gives the same result twice, but isolation makes sure the variation you measure comes from the model, not from your machine.

| Risk | Control | Proven by |
|---|---|---|
| Global config, skills, agents and approvals leak in | Empty `$HOME` and per-run `XDG_*` directories | `test_runs_never_share_directories`, `test_profile_env_is_applied` |
| A previous run leaves state behind | New directory tree per run, random ID, never reused, no session resume | `test_nothing_survives_from_an_earlier_run` |
| Shell environment variables change behaviour | Environment built from scratch; only listed names pass through | `test_your_environment_does_not_leak_in` |
| Config or `AGENTS.md` found in a parent directory | Runs live outside the repo; each workspace is its own git repo | `test_workspace_is_its_own_git_repo_outside_this_one` |
| The agent reads or tampers with the evidence | Transcripts and results stored outside the workspace | `test_evidence_lives_outside_the_agents_workspace` |
| The secret lands in the base commit | `.env` written after copying, and gitignored | `test_secret_exists_but_is_never_committed` |
| Credentials are shared or leaked between runs | Auth file copied into each run's own home; its path is not passed on | `test_auth_file_is_copied_into_the_runs_own_home_only` |
| The baseline differs from the real run in more than the artefact | Only the scenario's `under_test` paths are removed | `test_baseline_blanks_a_file_and_touches_nothing_else` |
| Host git config (hooks, aliases) interferes | `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` | every git call |
| Run order biases results (warm caches, rate limits) | Runs are shuffled with a recorded seed | `test_seed_reproduces_run_order` |
| Locale and timezone differ between machines | `LANG` and `TZ` fixed | n/a |

The model provider and the network remain shared, and you cannot remove them. Pin the model to a dated ID, never an auto-router, and record it. If commands the agent runs should not reach the network, use your agent's sandbox, if it has one.

## Judge results, not stories

Every check reads files on disk, git, test results or the raw output text. None of them trust what the agent *says* it did, and none parse an agent's session format. Three consequences:

- **Portable.** The same checks work for any agent that edits files and prints text.
- **Robust.** Upgrading the agent tool cannot break a check by changing its log format.
- **Limited.** Some things leave no trace in the result, such as the order in which files were written. Make those leave evidence (for example, require a commit for the failing test before the fix), or write a session parser for your agent and accept the maintenance cost.

### Canaries

Each artefact asks the agent to end its reply with a versioned marker, such as `agents-md: calc@1.0.0`. If the marker is missing, the artefact probably never loaded, and that run tells you nothing about compliance. Bump the version whenever the wording changes, so a report can only match the text it tested. For skills, the marker is also the trigger evidence. Once you trust loading, you can drop the canaries.

### Did the agent do the task at all?

If the agent does nothing, there are no new functions, so a docstring check has nothing to fail on. A lazy agent would score 100%. Every eval therefore pairs its instruction check with a **did-the-task** check (`function_defined`, `function_absent`), and the docstring check reports `N/A` rather than `PASS` when nothing changed. The fake agent's `nothing` mode exists to prove this works.

### Guardrails are tested by effect

A guardrail scenario asks directly for the forbidden thing, then checks the effect: is the file byte-for-byte unchanged, and does the planted secret appear anywhere? It never inspects how the agent refused. This is state verification rather than behaviour verification. It survives tool upgrades, and it catches bypass routes, for example a file-read denial that a `grep` or shell command gets round. The planted secret is a honeytoken.

## Baselines: does the artefact change anything?

`--baseline` reruns each eval with that scenario's `under_test` paths removed: a file is blanked, a directory (such as a skill) is deleted. Everything else stays identical. Compare the two with `compare.py`:

- **Much better with the artefact:** it is doing work. Keep it.
- **High in both:** the model does this anyway. The artefact costs context and buys nothing measurable, so consider dropping it.
- **Low in both:** it is not landing. Reword it, add an example, or enforce the behaviour deterministically instead.
- **The canary passes in the baseline:** something else is giving instructions. Find it before trusting any other number.

## How many runs?

With zero failures in *n* runs, the true failure rate is, with about 95% confidence, below 3/*n*: the "rule of three". Ten clean runs bound it at 30%, and twenty at 15%. Use 3 to 5 runs while iterating on wording and 20 or more before sharing a result, and always say how many runs a claim rests on.

To see how noisy your setup is, run the same configuration twice. Ignore any difference between two configurations that is smaller than the gap between those two identical runs.

## Keeping the eval set honest

- **Version scenarios like code.** Changing a scenario to make an artefact pass is the eval equivalent of editing an assertion to make a test pass. Make it visible in review.
- **Hold some scenarios back.** If you tune wording while watching the same scenarios, you overfit to them. Keep about a third aside, and run them only before you share a result.
- **Use realistic fixtures before wide rollout.** A 20-line fixture is for plumbing. Behaviour on a large codebase, under context pressure, can be very different.
- **Turn every reported miss into a scenario.** Lab evals never cover everything real use does.

## Testing the harness

A harness with a bug looks exactly like a badly behaved agent. So the harness has its own tests, run against `fake_agent.py`, which behaves well or badly on demand. Every scenario must have at least one mode in which it fails (`test_every_scenario_has_a_failure_case`): a scenario that nothing can fail is testing nothing.

Then check the tests themselves: break the harness on purpose and confirm something goes red. These were run against this repo:

| Deliberate bug | Caught |
|---|---|
| Inherit the whole host environment | yes |
| Reuse one run directory | yes |
| Share `$HOME` between runs | yes |
| Do not overlay `agent/` onto the workspace | yes |
| Baseline removes nothing | yes |
| Commit `.env` into the base commit | yes |
| Do not copy the auth file | yes |
| Docstring check judges untouched functions | yes |
| Ignore the secret appearing in agent output | yes |
| Count changelog lines that were already there | yes |
| `tests_pass` always passes | yes |
| `output_lacks` inverted | yes |
| Ignore the seed when shuffling | yes |
| Run guardrails in baseline mode | yes |

## People

Pass rates measure the artefacts, not the engineers. If results from real sessions ever turn into a team scorecard, people will route around the tooling, and you lose the signal along with the trust (Goodhart's law). Publish results with their limits: run count, agent version, model, date, and what the fixtures do not cover. Make it easy to report "it ignored the instruction", and make disagreeing with an instruction a legitimate route to changing it.
