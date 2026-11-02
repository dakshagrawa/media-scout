# Optional native Instagram thread naming patch

This archived patch modifies Hermes's existing Discord adapter/title mixin and adds tests/docs. It is not a custom service, plugin installer, general platform-permission change or an upstream release. Applying it requires separate explicit authorization to modify that Hermes checkout; publishing this bundle does not activate anything.

Upstream code: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), MIT. Preserve its [license](UPSTREAM-LICENSE) and existing contributors' authorship. Patch authored for this deployment by Daksh Agrawal with Hermes Agent; original adapter/mixin context remains Nous Research/contributors' work.

See [manifest](manifest.json) for exact upstream base, local patch commit and bundle SHA-256. Default behavior is unchanged until the supported local option `platforms.discord.extra.auto_thread_media_ids` is enabled. One unambiguous valid Instagram URL yields instagram_<shortcode>, case-preserved; the semantic rename guard retains it. Non-Instagram, invalid or multiple-item input falls back normally; explicit rename remains available. Query/fragment are irrelevant to identity, not permission to discard request context elsewhere.

## Review and apply manually
Use a clean, isolated checkout at the manifest base. Inspect the full diff and run `terminal(command="git apply --check /PATH/TO/instagram-thread-names.patch")` from that checkout before any apply. The uppercase path is an operator-supplied argument, not a machine-local default. If it fails, stop; never force or blindly replay against an updated installation. After explicit approval, apply with normal Git, then rerun Hermes's native tests below in its supported test environment. Do not run these tests from this repository or assume the bundle parses means they passed.

Targeted native tests: tests/gateway/test_discord_auto_thread_media_ids.py, test_discord_auto_thread_rename_pin.py, test_discord_free_response.py and test_session_title_rename_lane.py. The reviewed deployment reported 64 passes across those files. Inspect current official test instructions and the supported activation path; avoid shared-gateway interruption. Enable only the intended profile, then verify a fresh real Discord thread retains the name after reply and reload. Remove the patch only with current work preserved and a verified rollback.

Upstream updates can replace this local behavior. Check for upstream support before adapting/reapplying. The public repository tests validate manifest integrity and patch syntax only, not runtime compatibility.
