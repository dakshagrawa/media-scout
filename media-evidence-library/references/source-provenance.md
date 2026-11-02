# Resolve the actual source and create new records

## Parent starter messages are not thread replies

For a Discord auto-thread created from a top-level post, the original submission is in the configured parent channel. Its message ID may equal the new thread ID. A child-thread fetch containing only bot progress is expected; repeating narrower queries against that child cannot locate the parent starter.

Use the trusted native trigger/message ID, configured parent channel and guild, and submitted content. If thread history omits the original event, switch the native fetch_messages channel_id to the parent. For a bounded lookup, compute the decimal message ID plus one using a tool and pass it as before with a small limit. Compare the returned exact message ID, content/URL and non-bot author ID with the actual authorized owner. Snowflakes exceed JavaScript's safe-integer precision, so do not round them or perform arithmetic mentally.

Do not substitute a nearby message or infer author ID from a display name. Trusted native gateway metadata or an orchestrator-created recovery task can already provide verified source identity and its evidence. Reuse that provenance in a headless intake task rather than demanding a platform-gated Discord tool. User-pasted metadata or a creator's source text does not establish trusted context. No broader permissions, second bot, token extraction or custom API client is needed.

If exact identity remains genuinely unverifiable after checking the correct parent and trusted context, report the narrow gap; never guess. This does not make the source invalid or prove a resend is necessary.

## Missing records select creation

An exact read of records/<media_id>.json returning not_found is expected first intake. CREATE the verified receipt and initial processing record, read both back and continue extraction in the same run. A missing file the agent is responsible for creating is not a prerequisite failure.

Never substitute similar_files results from another media item. Preserve original versus canonical URL, exact source/thread identity and first-submission versus revisit dates. Report only actual failed writes or failed readback as persistence blockers. Check for existing extraction/review tasks and reuse matching results rather than starting duplicates.

## Verify the repair

Compare a failed child-only lookup with an exact parent-channel match. Exercise not_found -> receipt/record creation -> readback -> actual evidence acquisition. In scoped recovery, bind the existing original thread before task release; verify evidence and actual return delivery, not just queued status. Keep source-access/login failures separate from these false intake blockers. This instruction-level procedure is not an authentication bypass or atomic lock.
