# Qualification for Media Scout 0.2.1 candidate

This is an **experimental Linux-only native plugin — incomplete and not production-ready**. Evidence below is separated by class; synthetic fixtures do not prove live extraction or operator review. This is not an official Nous endorsement.

## Candidate evidence and required re-verification

- Candidate 0.2.1 portable suite: **103 passed** in parent execution with `ResourceWarning` and pytest unraisable warnings promoted to errors. This covers the current source revision; subsequent code changes require a new run.
- Native Hermes **0.22.7** Plugin Doctor and `validate --json` must be rerun against this candidate. Historical 0.22.6 results below do not qualify 0.2.1.
- Candidate native SDK smoke evidence is synthetic Instagram and YouTube only. The captured media, receipts, evidence and review/task state are disposable harness data. The synthetic operator completion is unverified; `completion_note_retained=false`.
- No genuine owner live extraction, naming, reviewer decision, or exact-thread return has been demonstrated. No live Discord title was changed or independently read back.

## Historical evidence (0.2.0; not candidate qualification)

- Historical repository suite: 77 passed.
- Historical preservation check against tagged 0.1.0 source retained catalog identity, receipt bytes and active claim after 0.2.0 initialization; task/return bindings were not rewritten. This remains a historical claim, not a 0.2.1 migration test.
- Historical Hermes v0.22.6 Plugin Doctor, native validation, and ten-platform synthetic SDK/queue fixtures passed as then reported. Those fixtures described retained synthetic completion notes; that behavior is not current candidate evidence (current harness reports `completion_note_retained=false`).

All SDK scenarios use synthetic IDs/evidence and test-only permission, not real owner events or consent. They start no real Discord connection, extraction, inference, dispatcher or notifier. Supported CLI output and fixture strings alone do not prove runtime behavior.

## Reproduce

Use the ordinary repository environment for portable contracts (the historical upgrade regression depends on repository tag history):

```bash
bash scripts/run_tests.sh -q
```

Prepare the proper official Hermes v0.22.7 runtime/developer environment according to its supported workflow; use its interpreter and CLI, never a similarly named JavaScript executable. Do not install dependencies merely to reproduce portable checks. Native doctor/validation require the official environment; use supported `--ci` and `validate --json` modes. The SDK matrix is reserved for the parent after the source is frozen:

```bash
hermes plugins doctor ./plugins/media-scout --ci
hermes plugins validate ./plugins/media-scout --json
python scripts/verify_media_scout_native.py --sdk PATH_TO_HERMES_V0_22_7_CHECKOUT \
  --platforms instagram,youtube,threads,tiktok,snapchat,x,reddit,facebook,vimeo,bluesky
```

Use disposable state without credentials or a live dispatch service. The harness creates/removes its own temporary profile/board. `--report PATH` writes incremental machine-readable scenario results. Native JSON uses bounded plugin-owned response files, not truncatable terminal stdout.

## Not established

- Live per-platform extraction, actual owner-authorized Discord rename/readback, real provider review and exact-thread conclusion delivery for this plugin.
- Genuine photo/carousel/long-video completeness, expired/private-source access, outage/quota/stress reliability or a proposed-skill installation cycle.
- Native Windows/macOS runtime qualification; this experimental package remains Linux-only. Public-platform availability and access limits can block supported-source acquisition; recognition is not proof of availability or extraction.
- Bounded opt-out phrase support is not universal natural-language consent/opt-out understanding. Partial or blocked evidence must remain disclosed as such; it is not complete coverage.
- Exactly-once behavior across the plugin database/native queue or defense against a hostile host process replacing files.

Source recognition/extractor presence is not live acquisition. Opaque shares remain provisional. Native task bodies have their own retention; plugin cleanup cannot erase task copies, conversations, logs or backups. See [acceptance](ACCEPTANCE.md), [source forms and safe acquisition](skills/workflow/references/sources.md), and [effect disclosures](README.md#security-and-effect-disclosure).
