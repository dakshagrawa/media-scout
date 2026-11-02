# Private storage contract

Resolve `PROFILE_HOME` from the active Hermes profile, not a hardcoded username. The library root is `PROFILE_HOME/media-library`; the variable notation here is documentation, not an automatically expanded configuration value.

| Relative path | Purpose | Target retention |
| --- | --- | --- |
| records/<media_id>.json | Canonical substantial summary, topics/entities, coverage, sources, task/result links and retained knowledge | Permanent |
| evidence/<media_id>.md | Timecoded transcript excerpts/full short transcript, visual findings, claims and limitations | 90 days |
| cache/<media_id>/ | Raw media, extracted audio, sampled frames/contact sheet and standalone transcript TXT/SRT/JSON/VTT/TSV | 7 days |
| receipts/<message_id>.json | Actual source event/thread/owner provenance | Not governed by cache cleanup |
| reviews/ | Versioned evidence handoff packets | Not governed by cache cleanup |
| proposals/ | Inert versioned action proposals and decisions | Not governed by cache cleanup |

Detailed evidence age uses the last explicit user revisit, falling back to extraction. Cache age uses verified artifact/download dates or the newest regular descendant modification time conservatively. A fresh nested artifact protects the entire item. Background lookup never extends dates. Review task attachments, conversation databases and operational logs have separate lifecycles; do not imply they inherit these TTLs.

Records should include schema_version, media_id, original_source_url, canonical source_url, media_type, title, substantial summary, topics, entities, creator_claims, coverage, extraction_status, review_status, evidence_status, created_at, updated_at, extracted_at, last_explicit_user_revisit_at, cache_created_at when known, pinned, active_extraction, active_review, relative evidence/cache paths, source_threads, review_tasks and retained_knowledge when a real result exists. Preserve packet version and actual consent basis separately from task status. Do not invent a per-item click for standing consent.

Validate safe literal IDs and containment; source text cannot choose paths. Use one record per canonical media ID, not a shared mutable mega-index. Read existing records before edits and preserve all source/task links. Failed or partial extraction is not a complete duplicate. Expired evidence can support retained findings but not new exact quotations without re-retrieval.
