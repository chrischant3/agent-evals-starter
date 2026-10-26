# Sources

Checked 26 October 2026. The harness code is original. These are the documented behaviours, specifications and practices it is built on.

## Kilo Code

- [Kilo Code CLI](https://kilo.ai/docs/code-with-ai/platforms/cli): `kilo run --auto`, exit codes, `--format json`, permission syntax and last-match-wins, refusal of unapproved actions in autonomous mode, `KILO_CONFIG` and trusted config, `{env:}` resolution, `KILO_ORG_ID`, "Always run" approvals saved to global config, OpenTelemetry, `@kilocode/cli`
- [agents.md](https://kilo.ai/docs/customize/agents-md): `AGENTS.md` loaded from the project root at task start; per-directory files loaded on demand
- [Skills](https://kilo.ai/docs/customize/skills): skill locations including `.agents/skills/`, description-based selection, `KILO_DISABLE_SKILL_SHELL`
- [Custom Rules](https://kilo.ai/docs/customize/custom-rules): `instructions` in `kilo.jsonc`
- [Agent Permissions](https://kilo.ai/docs/customize/agent-permissions): rule order, and the `.env` sensitive-file prompt
- [.kilocodeignore](https://kilo.ai/docs/customize/context/kilocodeignore)
- [Sandboxing](https://kilo.ai/docs/getting-started/settings/sandboxing): XDG directories, read denials being tool-specific, network restrictions
- [Cost Controls](https://kilo.ai/docs/getting-started/cost-controls-and-usage-safeguards): `kilo-auto/*` models
- [OpenCode Tools](https://opencode.ai/docs/tools/): `apply_patch` governed by the `edit` permission (the Kilo CLI is an OpenCode fork)

## Formats and specifications

- [AGENTS.md](https://agents.md/): the open format, and nearest-file precedence
- [Agent Skills specification](https://agentskills.io/specification): `name` and `description` rules, directory layout; the `skills-ref` validator is linked from its Validation section
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/)
- [git-config](https://git-scm.com/docs/git-config): `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`
- [Python `ast`](https://docs.python.org/3/library/ast.html): `get_docstring`, `get_source_segment`
- [Keep a Changelog](https://keepachangelog.com/): the `## Unreleased` convention

## Practice and research

- Anthropic, [Define success criteria and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests): task-specific evals, edge cases, automated grading
- Snowden, D.J. and Boone, M.E. (2007), [A Leader's Framework for Decision Making](https://hbr.org/2007/11/a-leaders-framework-for-decision-making), *Harvard Business Review*: Cynefin
- Bazel, [Hermeticity](https://bazel.build/basics/hermeticity)
- [Rule of three (statistics)](https://en.wikipedia.org/wiki/Rule_of_three_(statistics)); primary reference: Hanley, J.A. and Lippman-Hand, A. (1983), "If nothing goes wrong, is everything all right?", *JAMA* 249(13)
- Fowler, M., [Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html): state versus behaviour verification
- [Honeytoken](https://en.wikipedia.org/wiki/Honeytoken)
- [Training, validation and test data sets](https://en.wikipedia.org/wiki/Training,_validation,_and_test_data_sets): why hold scenarios back
- [Goodhart's law](https://en.wikipedia.org/wiki/Goodhart%27s_law)
- Zheng, L. et al. (2023), [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685): background if you add an LLM-graded check
