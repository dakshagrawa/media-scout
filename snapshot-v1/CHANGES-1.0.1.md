# Setup v1.0.1 — local instruction changes

**PR candidate; not published as a new GitHub release.** This is a selective update to the sanitized instruction-driven setup in `snapshot-v1/`, not a new full live-profile capture or an installer. Setup version **1.0.1**, bundled `media-to-github` **0.2.0**, and the experimental native plugin's own version are separate identities.

## Baseline and preservation

- Based on immutable setup v1.0.0 at `abf747ac3fbbd7494df30751466ea36dec215a98`, tag `media-scout-setup-v1.0.0`, on the protected `version-one` branch.
- The existing branch, tag, release and release assets are not changed. Current `snapshot-v1/` on this PR branch advances to 1.0.1; fetch the historical tag for exact 1.0.0 bytes.
- This PR targets `main`, not the locked archival branch. It therefore also brings the already-reviewed v1.0.0 snapshot infrastructure into the main branch. Compare against the archival commit to isolate the new patch.
- Plugin code, native naming patch, top-level evidence package, inactive configuration, safe-import overlays, retention/recovery policies and disabled cron definitions are unchanged from the baseline.

## Recorded local changes

1. **Bounded routing:** Scout may answer acknowledgments/status/source lookups, explicitly summary-only requests and faithful explanations of completed reviews directly. Ordinary new media, claim verification/research, personalized learning/project-fit and action proposals still use Default. Bare new links still trigger project-fit review; owner stop/no-forward/local-only overrides apply. Reuse existing work. A direct reply cannot fabricate completion, cancel tasks or change approvals; Default unavailability leaves judgment pending.
2. **Production repository scope:** production-readiness skill changes cover web/apps, backend, infrastructure, non-web software, security, testing, deployment, performance and operations. The source repository is now named `production-checklist`; the existing web-focused package remains `production-web-checklist/`. Public setup files generalize owner/repository IDs; a new operator must supply and verify their own targets. Media Scout machinery stays separate, and renames do not transfer action approvals.
3. **Optional owner actions:** final summaries may include 1–2 useful elective steps under **Optional things you can do**, with benefits. Omit the section when empty. **Your action** lists only genuine blockers/required decisions or **None required**. Do not duplicate planned work or invent homework; suggestions authorize no execution.
4. **Complete contribution workflow:** preserve the current local helper's evidence reuse, source-specific overlap checks, substantive Default assessment, exact public payload delivery and approval checks, private proposal/execution separation, full review-contract handoff and readback/deduplication guidance. These are instructions, not new enforced access controls.
5. **Implementation/deployment handoff:** both issue and PR templates now cover target/baseline, bounded implementation, dependencies/configuration/security/data, acceptance/release gates, rollout/activation, operations/ownership, rollback/recovery and open decisions/deferred work. Include enough cleared context to work without Discord or rewatching the video. Issues state proposed requirements; PRs describe actual changes and evidence with remaining release work explicit. Unknown fields name the missing check; irrelevant fields give a Not applicable reason. Documentation-only changes do not invent service infrastructure. Secret values and private deployment bindings remain excluded; irreversible data changes need real recovery analysis, not a promise that git revert restores data.

## Provenance and inventory interpretation

Only these live setup paths were selectively refreshed and sanitized: `SOUL.md`, `media-library/review-policy.md`, the primary-review/response templates and the complete six-file `media-to-github` package. No other live profile state was exported. Original authorship/license is retained.

Dependencies, other skill inventory entries, skill enable/disable state, original capture date, selected runtime configuration and private-backup statements describe the original 1.0.0 capture. They are not a new census or new private backup. The `media-to-github` inventory row alone is updated to version 0.2.0 and the hash of its **sanitized bundled** SKILL.md; `hash_scope` identifies this distinction. The manifest separately binds every public file and records the immutable baseline and refreshed allowlist.

## Safety, migration and verification

- Apply safe overlays from [README](README.md) and [RESTORE](RESTORE.md) before any import. Old owner consent is not transferable; messaging, forwarding, cleanup, recovery and command execution stay inactive until separately authorized and qualified.
- Review/admit changed instructions and reference closure in the target profile. Public publication is not installation or activation and does not override official-source policies.
- Existing queued/approved tasks are not silently rewritten or re-approved. Material proposal changes require a new exact-scope decision. Use a fresh session or native profile-scoped prompt refresh for ongoing sessions when activating reviewed instructions.
- Native candidate scans of both bundled skills returned safe/allowed with zero findings. Fresh local no-write behavioral fixtures covered routing, optional output and handoff edge cases; these do not prove actual GitHub publication or live restored Discord operation.
- Offline contracts check versions, inventory/manifest identity, closure, inactive defaults, privacy patterns, documented scope and ZIP roundtrip. Read actual PR checks for exact-head remote results.
- No new release/tag/assets, live deployment, cutover, authenticated media acceptance, rollback or credential migration is performed by this PR. Review/merge and any later release remain separate states.
