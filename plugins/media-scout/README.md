# Media Scout — native Hermes plugin

Turn an authorized Discord media submission into a durable source receipt, protected extraction record and source-bound native reviewer task. The plugin bundles `media-scout:workflow` for audiovisual evidence and review discipline.

**Early release.** This is a native bookkeeping extension, not a downloader, STT engine or replacement agent framework. It does not install media tools, create a Discord bot, configure your credentials or migrate an existing Scout. Review the qualification and limitations below before enabling it. Catalog submission is not official acceptance or a code audit.

## What runs as code

- Capture one supported Instagram post/reel from the actual authorized native `post_gateway_admission` event, after gateway admission. Internal wakes, control traffic and rejected senders do not become new owner submissions.
- Preserve original URL, exact owner, parent/guild/thread/message identity and case-sensitive canonical media identity. A missing record selects creation, not a false blocker.
- Persist receipts and summaries in profile-scoped native plugin storage; claim extraction transactionally so cooperating callers cannot start the same extraction concurrently.
- Save bounded source-attributed evidence with explicit coverage, then create/reuse a native Kanban review task: blocked creation → source subscription → verification → persisted links → release.
- Reuse the original review source for retries instead of redirecting results to a later thread. Read actual native task state rather than inventing a completion.
- Plan retention separately; apply only explicitly enabled, bounded, unchanged plans for registered owned artifacts. Permanent summaries, active work and pinned items are protected.

Hermes's native tools still do acquisition/transcription/vision. The reviewer uses its own authorized profile context for reasoning and optional recommendations. Consequential actions always need separate approval. The plugin never starts an extra daemon or replaces Hermes core functions.

## Install and configure

Use the official [Hermes plugin installer](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins), review the immutable release source and install **disabled** first:

```bash
hermes plugins install dakshagrawa/hermes-workflows/plugins/media-scout --ref FULL_40_CHARACTER_RELEASE_COMMIT --no-enable
hermes plugins show media-scout
```

Replace the commit placeholder with the full source commit in the GitHub release notes. The installer pin is a commit, not a tag or branch. In a separate intake profile, run the same commands with its native `-p PROFILE` selection. This repository is third-party authored; it does not override an official-source-only installation policy. An official catalog name becomes available only after maintainer acceptance.

Configure your own owner, guild and parent channel through Hermes's native setup/configuration UI or `hermes config set`, in this plugin's `plugins.entries.media-scout.settings` namespace. Use [the manifest](plugin.yaml) as the authoritative field/default schema. Never paste bot credentials into the examples or overwrite a working config file. Configure your Discord connection/allowlists independently using [Hermes Discord setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord).

Create the intended native board explicitly if it does not already exist, for example `hermes kanban boards create media-review`, in the same scoped setup. Configure native Discord auto-thread creation so the admitted source has an actual isolated thread; this plugin does not manufacture one. The review worker is capped at ten minutes and one attempt, with a local-only completion contract.

Defaults deliberately do not authorize automatic review or deletion. Set your own reviewer profile/board; enable automatic review only after recording explicit standing **review-only** consent. Enable cleanup only after qualifying its plans against disposable state. Creator text, reactions, silence and ambiguous replies never grant either consent.

After source/capability review and configuration:

```bash
hermes plugins enable media-scout
hermes plugins doctor media-scout --ci
```

Use [the companion role example](examples/scout-SOUL.md) to direct the intake profile to load `skill_view(name="media-scout:workflow")` for supported submissions. Plugin skills are read-only and namespaced, not copied over your personal skills. Enabling a plugin does not grant it broad permissions over unrelated profiles.

## Use

Send **one supported Instagram source per top-level message** in the configured intake channel. The native adapter owns thread creation. Keep clarifications in that thread. The original parent starter need not appear inside thread history: the trusted admission receipt supplies provenance before model processing.

The intake agent loads the bundled workflow and uses `media_scout` actions. Consult its current tool schema for exact argument fields:

| Action | Purpose |
| --- | --- |
| `status`, `get` | Inspect configured capture/item state |
| `claim` | Claim missing extraction work exclusively |
| `save` | Persist actual evidence, coverage and retained summary |
| `review` | Create/reuse and safely release an authorized native review |
| `review_status` | Read actual native state/result |
| `cleanup_plan` | Inspect bounded registered expiry candidates |
| `cleanup_apply` | Apply the authorized exact unchanged plan |
| `register_cache` | Register an actual contained cache file under the current claim |
| `pin` | Explicitly protect or unpin a known item |
| `release` | Explain the owner-only stopped-writer recovery command |

