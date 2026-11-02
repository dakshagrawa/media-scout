# Repository rename and layout compatibility

`dakshagrawa/agent-skills` is now `dakshagrawa/hermes-workflows`. This is the same GitHub repository and history, not a new replacement repository. GitHub normally redirects old repository URLs; update explicit remotes, bookmarks and downstream configuration rather than relying on redirects forever.

Existing skill package paths, including `production-web-checklist/SKILL.md`, are preserved. Top-level skill directories remain independently installable/reviewable. New reusable instructions live in [media-evidence-library](media-evidence-library/SKILL.md); multi-profile topology, inert templates and diagram live in [workflows/media-scout](workflows/media-scout/README.md); optional version-specific upstream changes live separately under [patches](patches/media-thread-naming/README.md).

No installation, native profile, live config, channel credential or private data is migrated by the rename or this PR. Existing installs do not auto-update or auto-enable forwarding/deletion. Repository package versions and deployed policy versions are separate: the new portable skill starts at 0.1.0, even though its source deployment was called usable v1.

For a checkout, use `terminal(command="git remote set-url origin https://github.com/dakshagrawa/hermes-workflows.git")`, then verify `git remote -v`. Do not move or rename existing installed skill directories just because the repository name changed.
