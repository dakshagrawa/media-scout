# Media Scout

Media Scout is a native Hermes plugin and companion workflow for turning an authorized social-media submission into source-backed evidence and a review task. This repository contains the plugin, portable workflow templates, a supporting evidence skill, and an optional upstream patch. It does not contain a media acquisition engine or a hosted service.

The project was split from [dakshagrawa/production-checklist](https://github.com/dakshagrawa/production-checklist) (formerly `hermes-workflows` / `production-web-checklist`), which hosts software production-readiness skills and retains the existing `production-web-checklist` package. This standalone repository is `dakshagrawa/media-scout`; its filtered Git history has different commit IDs, not replacement authorship. Original contributors and dates are preserved, and package release tags needed by upgrade tests remain available. See [migration notes](MIGRATION.md) for provenance and deployment boundaries.

**Status: experimental, not production-ready.** Offline contracts and synthetic native SDK qualification do not establish live per-platform extraction or end-to-end Discord/provider reliability. Review [qualification](plugins/media-scout/QUALIFICATION.md) before installation.

## Version-one setup snapshots

The `version-one` branch and `media-scout-setup-v1.0.0` release preserve the sanitized **instruction-driven deployment**, including local skills, project-fit review, issue/PR templates, policies and recovery documentation. This PR advances the bundled setup to **1.0.1**, documenting local routing/output/contribution changes and `media-to-github` 0.2.0. The 1.0.0 archive remains immutable. Start at [snapshot-v1/README.md](snapshot-v1/README.md) and [1.0.1 changes](snapshot-v1/CHANGES-1.0.1.md). This is separate from the experimental native plugin below; public templates are not consent to activate connections, forwarding or deletion. No private backup is published.

## Start here

- [Install, configure, security and qualification](plugins/media-scout/README.md)
- [Workflow setup and operation](workflows/media-scout/README.md)
- [Acceptance criteria](workflows/media-scout/acceptance.md)
- [Contribution guidelines](CONTRIBUTING.md) and [security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Inactive Agent Reach fallback archive](archive/agent-reach/README.md) — pinned original instructions, not installed or automatically activated.

The plugin at `plugins/media-scout` is the native executable extension. It handles trusted intake bookkeeping, extraction claims, bounded evidence persistence, native reviewer handoff and separately opted-in retention. Hermes's admitted tools perform acquisition/transcription/vision; a reviewer uses its own authorized profile context. The workflow documents how to configure the native roles and features. The top-level `media-evidence-library` remains a separately reviewable instruction skill. The optional patch under `patches/media-thread-naming` is not required or automatically applied.

## Consent and security

Public configuration is inactive by default. Configure your own native Discord connection, owner allowlist and intended channel. Automatic review and cleanup each require explicit, separate authorization and qualification. Item-specific local-only, stop, defer or reject instructions override standing review consent. Sharing media does not authorize installation, publication, purchases, outreach, account changes or other consequential actions; obtain separate approval for the exact action.

The plugin is not a filesystem sandbox and runs with host-user authority. Its claims protect cooperating callers, not hostile processes. No custom service, daemon, installer, private credentials, live profile or private media is included. Review native security admission and restrict source/tool access independently. This third-party repository is not the official Hermes catalog and does not override an official-source-only policy.

## Runtime data and migration

The plugin stores runtime state under profile-scoped `plugin-data/media-scout/`, outside its replaceable install directory. It does not import the older instruction workflow's `media-library/`, migrate a deployment, or update/enable an existing installation automatically. Keep live profile data and credentials private; do not copy them into this repository.

## Layout and checks

```text
media-evidence-library/         # Supporting standalone media skill
plugins/media-scout/             # Native extension and bundled workflow skill
workflows/media-scout/           # Setup, templates, diagram and acceptance
patches/media-thread-naming/     # Optional upstream patch, provenance and license
tests/skills/                    # Offline skill and safety contracts
tests/plugins/                   # Offline plugin bookkeeping contracts
scripts/run_tests.sh             # Test entry point
.github/workflows/ci.yml         # Ubuntu Python 3.10 and 3.13 jobs
```

Run the offline checks with Python 3.10 or newer. They use synthetic fixtures, not live Discord, media providers or private deployment data:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
bash scripts/run_tests.sh -q
git diff --check
```

Required CI jobs run on Ubuntu with Python 3.10 and 3.13. Cross-platform jobs remain manually dispatchable. The smaller standalone test suite must not be read as the historical source repository's test count or as proof of a live deployment. Native SDK qualification and runtime limits are documented in the plugin acceptance guide.

The repository uses the MIT License. The optional upstream-derived patch retains its original license and attribution.