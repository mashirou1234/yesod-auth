#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../../scripts/secret_env.sh
source "${ROOT_DIR}/scripts/secret_env.sh"
orch_load_standard_secret_envs "${ROOT_DIR}"

HOST="${WOODPECKER_HOST:-https://mashirou.stream}"
REPO_ID="${WOODPECKER_REPO_ID:-}"
REPO_FULL_NAME="${WOODPECKER_REPO:-}"
TOKEN="${WOODPECKER_TOKEN:-}"
FORMAT="summary"
USE_NETRC=1
STRICT=0
PIPELINE_NUMBER=""
COMMIT_SHA=""
PIPELINE_URL=""
SELECTION_SOURCE="latest"
SELECTION_NOTE=""

usage() {
  cat <<'EOF'
Usage:
  get-woodpecker-pipeline-status.sh [options]

Options:
  --host <url>       Woodpecker host (default: $WOODPECKER_HOST or https://mashirou.stream)
  --repo-id <id>     Repository ID (default: $WOODPECKER_REPO_ID)
  --repo <owner/repo>
                     Repository full name for repo lookup (default: $WOODPECKER_REPO)
  --pipeline-id <n>  Pipeline number shown in Woodpecker UI (/repos/<repo>/pipeline/<n>/...)
  --pipeline-number <n>
                     Alias of --pipeline-id
  --pipeline-url <url>
                     Extract host / repo-id / pipeline-id from a Woodpecker UI URL
  --status-url <url> Alias of --pipeline-url
  --commit <sha>     Resolve the newest exact-match pipeline for a commit
  --token <token>    Woodpecker Personal Access Token (default: $WOODPECKER_TOKEN)
  --json             Print raw JSON response
  --summary          Print a compact summary (default)
  --strict           Exit with code 3 unless the selected pipeline status is "success"
  --no-netrc         Do not use ~/.netrc for Basic auth
  -h, --help         Show this help

Examples:
  export WOODPECKER_TOKEN='...'
  ./get-woodpecker-pipeline-status.sh --repo-id 1
  ./get-woodpecker-pipeline-status.sh --repo-id 1 --json | jq
  ./get-woodpecker-pipeline-status.sh --repo mashirou1234/MIYABI --commit <sha>
  ./get-woodpecker-pipeline-status.sh --pipeline-url https://mashirou.stream/repos/6/pipeline/28/1
  ./get-woodpecker-pipeline-status.sh --host https://mashirou.stream --repo-id 1 --strict
EOF
}

die() {
  echo "[error] $*" >&2
  exit 1
}

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    die "jq is required for this mode"
  fi
}

api_get() {
  local endpoint="$1"
  local body_file="$2"
  local http_code

  http_code="$(
    curl "${curl_args[@]}" \
      -o "${body_file}" \
      -w '%{http_code}' \
      "${endpoint}"
  )"

  if [[ "${http_code}" != "200" ]]; then
    echo "[error] API request failed: HTTP ${http_code}" >&2
    if [[ -s "${body_file}" ]]; then
      echo "[error] response body:" >&2
      sed -n '1,40p' "${body_file}" >&2
    fi
    if [[ "${http_code}" == "401" ]]; then
      echo "[hint] ~/.netrc の Basic 認証と WOODPECKER_TOKEN の Bearer 認証を確認してください" >&2
    fi
    exit 1
  fi
}

