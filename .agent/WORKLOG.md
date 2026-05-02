# Worklog

## Goal

Issue #627: Webhook delivery history should lead operators from API fields to troubleshooting without changing API behavior.

## Assumptions

- Scope is documentation only.
- No webhook implementation, API schema, or new admin endpoint changes are required.
- Linked Project status / priority is N/A because `gh issue view` returned no project items for #627.

## Checklist

- [x] Confirm live issue selection and project status.
- [x] Claim issue #627.
- [x] Align delivery history field meanings with troubleshooting terms.
- [x] Add a clear handoff from API docs to troubleshooting.
- [x] Confirm guide wording still matches API/troubleshooting.
- [x] Run targeted documentation verification.
- [x] Self-review diff.

## Verification Commands

- `rg -n "event_id|endpoint_id|attempt_count|delivery|troubleshooting" docs/api/webhooks.md docs/help/troubleshooting.md`
- `rg -n "配信履歴|event_id|endpoint_id|attempt_count|Webhook API|トラブルシューティング|self-hosted production callback" docs/api/webhooks.md docs/guides/webhooks.md docs/help/troubleshooting.md docs/help/faq.md docs/installation.md`
- `git diff --check`
- `docker run --rm -v "$PWD":/docs squidfunk/mkdocs-material:latest build --strict`

## Completed

- Live selection chose #627 from normal `codex:queue`.
- `codex:claimed` was applied and the temporary worktree was created from `origin/main`.
- `docs/api/webhooks.md` now explains how `event_id` / `endpoint_id` / `attempt_count` lead into troubleshooting.
- `docs/guides/webhooks.md` now tells operators to collect the same keys before moving from delivery history to recovery.
- `docs/help/troubleshooting.md` now has a delivery-history triage entry before symptom-specific webhook checks.
- `docs/help/faq.md` no longer uses a docs-internal relative link to repository README, which restored strict docs build success.
- Targeted `rg` checks, `git diff --check`, and strict MkDocs build completed successfully.
- Self-review confirmed the change is docs/worklog only and does not modify webhook API behavior.

## Remaining

- PR creation and issue transition.

## Blockers

- None.
