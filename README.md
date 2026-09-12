# Hermes Agent Skills

Reusable skill packages for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

## Included skill

- [`production-web-checklist/`](production-web-checklist/) audits websites across
  strategy, interface design, content, SEO, accessibility, privacy, security,
  performance, and release verification.

The skill is a workflow for an agent. It is not a website generator, legal
advice, a security certification, or a guarantee of search performance.

## Use a skill

Use the installation and profile guidance in the [Hermes Agent skills
documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).
This repository keeps each skill in its own top-level directory so a package can
be copied, reviewed, versioned, and released independently.

## Repository layout

```text
production-web-checklist/SKILL.md  # Skill instructions and metadata
tests/skills/                        # Contract tests for skill packages
scripts/run_tests.sh                # Reproducible local test entry point
.github/workflows/ci.yml             # Cross-platform CI
```

## Development

Requirements: Python 3.10 or newer. Create a virtual environment, install the
development dependencies, and run the same entry point used by CI:

```text
terminal(command="python -m venv .venv")
terminal(command=".venv/bin/python -m pip install -r requirements-dev.txt")
terminal(command="bash scripts/run_tests.sh -q", timeout=300)
terminal(command="git diff --check")
```

On Windows, run the script from Git Bash; its test runner also recognizes
`.venv/Scripts/python.exe`. From PowerShell, invoke
`.venv\\Scripts\\python.exe -m pytest -q`. The test suite uses no live network
and does not require Hermes credentials.

When editing a skill:

1. Keep frontmatter complete, valid, and under the documented description limit.
2. Keep instructions actionable, source-verified, and free of machine-local
   paths or secrets.
3. Update the skill contract tests when its structure or safety invariants
   change.
4. Run the local gates, inspect the complete diff, and open a pull request.

## Versioning

The `version` in each `SKILL.md` is the package version. Use semantic versioning:
patch changes correct wording or examples, minor changes add backward-compatible
workflow guidance, and major changes alter the skill's contract. Record public
changes in [`CHANGELOG.md`](CHANGELOG.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the review and pull-request
checklist. Security reports should follow [`SECURITY.md`](SECURITY.md).

## License

This repository is released under the [MIT License](LICENSE).
