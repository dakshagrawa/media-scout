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
