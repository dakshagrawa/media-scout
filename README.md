# Hermes Workflows

Reusable skills, a native plugin and portable workflow templates for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Use them to review websites or turn shared media into source-backed knowledge and considered recommendations.

Formerly `dakshagrawa/agent-skills`. The repository name changed, but its Git history and existing skill paths remain intact. See the [migration guide](MIGRATION.md) for updating remotes and existing references.

## Find what you need

Choose a reusable skill for one agent, or follow the Media Scout guide for a multi-profile deployment:

| Package | Use it for | Start here |
| --- | --- | --- |
| `production-web-checklist` | Review website strategy, design, content, accessibility, search visibility, privacy, security, performance and release evidence | [Skill instructions](production-web-checklist/SKILL.md) |
| `media-evidence-library` | Capture audiovisual evidence, reuse saved findings, preserve provenance and recall earlier media | [Skill instructions](media-evidence-library/SKILL.md) |
| Native Media Scout plugin | Capture trusted sources, create records, claim extraction work, persist evidence and route native review tasks | [Install, safety and qualification](plugins/media-scout/README.md) |
| Media Scout workflow | Configure native intake and reviewer profiles, source-thread delivery, learning notes and qualified retention | [Setup and operating guide](workflows/media-scout/README.md) |
| Optional Instagram naming patch | Give compatible native Discord auto-threads a case-preserving `instagram_<shortcode>` name | [Patch scope and compatibility](patches/media-thread-naming/README.md) |

Skills contain agent instructions. The native plugin puts bookkeeping into code and bundles a namespaced workflow skill; it does not replace acquisition engines, the queue or model reasoning. Workflows describe how native Hermes features work together. The optional patch changes upstream Hermes code only when you separately review and apply it; the plugin does not apply or require that patch.

## Install the native Media Scout extension

The [native plugin](plugins/media-scout/README.md) packages durable receipt/record creation, exclusive extraction claims, source-bound native review handoff and opt-in bounded retention. Its bundled `media-scout:workflow` skill guides actual media understanding. Use an immutable release commit through Hermes's native installer; review the code and configure your own owner/channel/guild, reviewer and consent before enabling it.

This early plugin release does not alter an existing Scout deployment, migrate private data or ship a bot token. Read its [acceptance and rollback contract](plugins/media-scout/ACCEPTANCE.md). GitHub publication and submission to the official catalog are separate from maintainer acceptance; this repository is not the official catalog.

## Review a website

Use `production-web-checklist` when building, auditing or preparing a website for release. It covers requirements, creative direction, working interface states, content, search engine optimization (SEO), accessibility, legal and privacy considerations, security and evidence-backed delivery.

Read the [skill](production-web-checklist/SKILL.md), give the agent your project context and review the findings against actual implementation evidence. The checklist is not legal advice, a security certification, a website generator or a guarantee of search performance.

## Turn shared media into knowledge

Media Scout separates acquisition from personalized reasoning. It supports a reference workflow for reels, videos, audio, photos, ordered carousels, articles and PDFs, subject to actual tool and source availability.

| Role | Responsibility |
| --- | --- |
| You | Share media, state your purpose and approve consequential changes |
| Scout | Identify the source, reuse or extract real evidence, save it, route review and relay the result |
| Default | Use authorized context to understand the material, evaluate claims, retain learning and consider optional skills or actions |

Once you explicitly enable standing review consent, the intended flow is:

1. Send one item per top-level intake message; continue follow-ups in its thread.
2. Scout checks the canonical record before downloading or analyzing again.
3. Scout saves actual speech, visual observations, source identifiers and coverage limits, then posts a non-blocking preview.
4. Scout automatically queues a versioned native reviewer task with verified return routing. No per-item forwarding prompt is needed in this enabled mode.
5. A separate Default worker session returns an answer, attributed learning note and any justified recommendations.
6. Scout relays the actual result in the original thread and retains searchable knowledge and task references.
7. If Default proposes a consequential change, Scout asks for separate approval of the exact action, target and version.

A submission can be for learning, research, an idea or project context. It does not need to produce a skill proposal or an action list. Sharing a source does not make its claims facts about you, and retained knowledge is not automatically injected into every existing chat.

Open the [workflow diagram](workflows/media-scout/workflow.html) by downloading the HTML file and opening it locally. It is self-contained; GitHub's file view displays source rather than running the diagram. Follow the [Media Scout setup guide](workflows/media-scout/README.md) for configuration and [acceptance checklist](workflows/media-scout/acceptance.md) for validation.

## Understand the consent boundaries

Public templates start inactive. Cloning this repository does not authorize or activate your deployment:

| Capability | Public default | Before enabling it |
| --- | --- | --- |
| Discord connection | Disabled | Configure private credentials, owner allowlists and the intended channel |
| Automatic Scout-to-Default review | Disabled | Record explicit standing authorization for new-submission review and verify source-thread return delivery |
| Evidence and cache deletion | Report-only | Qualify disposable deletion fixtures and record matching operator approval for the exact retention policy |
| Skill installation or other consequential changes | Not authorized | Obtain separate approval for the specific proposed action |
| Optional native naming patch | Not applied; option disabled | Check the exact Hermes base, review the patch and explicitly authorize applying it |

Item-specific `local-only`, stop, defer and reject instructions override standing review consent. Do not bulk-forward old records. Review consent does not authorize installations, purchases, code or configuration changes, publication, outreach or new services.

No package creates a custom service, daemon or installer. The instruction-only workflow does not form a filesystem sandbox or transactional lock; the native plugin adds transactional claims for cooperating callers, not an OS sandbox or a cross-system exactly-once guarantee. Follow native security admission and your own source restrictions. This repository is not the official Hermes skill catalog and does not override an official-source-only policy.

