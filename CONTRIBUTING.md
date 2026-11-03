# Contributing

Thanks for improving these skill packages. Keep changes small, evidence-based,
and independently reviewable.

## Before editing

- Read the target `SKILL.md`, its tests, and the repository README.
- Confirm the change belongs in the selected skill rather than a new package.
- Do not include credentials, private data, machine-local paths, fabricated
  claims, or unrelated formatting churn.

## Skill requirements

Every skill package must have:

- `SKILL.md` with complete frontmatter: `name`, `description`, `version`,
  `author`, `license`, `platforms`, and `metadata.hermes`.
- A description of 60 characters or fewer that ends with a period and states the
  capability in its first 57 characters.
- A body with a clear trigger, prerequisites, actionable procedure, pitfalls,
  and verification guidance.
- Tests under `tests/skills/test_<skill>_skill.py` for frontmatter and important
  behavioral invariants.
- No secret values or absolute machine paths.
- Source notes and social-media references are evidence, not authority. Record
  the source URL and retrieval date for external advice, separate observed
  facts from your adaptation, and do not reproduce private data, credentials,
  or a creator's entire catalog in a skill.

## Workflow templates and publication

Keep skills in their existing top-level package directories. Put multi-profile
topologies, inert examples and diagrams under `workflows/<name>/`; optional
version-specific upstream patches belong under `patches/<name>/` with exact base,
integrity metadata and upstream license. A repository rename does not authorize
moving installed packages or editing live profiles.

Write portable examples from an explicit allowlist, not a copy of a private
profile. Exclude media, transcripts, real receipts/records, auth/config dumps,
logs, memory, real channel/task IDs and machine-local paths. Preserve original
authorship. Local deployment test results must be labelled as such, not as CI
coverage or a guarantee for a new install. Keep forwarding/deletion inactive in
public defaults until explicit local consent and qualification. Test safety
contracts and links without live credentials or destructive CI actions.

## Native plugins

Keep executable extensions under `plugins/<name>/`, separate from instruction-only
skills and workflow templates. Use documented public Hermes plugin APIs only; no
runtime overrides of core functions, private registries or UI markup. Store runtime
data through the native profile-scoped plugin storage helpers, outside the install
tree. Declare the exact tools/hooks/capabilities and truthful compatibility floor.

Add behavioral tests under `tests/plugins/`, with isolated state, no credentials or
external clients, and failure/replay/concurrency coverage. Run actual native Plugin
Doctor and catalog validation in a disposable matching SDK environment. Distinguish
synthetic SDK acceptance from real Discord/provider/media qualification. Never
reuse private deployment fixtures as public examples or claim an untested OS.

Publish only a reviewed immutable commit after both required Ubuntu checks pass.
Component release tags and archive hashes must match that commit. An official
catalog submission is a separate exact-SHA PR, not a claim of maintainer admission.
Enabling a package in a live profile is separate from publishing it.

## Local checks

From the repository root:

```text
terminal(command="python -m venv .venv")
terminal(command=".venv/bin/python -m pip install -r requirements-dev.txt")
terminal(command="bash scripts/run_tests.sh -q", timeout=300)
terminal(command="git diff --check")
```

On Windows, run the test script from Git Bash or invoke
`.venv\\Scripts\\python.exe -m pytest -q` from PowerShell.

Inspect test output and the full diff. If the skill's instructions mention a
command, verify that the command is real, bounded, and appropriate for the
supported platforms.

## Pull requests

Use a focused branch and explain:

- what behavior or workflow changed;
- why the change is needed;
- which tests and checks were run;
- any assumptions, unsupported platforms, or unresolved risks.

Reviewers should be able to validate every changed file from the pull request.
Do not merge a change with failing required checks or unexplained generated
files.
