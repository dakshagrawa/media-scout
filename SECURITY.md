# Security policy

This repository contains an executable native Hermes plugin, agent instructions
and documentation, not a hosted service. The plugin runs with host-user authority;
its logical claims and retention guards are not an operating-system sandbox.
Code and skills can create risk through unsafe commands, data collection,
secret exposure or overstated security boundaries. Review the plugin's
capabilities and keep public defaults inactive until separately authorized.

This policy applies to the standalone Media Scout repository
`dakshagrawa/media-scout`. The historical source repository
`dakshagrawa/hermes-workflows` remains separate.

## Reporting a concern

Do not publish credentials, exploit details, private data, or a working
proof-of-concept in an issue. Use GitHub's private vulnerability-reporting or
security-advisory flow for this repository when it is available. If that flow
is unavailable, contact the repository owner privately through GitHub and share
only the minimum reproducible detail.

Include the affected file and version, a concise impact statement, reproduction
steps that do not expose secrets, and a suggested mitigation if known.

## Handling reports

Reports are triaged by impact and reproducibility. A maintainer may publish a
sanitized fix summary after the affected guidance is corrected. This repository
makes no promise of a response time or of a particular disclosure timeline.

Never paste API keys, passwords, tokens, personal records, or private customer
content into an issue, pull request, test fixture, or skill file.