## Locate stored evidence

The instruction-only Media Scout reference uses a private `media-library/` under the active profile home. The native plugin instead uses profile-scoped `plugin-data/media-scout/`, deliberately outside its replaceable install directory. It does not migrate the older tree. These are runtime locations, not data included in this repository:

| Relative path | Contents | Retention target |
| --- | --- | --- |
| `records/<media_id>.json` | Concise summary, entities, coverage, source/thread/task links and retained learning | No automatic expiry |
| `evidence/<media_id>.md` | Detailed timecoded speech, visual findings, attributed claims and limitations | 90 days from explicit revisit, otherwise extraction |
| `cache/<media_id>/` | Raw media, audio, sampled images, contact sheets and standalone transcript exports | 7 days |
| `receipts/`, `reviews/`, `proposals/` | Source receipts, handoff packets and inert action proposals | Outside cache cleanup |

Default's task results and attachments use native Kanban storage. Conversation databases, operational logs and personal memory have separate lifecycles. Do not assume the media cache policy deletes them.

Pinned or active items, recent nested artifacts, unsafe paths and unknown metadata remain protected. A background lookup does not extend revisit dates. See the [storage contract](media-evidence-library/references/storage.md) and [bounded retention procedure](media-evidence-library/references/retention.md) for exact limits and exclusions.

## Adopt a skill or workflow

Use the official [skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) and your installation's native review process for a standalone skill. Top-level skill directories remain independently reviewable and versioned.

For Media Scout, follow the [deployment guide](workflows/media-scout/README.md) instead of copying files into a live profile. It covers profile isolation, admitted acquisition and transcription tools, the reviewer contract, native task subscriptions, owner consent, retention qualification and rollback.

Keep these setup rules:

- Do not copy a live profile, authentication files, private memory or deployed channel configuration.
- Do not overwrite a live `config.yaml` with an example; apply settings through supported Hermes setup and configuration commands.
- Review acquisition tools, models and third-party dependencies separately. This package installs none of them.
- Verify your own deployment. Source-deployment test counts do not establish that another installation works.

## Check compatibility and limitations

The reusable media skill is currently Linux-scoped because that is the reviewed deployment platform. Required repository checks run on Ubuntu with Python 3.10 and 3.13. macOS and Windows contract checks are available on demand; passing them does not establish a working media runtime on those systems.

The [acceptance document](workflows/media-scout/acceptance.md) separates actual source-deployment tests, synthetic integration fixtures and untested paths. Known reference-workflow limits include simultaneous duplicate submissions, quota/restart stress, complete real-world photo/carousel acquisition and a complete proposed-skill installation cycle. Use one item per top-level message rather than batching different reels into one thread.

Source access and direct video support depend on your tools and provider. Timestamped speech plus sampled visual inspection is not exhaustive frame-by-frame analysis. The optional naming patch is base-specific, not an upstream release; recheck compatibility after Hermes updates.

Native model-driven scheduling can be delayed by outages or exhausted quota. It does not guarantee all-history discovery, exactly-once processing or deletion deadlines.

## Navigate the repository

The repository keeps skill packages separate from deployment topology and optional upstream changes:

```text
production-web-checklist/       # Existing skill; installation path preserved
media-evidence-library/         # Media skill and supporting references
plugins/media-scout/            # Native extension, bundled skill and setup
workflows/media-scout/          # Setup, templates, diagram and acceptance
patches/media-thread-naming/    # Native patch, base, hash and upstream license
tests/skills/                  # Offline package and safety-contract tests
tests/plugins/                 # Offline plugin state, safety and queue tests
scripts/run_tests.sh            # Shared test entry point
.github/workflows/ci.yml        # Required Ubuntu checks; other OSes on demand
```

## Run the repository checks

Use Python 3.10 or newer and an isolated virtual environment. The checks require no Hermes credentials or live provider access.

On Linux or macOS, install the pinned test dependencies and run the same entry point as continuous integration (CI):

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
bash scripts/run_tests.sh -q
git diff --check
```

On Windows PowerShell, use the virtual environment's executable directly:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

The suite checks skill metadata, safety contracts, inactive JSON/YAML defaults, privacy patterns, relative links, patch integrity, self-contained HTML and native-plugin bookkeeping against disposable fixtures. It does not run real Discord, provider APIs or media extraction. The plugin's separate native SDK qualification is described in its acceptance guide; fixture cleanup is not production cleanup.

Pull requests and pushes to `main` run two Ubuntu jobs: Python 3.10 and 3.13. Both are required, and branch protection still requires an up-to-date branch. For the full six-job cross-platform matrix, open **Actions → test → Run workflow** and choose a branch. That manual run adds macOS and Windows without putting their runner queues on every pull request's critical path.

## Contribute and version changes

Keep changes on a branch and open a pull request (PR). Read [CONTRIBUTING.md](CONTRIBUTING.md), preserve authorship and existing package paths, and record public changes in [CHANGELOG.md](CHANGELOG.md).

Each skill's frontmatter version describes that package, not a deployed setup. Repository renames, documentation updates and template versions do not automatically upgrade private profiles or enable automation. For cleanup rollback, pause the configured native job and restore consistent policy, role and job guidance without overwriting newer media or decisions.

## Protect private data and preserve attribution

Follow [SECURITY.md](SECURITY.md). Exclude credentials, identifying runtime configuration, private media, transcripts, receipts, conversation history, logs and personal memory from commits, issues and pull requests. Public examples must remain portable and synthetic.

Repository content uses the [MIT License](LICENSE). The optional upstream-derived patch preserves [Nous Research's license](patches/media-thread-naming/UPSTREAM-LICENSE) and contributor attribution. Existing contributors' Git history remains intact.
