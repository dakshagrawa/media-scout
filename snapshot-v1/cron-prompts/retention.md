Stable v1 bounded retention cleanup for the media-scout profile. Load media-evidence-library, read
its references/retention-cleanup.md IN FULL and media-library/policy.json. Owner accepted
fixture-qualified bounded cleanup in the stable-version request. Only this exact private
media-library is in scope. Honor cleanup_mode; delete-expired allows verified expired evidence/cache
files only, while report-only forbids deletion. Use native tools and ordinary metadata/rm/rmdir
commands; no scripts/code_execution, recursive deletion, wildcard deletion, symlinks, outside-root
paths or other profiles. Preserve permanent records/summaries, sources, review history and user
dates; skip pinned/active/queued/unknown/unsafe/fresh nested cases. At most100 records/100
files/50MiB. Recheck exact paths and record state before mutation, verify targets absent and
protected data preserved, then update only verified cleanup-availability metadata. Write/read back
media-library/cleanup-report.md with actual UTC, exact deleted paths/bytes, skip reasons, truncation
and failures. Zero eligible means zero deletions. Do not forward media, install, purchase, alter
policies or create jobs. On uncertainty skip and report, never widen scope.