Do not start extraction without the claim, label a caption as a watched reel or a sampled frame set as exhaustive coverage. Private/deleted/login-restricted sources may remain partial or blocked. Local-only, stop, defer, reject and no-review/no-forward instructions override standing review. A genuine missing dependency or transport failure is reported precisely, not silently fixed by installing packages.

To recover an interrupted claim, first stop its old native writer, then the owner must issue `/media-scout release MEDIA_ID --writer-stopped` in the configured intake thread. The model-facing `release` action cannot attest on the owner's behalf. The `pin` action requires an explicit boolean; `register_cache` requires the current claim and an existing file within that item's returned cache directory.

## Storage and lifecycle

Runtime state lives in `plugin-data/media-scout/` under the **active profile home**, outside the installed plugin tree. It survives normal plugin updates/removal; back it up privately. It is separate from the older instruction-only workflow's `media-library/`. Do not import that live tree by copying files or rewriting records.

Receipt/catalog summaries and native task references do not expire automatically. The retained review note is bounded and stored separately from detailed evidence. Native task bodies necessarily carry a compact evidence copy to the reviewer and have their own retention lifecycle; deleting a plugin artifact does not delete that native queue copy. Registered cache/evidence may expire under the configured policy; no wildcard/recursive directory deletion or unregistered-file cleanup is performed. Status lookups do not pretend a new user revisit occurred. An interrupted claim is not taken over merely because a timer elapsed; stop the old writer before explicit recovery.

Disabling/removing the plugin does not cancel already released native tasks. Stop/cancel those using Hermes's native queue controls if needed. Do not delete persistent state as an uninstall shortcut.

## Security and effect disclosure

- **Credentials:** no plugin-specific API keys, no reads of another client's OAuth, browser session or credential store. Discord/model/extraction credentials remain with native Hermes or admitted tools.
- **Network:** no HTTP client, telemetry, LLM call or network activity in registration/capture. Native media/reviewer tools may contact sources and use the operator's configured quota.
- **Native commands:** review operations dispatch fixed, validated, safely quoted Hermes Kanban CLI commands through `ctx.dispatch_tool("terminal", ...)`; existing host approvals remain in force. These commands write native tasks/subscriptions in the active profile's configured board.
- **Files:** reads/writes are plugin-owned state/evidence plus packaged instructions, not arbitrary caller paths. Detailed evidence can contain private material; protect the profile and backups.
- **Processes:** no custom background service, direct subprocess executor, self-updater or replacement Discord client. Native Kanban remains responsible for scheduling and notification/wake.
- **Consent:** automatic review and retention are independently opt-in. No tool action approves software installation, account mutation, purchases, publication, outreach or configuration changes.
- **Trust model:** a native Python plugin runs with the host user's authority, not in a filesystem sandbox. Claims/cleanup protect cooperating callers, not a hostile process replacing files under the profile.

## Compatibility and qualification

The v0.1.0 native runtime is Linux-scoped and requires Hermes >=0.22.6. It targets documented Hermes native plugin APIs: `post_gateway_admission`, `ctx.register_tool`, `ctx.register_skill`, `ctx.get_config`, `ctx.dispatch_tool`, `plugin_data_dir` and `plugin_db`. See [acceptance](ACCEPTANCE.md) for the exact tested release and boundary distinctions.

V1 supports one configured owner/profile and a single distinct supported Instagram item per submission. It does not identify semantic reposts, batch different sources into one thread, replace extraction engines, implement all-history discovery or promise cross-system exactly-once execution. A native idempotency key plus persisted claim/recovery protects retries; SQLite and the queue are not one transaction. Source access, provider quota, native delivery and model behavior can still fail.

The archived Instagram naming patch elsewhere in this repository is **not applied or required by this plugin**. No runtime core overrides ship here. Future title integration must use public platform actions with explicit capability consent.

## Development

Run portable offline tests from the repository root:

```bash
bash scripts/run_tests.sh -q
```

On a separately prepared matching Hermes SDK environment, run the actual native gates:

```bash
hermes plugins doctor ./plugins/media-scout --ci
hermes plugins validate ./plugins/media-scout --install-deps
```

Doctor/validation execute plugin registration; review code first. Use only disposable profile state and no credentials for tests. See [acceptance](ACCEPTANCE.md) for native queue, replay, failure and cleanup requirements. Public tests use synthetic data, never private media or deployed identifiers.

## License and source

[MIT](LICENSE). Author: Daksh Agrawal (`dakshagrawa`), with Hermes Agent. Source: [hermes-workflows](https://github.com/dakshagrawa/hermes-workflows). Hermes itself is developed by Nous Research; this plugin is not a Nous product or endorsement.