parse_pipeline_url() {
  local url="$1"

  if [[ "${url}" =~ ^(https?://[^/]+)/repos/([0-9]+)/pipeline/([0-9]+)(/.*)?$ ]]; then
    HOST="${BASH_REMATCH[1]}"
    REPO_ID="${BASH_REMATCH[2]}"
    PIPELINE_NUMBER="${BASH_REMATCH[3]}"
    SELECTION_SOURCE="pipeline-url"
    return 0
  fi

  die "invalid pipeline/status url: ${url}"
}

resolve_repo_id() {
  local lookup_file encoded

  [[ -n "${REPO_ID}" ]] && return 0
  [[ -n "${REPO_FULL_NAME}" ]] || return 0

  require_jq
  lookup_file="$(mktemp)"
  encoded="${REPO_FULL_NAME//\//%2F}"
  api_get "${HOST}/api/repos/lookup/${encoded}" "${lookup_file}"
  REPO_ID="$(jq -r '.id // empty' "${lookup_file}")"
  REPO_FULL_NAME="$(jq -r '.full_name // empty' "${lookup_file}")"
  rm -f "${lookup_file}"

  [[ -n "${REPO_ID}" ]] || die "failed to resolve repo id from --repo ${REPO_FULL_NAME}"
}

select_pipeline_by_commit() {
  local list_file selected_file exact_count selected_event selected_number

  require_jq
  list_file="$(mktemp)"
  selected_file="$(mktemp)"
  api_get "${HOST}/api/repos/${REPO_ID}/pipelines?commit=${COMMIT_SHA}" "${list_file}"

  exact_count="$(jq -r --arg commit "${COMMIT_SHA}" '[.[] | select((.commit // "") == $commit)] | length' "${list_file}")"
  if [[ "${exact_count}" == "0" ]]; then
    rm -f "${list_file}" "${selected_file}"
    die "no exact-match pipeline found for commit ${COMMIT_SHA} in repo ${REPO_ID}"
  fi

  jq --arg commit "${COMMIT_SHA}" '
    [
      .[]
      | select((.commit // "") == $commit)
    ]
    | sort_by(
        (if .event == "pull_request" then 0 elif .event == "push" then 1 else 2 end),
        -(.number // 0),
        -(.id // 0)
      )
    | .[0]
  ' "${list_file}" > "${selected_file}"

  selected_event="$(jq -r '.event // "unknown"' "${selected_file}")"
  selected_number="$(jq -r '.number // "unknown"' "${selected_file}")"
  SELECTION_SOURCE="commit"
  SELECTION_NOTE="commit exact match ${COMMIT_SHA} (matches=${exact_count}, selected_event=${selected_event}, selected_number=${selected_number})"

  api_get "${HOST}/api/repos/${REPO_ID}/pipelines/${selected_number}" "${body_file}"
  rm -f "${list_file}" "${selected_file}"
}

print_workflow_failures() {
  if ! command -v jq >/dev/null 2>&1; then
    return 0
  fi

  if jq -e '
    (
      [.workflows[]? | select((.state // "") != "success")]
      +
      [.workflows[]?.children[]? | select((.state // "") != "success")]
    ) | length > 0
  ' "${body_file}" >/dev/null 2>&1; then
    echo
    echo "workflow_failures:"
    jq -r '
      (
        [.workflows[]? | select((.state // "") != "success") | {
          kind: "workflow",
          name: (.name // "-"),
          state: (.state // "unknown"),
          error: (.error // ""),
          exit_code: null
        }]
        +
        [.workflows[]?.children[]? | select((.state // "") != "success") | {
          kind: (.type // "step"),
          name: (.name // "-"),
          state: (.state // "unknown"),
          error: (.error // ""),
          exit_code: (.exit_code // null)
        }]
      )[]
      | "- [\(.kind)] \(.name) state=\(.state)\(if .exit_code != null then " exit_code=\(.exit_code)" else "" end)\(if (.error | length) > 0 then " error=\(.error)" else "" end)"
    ' "${body_file}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --repo-id)
      REPO_ID="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_FULL_NAME="${2:-}"
      shift 2
      ;;
    --pipeline-id|--pipeline-number)
      PIPELINE_NUMBER="${2:-}"
      shift 2
      ;;
    --pipeline-url|--status-url)
      PIPELINE_URL="${2:-}"
      shift 2
      ;;
    --commit)
      COMMIT_SHA="${2:-}"
      shift 2
      ;;
    --token)
      TOKEN="${2:-}"
      shift 2
      ;;
    --json)
      FORMAT="json"
      shift
      ;;
    --summary)
      FORMAT="summary"
      shift
      ;;
    --strict)
      STRICT=1
      shift
      ;;
    --no-netrc)
      USE_NETRC=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

HOST="${HOST%/}"

if [[ -n "${PIPELINE_URL}" ]]; then
  parse_pipeline_url "${PIPELINE_URL}"
fi

selector_count=0
[[ -n "${PIPELINE_NUMBER}" ]] && ((selector_count+=1))
[[ -n "${COMMIT_SHA}" ]] && ((selector_count+=1))
if (( selector_count > 1 )); then
  die "--pipeline-id/--pipeline-url and --commit cannot be used together"
fi

if [[ -z "${TOKEN}" ]]; then
  die "token is required (--token or WOODPECKER_TOKEN)"
fi

curl_args=(-sS -H "Authorization: Bearer ${TOKEN}" -H "Accept: application/json")
if [[ ${USE_NETRC} -eq 1 ]]; then
  curl_args+=(-n)
fi

resolve_repo_id

if [[ -z "${REPO_ID}" ]]; then
  die "repo id is required (--repo-id, --repo, --pipeline-url, or WOODPECKER_REPO_ID)"
fi

body_file="$(mktemp)"
trap 'rm -f "${body_file}"' EXIT

if [[ -n "${PIPELINE_NUMBER}" ]]; then
  if [[ "${SELECTION_SOURCE}" == "latest" ]]; then
    SELECTION_SOURCE="pipeline-id"
  fi
  api_get "${HOST}/api/repos/${REPO_ID}/pipelines/${PIPELINE_NUMBER}" "${body_file}"
elif [[ -n "${COMMIT_SHA}" ]]; then
  select_pipeline_by_commit
else
  SELECTION_SOURCE="latest"
  api_get "${HOST}/api/repos/${REPO_ID}/pipelines/latest" "${body_file}"
fi

if [[ "${FORMAT}" == "json" ]]; then
  cat "${body_file}"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "[warn] jq が見つからないため raw JSON を出力します" >&2
  cat "${body_file}"
  exit 0
fi

status="$(jq -r '.status // "unknown"' "${body_file}")"

jq -r --arg repo_id "${REPO_ID}" --arg repo "${REPO_FULL_NAME}" --arg source "${SELECTION_SOURCE}" --arg note "${SELECTION_NOTE}" '
  [
    "source: \($source)",
    if $repo != "" then "repo: \($repo)" else empty end,
    "repo_id: \($repo_id)",
    "number: \(.number)",
    "id: \(.id)",
    "status: \(.status)",
    "event: \(.event)",
    "branch: \(.branch)",
    "commit: \(.commit)",
    "author: \(.author)",
    "message: \(.message // "")",
    if $note != "" then "selected_by: \($note)" else empty end
  ] | join("\n")
' "${body_file}"

print_workflow_failures

if jq -e '.errors | length > 0' "${body_file}" >/dev/null 2>&1; then
  echo
  echo "errors:"
  jq -r '
    .errors[]
    | "- [\(.type)] \(.message) (field=\(.data.field // "-"), file=\(.data.file // "-"), warning=\(.is_warning))"
  ' "${body_file}"
fi

if [[ ${STRICT} -eq 1 && "${status}" != "success" ]]; then
  exit 3
fi
