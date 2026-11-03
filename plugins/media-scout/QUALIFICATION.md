# Qualification for Media Scout 0.1.0

This is an **experimental native plugin**, not a production-qualified Discord/media deployment. It is a working extension with real SDK and queue qualification, not an extraction engine or an official Nous endorsement.

## Executed checks

- Repository offline suite: 59 tests passed, covering existing packages and plugin provenance, claims, evidence validation, retry/source safeguards, registered retention, privacy and packaging contracts.
- Actual Hermes v0.22.6 Plugin Doctor: discovery, manifest parsing, import and registration passed.
- Actual native catalog validation with `--install-deps`: all checks passed; security verdict `safe`, no warnings, no declared Python dependencies and no runtime core overrides.
- Actual SDK fixture through the registered hook/tool: source capture/replay, exclusive claim, registered cache, evidence save/readback/hash, blocked native task creation, subscription verification, persisted identity before release, retry reuse of the same task, native completion and retained completion note passed.

The SDK fixture uses synthetic source IDs and explicitly labeled synthetic evidence. Completion is an explicit synthetic operator action, **not** a model review. No Discord connection, source download, inference call, dispatcher or notifier is started. The live Scout is not migrated or enabled by these tests.

## Reproduce

Use the ordinary repository environment for portable contracts:

```bash
bash scripts/run_tests.sh -q
```

Prepare an isolated Hermes v0.22.6 SDK environment using its official PM developer workflow, with its `dev`/`test` groups and `discord` extra. Run the native checks with that environment's interpreter/CLI, never a similarly named JavaScript executable:

```bash
hermes plugins doctor ./plugins/media-scout --ci
hermes plugins validate ./plugins/media-scout --install-deps
python scripts/verify_media_scout_native.py --sdk PATH_TO_HERMES_V0_22_6_CHECKOUT
```

Use disposable state, no credentials, and no live dispatch service. The harness creates its own temporary profile/board and removes them afterward. Native task JSON is captured in bounded plugin-owned response files rather than relying on truncatable terminal stdout.

## Not established

- Real end-to-end Discord/provider/acquisition delivery for this new plugin.
- Real photo/carousel completeness, outage/quota/stress reliability or a proposed-skill installation cycle.
- Windows/macOS native runtime qualification; v1 is Linux-scoped.
- Exactly-once behavior across the plugin database and native queue, or protection against a hostile host process replacing files.

Native queue bodies carry a compact evidence copy and have their own retention. Plugin artifact cleanup does not erase native conversations, task bodies, logs or backups. See [acceptance and rollback](ACCEPTANCE.md) and [effect disclosures](README.md#security-and-effect-disclosure).
