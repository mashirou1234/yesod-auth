# Worklog

## Goal

Issue #629: Align Webhook failure classification between API docs and troubleshooting without changing API behavior.

## Assumptions

- Scope is documentation only.
- No webhook implementation, API schema, or new admin endpoint changes are required.
- Linked Project status / priority is N/A because `gh issue view` returned no project items for #629.

## Checklist

- [x] Confirm live issue selection and project status.
- [x] Claim issue #629.
- [x] Align `failure_reason` meanings with troubleshooting terms.
- [x] Add a clear handoff from API docs to troubleshooting.
- [x] Confirm FAQ / installation / troubleshooting wording still matches.
- [x] Run targeted documentation verification.
- [x] Self-review diff.

## Verification Commands

- `rg -n "failure_reason|missing_signature_header|timestamp_skew|hmac_mismatch|webhook_delivery_retry_exhausted|webhook-failure-reason-map" docs/help/troubleshooting.md docs/api/webhooks.md docs/help/faq.md docs/installation.md`
- `rg -n "Webhookが届かない|Webhook reload 障害|配信履歴から初動|署名検証に失敗する" docs/help/troubleshooting.md docs/api/webhooks.md docs/help/faq.md docs/installation.md`
- `git diff --check`
- `docker run --rm -v "$PWD":/docs squidfunk/mkdocs-material:latest build --strict --site-dir /tmp/yesod-auth-site`

## Completed

- Live selection chose #629 from normal `codex:queue`.
- `codex:claimed` was applied and the temporary worktree was created from `origin/main`.
- `docs/help/troubleshooting.md` now maps API `failure_reason` values to the first troubleshooting step.
- `docs/api/webhooks.md` now has stable anchors for retry-exhausted and signature failure classifications and links back to troubleshooting.
- `docs/help/faq.md` and `docs/installation.md` now send `failure_reason` cases to the same troubleshooting map.
- Targeted `rg` checks, `git diff --check`, and Docker MkDocs strict build completed successfully.
- Self-review confirmed the change is docs/worklog only and does not modify webhook API behavior.

## Remaining

- PR creation and issue transition.

## Blockers

- None.
