#!/usr/bin/env bash
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required." >&2
  exit 1
fi

repo="${1:-${GH_REPO:-}}"
if [[ -z "${repo}" ]]; then
  repo="$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || true)"
fi

if [[ -z "${repo}" ]]; then
  echo "Repository not found. Pass owner/repo as the first argument or set GH_REPO." >&2
  exit 1
fi

existing_labels="$(
  gh label list --repo "${repo}" --limit 200 --json name -q '.[].name' 2>/dev/null || true
)"

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"

  if grep -Fxq "${name}" <<<"${existing_labels}"; then
    gh label edit "${name}" \
      --repo "${repo}" \
      --color "${color}" \
      --description "${description}" >/dev/null
    echo "updated: ${name}"
  else
    gh label create "${name}" \
      --repo "${repo}" \
      --color "${color}" \
      --description "${description}" >/dev/null
    echo "created: ${name}"
  fi
}

while IFS='|' read -r name color description; do
  ensure_label "${name}" "${color}" "${description}"
done <<'EOF'
codex|0E8A16|managed by Codex
codex-automation|1D76DB|created or updated by Codex automation
codex:queue|0E8A16|managed by codex-orch
codex:claimed|0E8A16|managed by codex-orch
codex:blocked|0E8A16|managed by codex-orch
codex:pr-opened|0E8A16|managed by codex-orch
EOF
