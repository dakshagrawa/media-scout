# Qualification for Media Scout 0.2.0

This is an **experimental native plugin — incomplete, not production-ready**. It has real SDK/queue qualification, not a universal extraction engine or an official Nous endorsement. A synthetic fixture does not prove a live social site can be downloaded.

## Executed checks

- Repository offline suite: **77 passed**, including legacy package contracts, strict multi-platform identity/aliases, hostile/ambiguous source rejection, case preservation, bounded titles, provenance/claims/coverage, text-only evidence, retention, native retry/source guards and inert defaults.
- A catalog created by the actual tagged **0.1.0 source** retains its original Instagram media ID, receipt bytes and active claim after 0.2.0 initialization. Existing native task/return bindings are not rewritten.
- Actual **Hermes v0.22.6** Plugin Doctor: discovery, manifest, import and real tool/hook registration passed.
- Actual native validation: security verdict `safe`, no warnings, no Python dependencies or runtime core overrides.
- Actual SDK/queue fixtures passed for **all 10 sources**: Instagram, YouTube, Threads, TikTok, Snapchat, X/Twitter, Reddit, Facebook, Vimeo and Bluesky. Each exercised trusted source capture/replay, exclusive claim, registered cache, evidence/hash readback, real blocked native task creation, verified original-source subscription/release, retry reuse, explicit synthetic completion and retained completion note.
- The same fixtures awaited the real public platform-action facade on the caller's event loop with a **synthetic adapter** and test-only capability grant. Every expected platform title received an SDK acknowledgement. No actual Discord title was changed or independently read back.

Fixtures contain synthetic source IDs and labeled synthetic evidence. Task completion is an explicit synthetic operator action, **not** a Default model review. No real Discord connection, source extraction, inference, dispatcher or notifier is started. The live Scout is unchanged.

## Reproduce

Use the ordinary repository environment for portable contracts (the upgrade regression requires repository tag history):

```bash
bash scripts/run_tests.sh -q
```

Prepare an isolated official Hermes v0.22.6 SDK environment using its PM developer workflow, with `dev`/`test` groups and the `discord` extra. Use that environment's interpreter/CLI, never a similarly named JavaScript executable:

```bash
hermes plugins doctor ./plugins/media-scout --ci
hermes plugins validate ./plugins/media-scout --install-deps
python scripts/verify_media_scout_native.py --sdk PATH_TO_HERMES_V0_22_6_CHECKOUT \
  --platforms instagram,youtube,threads,tiktok,snapchat,x,reddit,facebook,vimeo,bluesky
```

Use disposable state without credentials or a live dispatch service. The harness creates/removes its own temporary profile/board. `--report PATH` writes incremental machine-readable scenario results. Native JSON uses bounded plugin-owned response files, not truncatable terminal stdout.

## Not established

- Live per-platform extraction, actual Discord rename/readback, real provider review and exact-thread conclusion delivery for this plugin.
- Genuine photo/carousel/long-video completeness, expired/private-source access, outage/quota/stress reliability or a proposed-skill installation cycle.
- Native Windows/macOS runtime qualification; this experimental package remains Linux-only.
- Exactly-once behavior across the plugin database/native queue or defense against a hostile host process replacing files.

Source recognition/extractor presence is not live acquisition. Opaque shares remain provisional. Native task bodies have their own retention; plugin cleanup cannot erase task copies, conversations, logs or backups. See [acceptance](ACCEPTANCE.md), [source forms and safe acquisition](skills/workflow/references/sources.md), and [effect disclosures](README.md#security-and-effect-disclosure).
