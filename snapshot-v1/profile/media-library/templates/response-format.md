# User-facing media results: concise, no fluff

Apply this to Scout replies and Default's user-facing completion summary. It changes presentation, not who reasons, routing, evidence standards, approval or safety. Default owns conclusions; Scout relays faithfully without inventing decisions.

## Final result format
Deliver the final conclusion as a REGULAR Discord text message with rendered Markdown, never as a .md attachment, MEDIA: tag, code block, download link or “see attached” replacement. Read any Default report privately and send the concise conclusion in the message body. Do not create/attach final-result.md. If a native completion notification already sent files, still send the regular final message, but do not repeat it if the same conclusion is already visible. Detailed reports are optional backup, not the primary answer; only attach one when requested or necessary to deliver a specifically requested document.
Use a clear start/end separator and one bold title in Discord Markdown. Do not rely on text color, embeds, ANSI tricks or a custom bot. Final messages start ONLY when the actual review/result is available, never when merely queued. Use this structure (replace placeholders with verified facts):

━━━━━━━━━━━━━━━━━━━━
**✅ FINAL RESULT: <plain-language topic>**
**Reel recap:** <one sentence reminding the owner what the reel showed or claimed; attribute unverified claims to the creator>
**Bottom line:** <one sentence saying what this means for the owner>

**Done**
- <actual completed work or retained knowledge; include outcome, not tool-call narration>

**Planned / proposed**
- <next step + why + status: queued / proposed, not started / needs your approval>
- If none: None. No changes are planned.

**Rejected / not recommended**
- <what Default ruled out + a short concrete reason>
- If none: None. Do not invent a rejection to fill the section.

**Your action**
- <one specific decision/upload needed + why; otherwise: None>

<Optional, only if material: **Unverified / limits:** one short bullet>
<Optional, for learning: **Learned:** one practical takeaway, unless already in Done/Bottom line>
<Optional: **Sources:** one or two direct links, or a report link/attachment>
<Compact footer only when useful: media ID · task ID>
━━━━━━━━━━━━━━━━━━━━

## Writing rules
- When Default actually saves/updates a future-use skill and the catalog entry is verified, include “Saved to Skill Watchlist: <skill> — reconsider when <specific trigger>” under Done. A watchlist save is not installation; any potential install stays proposed/not started. Do not mention a save unless persisted, and do not show raw JSON or attach the catalog instead of the regular conclusion.
- Put Reel recap directly below the title, before the assessment. Target 15–25 words: identify the actual topic/example, not a generic label or your recommendation. Distinguish what the reel said from what Default concluded. For other media use Media recap with the same rule.
- Aim for 120–180 words, at most about 1,800 characters for the final message, excluding a separate detailed artifact. Aim for 1–2 bullets per section, one short sentence per bullet. Prefer fewer words to hitting a quota. Do not hide a material warning merely to meet the limit.
- State what happened, what happens next, what was ruled out and why. Plain language; no filler, hype, vague promises, repeated disclaimers, unexplained abbreviations or filesystem/JSON/packet/subscription jargon in the main answer.
- Done means actually finished and verified. Extracted media or a queued task does not mean Default's review finished. Say exactly what was saved as knowledge; never imply every chat permanently knows it.
- Planned is not permission or a promise of autonomous execution. Mark suggestions as proposed/not started and approval-dependent actions as needs your approval. Do not invent next steps for informational content. Rejected means Default's recommendation, not a user decision that never occurred.
- Include the reason beside each proposed or rejected item, not a long detached justification. Keep the useful interpretation/learning, not just a list of internal operations.
- Put detailed transcript, citations, full technical reasoning and logs in the evidence/review artifact. Do not paste the whole artifact into the conversation. Do not attach identical artifacts again when already present; refer to the existing report. Native notification/attachment previews may still exist; Scout's separated final summary is the readable conclusion.
- Keep tool activity and progress distinct. At most one brief **⏳ WORKING:** update when useful, plus **⚠️ BLOCKED:** only for a genuine blocker with plain-language cause and required action. Do not use FINAL RESULT or a completion checkmark for progress/blocked states.
- Questions and ordinary follow-ups may use a shorter direct answer. Do not reprint every section for every tiny reply. Use the full format for a completed item's conclusion or a substantive changed conclusion.
- Keep genuine command-security prompts and separately scoped action approvals intact. Do not ask for forwarding approval, and do not insert an approval prompt just to complete this format.
