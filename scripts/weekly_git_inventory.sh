#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

JST_DATE="$(TZ=Asia/Tokyo date +%F)"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
REMOTE_MAIN="origin/main"

if ! git rev-parse --verify "$REMOTE_MAIN" >/dev/null 2>&1; then
  git fetch origin main >/dev/null 2>&1 || true
fi

echo "## 週次Git棚卸し（${JST_DATE}）"
echo
echo "- Repository: $(basename "$ROOT_DIR")"
echo "- Current branch: ${CURRENT_BRANCH}"
echo
echo "### Working tree"
if [ -n "$(git status --porcelain)" ]; then
  git status --short
else
  echo "- clean"
fi
echo
echo "### Local branch summary"
git for-each-ref refs/heads \
  --sort=-committerdate \
  --format='- %(refname:short) | %(committerdate:short) | %(authorname) | %(subject)' \
  | head -n 20
echo
echo "### Ahead/behind vs origin/main"
if git rev-parse --verify "$REMOTE_MAIN" >/dev/null 2>&1; then
  git rev-list --left-right --count "${REMOTE_MAIN}...HEAD" \
    | awk '{printf("- ahead=%s behind=%s\n", $2, $1)}'
else
  echo "- origin/main が未取得のため未確認"
fi
echo
echo "### Remote branch candidates (merged into origin/main)"
if git rev-parse --verify "$REMOTE_MAIN" >/dev/null 2>&1; then
  git branch -r --merged "$REMOTE_MAIN" \
    | sed 's/^ *//' \
    | rg '^origin/codex/issue-' \
    | head -n 20 || true
else
  echo "- origin/main が未取得のため未確認"
fi
