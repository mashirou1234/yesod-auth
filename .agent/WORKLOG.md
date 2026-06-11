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

---

# Worklog

## Goal

Add an in-admin guided operation tutorial for the Streamlit admin panel, built with Bun inside Docker and served locally from the admin container.

## Assumptions

- The tutorial should feel like an operation walkthrough, not a documentation page.
- Driver.js can be used as a local, container-built JS tour library.
- Bun is a build-time dependency only; the runtime admin container remains Python/Streamlit based.
- The tutorial must not auto-run destructive actions such as session revocation or API mutation.

## Checklist

- [x] Inspect existing admin navigation, i18n, Docker, and static-serving setup.
- [x] Add Bun package metadata and a tour asset build script.
- [x] Add Docker multi-stage build using `oven/bun` for tour assets.
- [x] Add local Driver.js assets and admin tour JS/CSS outputs.
- [x] Add Streamlit static serving and JS injection into the parent document.
- [x] Add stable page IDs, query-param page sync, and tour anchors.
- [x] Add localized tour labels and step copy.
- [x] Run build/test verification.
- [x] Start the built admin container for browser confirmation.
- [x] Verify the tutorial in browser and self-review the diff.

## Verification Commands

- `docker run --rm -v "$PWD/admin":/app -w /app oven/bun:1.3.5 bun install`
- `docker run --rm -v "$PWD/admin":/app -w /app oven/bun:1.3.5 bun run build:tour`
- `docker build -t yesod-auth-admin-tour:local ./admin` (local Docker Hub metadata fetch for `python:3.11-slim` timed out; CI must validate the full image build)
- `docker run --rm -v "$PWD/admin":/app -w /app yesod-auth-admin-tour:local python -m unittest discover -s tests`
- `docker run --rm -v "$PWD/admin":/app -w /app yesod-auth-admin-tour:local python -m py_compile app.py tour_runtime.py i18n.py`
- `docker run --rm -p 8501:8501 -e ADMIN_USER=admin -e ADMIN_PASSWORD=admin -e ENVIRONMENT=DEV yesod-auth-admin-tour:local`
- Browser verification at `http://localhost:8501`
- `git diff --check`
- Security diff scan: `/tmp/codex-security-scans/yesod-auth/local-admin-tour-20260610T172144Z/report.md`

## Completed

- Bun/Driver.js setup and local static tour assets are implemented.
- Streamlit page navigation now uses stable page IDs required for page-crossing tutorial flow.
- Tour anchors and localized copy are in place.
- Bun asset generation succeeds with `oven/bun:1.3.5`; local full-image build is blocked by Docker Hub metadata timeout for `python:3.11-slim` and is left to CI.
- Browser verification confirmed login, tour launcher, first step, and cross-page transition to Users.
- Mounted current-tree `python -m unittest discover -s tests`, `python -m py_compile app.py tour_runtime.py i18n.py`, and `git diff --check` passed.
- Security review identified Driver.js `innerHTML` tour text sinks and suppressed the risk by escaping all tour strings before Driver.js receives them.
- Tour asset tests now guard source/static drift, stable page allowlist, markup-free tour translations, and escape coverage.
- MoSCoW queue analysis on 2026-06-11 JST classified `security-hardening` as Must, `product-hardening` and direct-contract `quality-devex` as Should, and broad architecture/refactor as Could.

## MoSCoW Queue Prioritization

- Live population: `codex:queue` 121, `codex:blocked` 0, `codex:priority + codex:queue` 0.
- Must: `security-hardening` 30件 plus operations issue #796 for weekly inventory hygiene.
- Should: `product-hardening` 30件 after security queue is reduced or when product semantics block a security acceptance condition.
- Should: `quality-devex` 30件 when it directly protects auth/session/webhook contracts; otherwise after product hardening.
- Could: `architecture` + `refactor` 30件 unless directly required for a Must/Should item.
- Next pull direction: start with #705 `[Backlog-120][SEC-30] 依存関係の脆弱性チェックを CI/手順に追加する`.

## Remaining

- None.

## Blockers

- None.
