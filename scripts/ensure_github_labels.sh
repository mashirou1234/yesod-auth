#!/usr/bin/env bash
set -euo pipefail

dry_run=0
repo=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      dry_run=1
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--dry-run] [owner/repo]" >&2
      exit 1
      ;;
    *)
      if [[ -n "${repo}" ]]; then
        echo "Too many positional arguments." >&2
        echo "Usage: $0 [--dry-run] [owner/repo]" >&2
        exit 1
      fi
      repo="$1"
      shift
      ;;
  esac
done

repo="${repo:-${GH_REPO:-${GITHUB_REPOSITORY:-}}}"
if [[ -z "${repo}" ]]; then
  repo="$(git remote get-url origin 2>/dev/null | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\\.git)?$#\1#' || true)"
fi
if [[ -z "${repo}" || "${repo}" == http* || "${repo}" == git@* ]]; then
  if command -v gh >/dev/null 2>&1; then
    repo="$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || true)"
  fi
fi

if [[ -z "${repo}" ]]; then
  echo "Repository not found. Pass owner/repo as the first argument or set GH_REPO/GITHUB_REPOSITORY." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
  if [[ -z "${token}" ]]; then
    echo "gh CLI is unavailable and GH_TOKEN/GITHUB_TOKEN is not set; cannot sync GitHub labels." >&2
    exit 1
  fi
  export GITHUB_LABEL_SYNC_REPO="${repo}"
  export GITHUB_LABEL_SYNC_DRY_RUN="${dry_run}"
  python3 - <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

repo = os.environ["GITHUB_LABEL_SYNC_REPO"]
dry_run = os.environ["GITHUB_LABEL_SYNC_DRY_RUN"] == "1"
token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
encoded_repo = urllib.parse.quote(repo, safe="/")
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "User-Agent": "yesod-auth-codex-automation",
    "X-GitHub-Api-Version": "2022-11-28",
}

def request(method, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"https://api.github.com{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        print(f"GitHub API request failed: HTTP {exc.code} {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(body) if body else None

specs = [
    ("codex", "0E8A16", "managed by Codex"),
    ("codex-automation", "1D76DB", "created or updated by Codex automation"),
    ("codex:queue", "0E8A16", "managed by codex-orch"),
    ("codex:claimed", "0E8A16", "managed by codex-orch"),
    ("codex:blocked", "0E8A16", "managed by codex-orch"),
    ("codex:pr-opened", "0E8A16", "managed by codex-orch"),
]
existing = {item["name"] for item in request("GET", f"/repos/{encoded_repo}/labels?per_page=100")}
for name, color, description in specs:
    exists = name in existing
    action = "update" if exists else "create"
    if dry_run:
        print(f"would {action}: {name}")
        continue
    if exists:
        encoded_name = urllib.parse.quote(name, safe="")
        request("PATCH", f"/repos/{encoded_repo}/labels/{encoded_name}", {"new_name": name, "color": color, "description": description})
        print(f"updated: {name}")
    else:
        request("POST", f"/repos/{encoded_repo}/labels", {"name": name, "color": color, "description": description})
        print(f"created: {name}")
PY
  exit $?
fi

existing_labels="$(
  gh label list --repo "${repo}" --limit 200 --json name -q '.[].name' 2>/dev/null || true
)"

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"

  if grep -Fxq "${name}" <<<"${existing_labels}"; then
    if [[ "${dry_run}" -eq 1 ]]; then
      echo "would update: ${name}"
    else
      gh label edit "${name}" \
        --repo "${repo}" \
        --color "${color}" \
        --description "${description}" >/dev/null
      echo "updated: ${name}"
    fi
  else
    if [[ "${dry_run}" -eq 1 ]]; then
      echo "would create: ${name}"
    else
      gh label create "${name}" \
        --repo "${repo}" \
        --color "${color}" \
        --description "${description}" >/dev/null
      echo "created: ${name}"
    fi
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
