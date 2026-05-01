# Worklog

## Goal

Issue #617: OAuth provider index and callback guidance should be easy to follow from installation, FAQ, and provider-specific guides.

## Assumptions

- Scope is documentation only.
- No provider implementation, callback handler, or new provider changes are required.
- Linked Project status / priority is N/A because `gh issue view` returned no project items for #617.

## Checklist

- [x] Confirm live issue selection and related PR state.
- [x] Claim issue #617.
- [x] Align OAuth provider index with provider guide links and callback examples.
- [x] Standardize callback guidance in Google / GitHub / Discord guides.
- [x] Link installation / FAQ back to the OAuth provider guide.
- [x] Run targeted documentation verification.
- [x] Self-review diff.

## Verification Commands

- `rg -n "callback|provider|self-hosted|installation|FAQ" docs/guides/oauth/index.md docs/guides/oauth/*.md docs/installation.md docs/help/faq.md`

## Completed

- Live selection chose #617 from normal `codex:queue`.
- `codex:claimed` was applied.
- Temporary worktree was created from `origin/main`.
- OAuth index now lists local and production callback URL examples per provider.
- Google / GitHub / Discord guides now share a `Callback URL の登録値` section.
- Installation and FAQ now link back to the OAuth first-setup order.
- `rg -n "callback|provider|self-hosted|installation|FAQ" ...` completed successfully.
- `docker run --rm -v "$PWD":/docs squidfunk/mkdocs-material:latest build --strict` completed with `MKDOCS_STATUS=0`.
- `git diff --check` completed successfully.
- Self-review confirmed the change is docs/worklog only and does not modify provider implementation.

## Remaining

- PR creation and issue transition.

## Blockers

- None.
