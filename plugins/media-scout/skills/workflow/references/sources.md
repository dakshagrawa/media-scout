# Supported sources and acquisition paths

All sources use the same trusted owner receipt → durable record → exclusive evidence claim → native reviewer → original-thread return workflow. Only source identity, acquisition guidance and the generated thread title vary. Discord remains the transport; these are social-content sources, not new gateway bots.

## Platform matrix

| Source | Accepted content forms | Thread title prefix | Acquisition path |
| --- | --- | --- | --- |
| Instagram | `/reel/`, `/p/`, `/tv/` post permalinks | `instagram_` | Existing admitted Instagram tools or verified public media/browser evidence |
| YouTube | `watch?v=`, `youtu.be/`, `/shorts/`, `/embed/` | `youtube_` | Admitted yt-dlp/captions/STT and real visual inspection; do not ingest a playlist |
| Threads | `threads.com` or legacy `threads.net` `/@author/post/ID` | `threads_` | Public native web/browser text, attached images and permitted media; do not assume an Instagram-only helper supports Threads |
| TikTok | `/@author/video/ID`, `/@author/photo/ID`; known `vm`, `vt` and `/t/` shares | `tiktok_` | Admitted TikTok acquisition, actual audio/frames or ordered photo inspection |
| Snapchat | Public `/spotlight/ID` and `/t/` shares | `snapchat_` | Admitted Spotlight retrieval or public native browser evidence; never private Snaps/chats |
| X / Twitter | `/author/status/ID`, `/i/status/ID`, including known mobile aliases | `x_` | Public post text and attached media through admitted tools; distinguish post claims from linked content |
| Reddit | Post permalinks, `/comments/ID`, `redd.it/ID`; `v.redd.it` provisional media links | `reddit_` | Public post text, attached media and explicitly scoped context; not whole subreddit/comment harvesting |
| Facebook | Public reels, watch/video permalinks | `facebook_` | Admitted video extraction or public browser evidence; report login/access restrictions honestly |
| Vimeo | Numeric video permalinks and player embeds | `vimeo_` | Admitted finite-video extraction and actual audiovisual evidence |
| Bluesky | `bsky.app/profile/author/post/rkey` | `bluesky_` | Public post text, attached images or admitted video extraction; author-qualified identity |

The title is a safe, case-preserving, bounded platform/content identifier, not a creator-controlled caption. Long identifiers receive a deterministic hash suffix. Existing Instagram record hashes and stored receipts are preserved.

Known opaque share links are **provisional** (`*_share_*` names). Their token is not a verified post ID. Resolve them only through an admitted tool and record the actual final post URL/ID in evidence. Never assume two different shares or a share and a canonical permalink are already deduplicated. No network redirect resolution occurs inside the admission parser.

## Evidence, not a promise that every site downloads

The checked upstream [yt-dlp 2026.10.26 extractor tree](https://github.com/yt-dlp/yt-dlp/tree/2026.10.26/yt_dlp/extractor) contains dedicated modules for YouTube, Instagram, TikTok, Snapchat Spotlight, X/Twitter, Reddit, Facebook, Vimeo and Bluesky. Module presence is **not** a successful extraction test, and support changes with websites. Threads has no standalone `threads.py` module in that snapshot; use verified admitted capabilities or public web/browser evidence rather than claiming a universal downloader.

- Use only already admitted upstream tools and authorized source access. The plugin does not install extractors, model weights, account sessions or new services.
- For text-only posts, store actual retrieved text, author/context, substantive observations and explicit `kind="text"`, bounded nonempty `text_content` segments, matching `text_segments=len(text_content)` and `has_media=false` only when no attached media remains uninspected. A title/preview alone is not a read post.
- For pictures/carousels, preserve order and inspect each available image; state missing slides and OCR/legibility limits.
- For video/audio, retain actual timed speech and inspected visual coverage. Long videos require bounded clips/chunks or an explicitly approved acquisition budget, not automatic high-resolution multi-hour downloads. Sampled coverage remains partial.
- Keep meaningful timestamp/slide context in original URLs and compare it with saved evidence before reuse. Redirects or handle/DID changes do not prove semantic identity; preserve attribution and uncertainty.
- If a source is private, deleted, expired, blocked, login-only or unavailable to admitted tools, retain a truthful blocked/partial explanation. Do not bypass authentication, claim a preview is complete evidence or fabricate missing content.

Profiles, feeds, search results, standalone playlists, arbitrary redirects, private messages/Snaps, indefinite live streams and Reddit comment-level links are outside this release. LinkedIn, Pinterest and arbitrary federated instances are not added merely through a permissive generic-URL fallback.

## Naming permission

Thread naming uses only the public `ctx.platform_actions.set_thread_title` facade. It requires both the operator's `rename_threads` opt-in and native `gateway.platform_actions` consent. It is scoped to an actually captured owner/source/thread. Permission errors or naming failure never discard evidence or stop review. A stored `acknowledged` state means the native SDK accepted the change, not an independent remote title readback. Never edit Hermes core or widen bot/channel permissions as a workaround.
