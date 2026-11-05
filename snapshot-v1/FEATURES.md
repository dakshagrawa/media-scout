# Feature inventory and preservation boundaries

| Capability | Preserved source / dependency | Captured behavior and qualification limit |
| --- | --- | --- |
| Owner-only Discord intake and separate threads | `config.example.yaml`, `profile/SOUL.md` | Bind your own owner/server/channel before connecting; never clone a bot login or unrelated profile. |
| Canonical media IDs and tracking-aware provenance | Evidence skill + `references/source-provenance.md` | Keep original URL/context; canonical identity is not source-authenticity proof. |
| Speech, sampled visuals, photo/carousel/OCR evidence | Evidence skill Extraction; `dependencies.json` | Local Whisper small CPU/int8, ffmpeg/ffprobe, downloader and profile-local OCR. No direct video input with captured Codex provider. Mixed-media coverage must be disclosed. |
| Durable records, reuse, revisits and corrected findings | Evidence skill record contract | Data is private; raw/evidence expiration is distinct from permanent summaries. No atomic multiwriter guarantee. |
| Separate Default review and private learning | Full primary review contract + routing reference | Automatic for eligible new owner submissions only after deployment consent. Explicit stop/local-only takes precedence; no historical bulk forwarding. |
| GitHub project-fit suggestions | Primary review contract + SOUL | Default inspects likely relevant repositories read-only, then recommends implement/investigate/save/reject; not limited to this plugin or checklist. |
| Issue/PR drafting | Full `media-to-github` skill, references and templates | Natural-language trigger; no need to resend known media or manually relay to Default. Exact public payload and owner approval required; Default publishes. No direct GitHub grant or automatic merge. |
| Readable original-thread conclusion | `response-format.md` | Regular text with recap and distinct final-result sections, not mandatory report attachments. |
| Canonical Instagram thread naming | Native Hermes dependency + repository `patches/media-thread-naming/` | Scout-only opt-in adapter setting. Patch applicability to the selected Hermes revision must be rechecked; public historical patch is not asserted to apply cleanly to every later revision. Exact captured adapter files are preserved privately. |
| Retention | Retention reference, original policy, safe overlay, cron definition | Source: bounded deletion enabled, 7-day cache / 90-day evidence; 100 records / 100 files / 50 MiB max. Import: report-only until disposable fixtures and owner consent. |
| Quota/reconnect and headless recovery | Recovery/routing references + recovery policy | Native best effort, 6-hour/100-message/3-dispatch/3-attempt reconnect bounds. No instant, lossless, exact-once or model-independent receipt guarantee. |
| Optional browser history reconciliation | Disabled cron definition | Disabled in source; real authenticated history access was not established. Browser remains isolated without the owner's signed-in Discord session. Existing bot connection is separate. |
| Central future-skill catalog | Primary contract watchlist schema | Default owns one permanent JSON, not an install queue. No recommendation or approval is fabricated during restore. Existing entries stay private. |
| Knowledge/wiki workflow | Evidence skill + enabled `llm-wiki` inventory | Preserve the local wiki data privately; acquire the official skill at captured version where available. No blind source-claim/user-memory ingestion. |
| Additional enabled tools/skills | Config toolsets + `skills-inventory.json` | Availability, model access, package admission and live operation are separate gates. Disabled package `watch-video` must not be run. |
| Existing private data and state | Separate private archive, not public assets | Includes library, bindings, Scout SQLite state, review-board SQLite state and local instructions. No credential-store export. Do not automatically dispatch old pending/blocked tasks. |

## Explicit differences caused by sanitization

- Personal names (except contributor credit), account/channel/server/message/task identifiers, machine home paths, real submission URLs and personal repository bindings become placeholders.
- Source active forwarding/deletion remains documented, while the import overlay disables them. This is an intentional safety gate, not removal of those features.
- Private conversations, media, proposals, approvals, routing bindings, watchlist entries and credential stores are absent publicly.
- Bundled/third-party skill identities and media Python packages are inventoried. Vendored models, OCR libraries, virtual environments, authenticated provider sessions and OS packages are **not** redistributed in public assets. Reconnect/reinstall through original authorized sources; do not delete the old runtime until the new one passes.
- The experimental native plugin source in the repository is preserved unchanged, but installing it is not required to recreate the captured instruction-only workflow and is not an automatic migration.

No claim is made that every historical test, photo/carousel variant, concurrent duplicate or provider outage has been re-qualified by creating this release. Unsupported guarantees remain unsupported, rather than being hidden by the snapshot.
