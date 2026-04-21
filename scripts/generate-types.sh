#!/bin/bash
# Generate TypeScript types from OpenAPI schema
#
# Prerequisites:
#   npm install -g openapi-typescript
#
# Usage:
#   ./scripts/generate-types.sh [output_dir]
#
# Example:
#   ./scripts/generate-types.sh ./frontend/src/types

set -euo pipefail

OUTPUT_DIR="${1:-./generated}"
API_URL="${API_URL:-http://localhost:8000}"
OPENAPI_URL="${API_URL}/openapi.json"
DOC_REF="docs/api/auth.md"
DOC_INDEX_REF="docs/index.md"
MISSING_ITEMS=()

print_help_hint() {
    echo "   次の確認手順: ${DOC_REF} を参照してください。"
}

add_missing() {
    MISSING_ITEMS+=("$1")
}

require_cmd() {
    local cmd="$1"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        add_missing "コマンド: ${cmd}"
    fi
}

require_file() {
    local path="$1"
    if [ ! -f "${path}" ]; then
        add_missing "ファイル: ${path}"
    fi
}

run_preflight() {
    require_cmd curl
    require_cmd npx
    require_file "${DOC_REF}"
    require_file "${DOC_INDEX_REF}"

    if [ "${#MISSING_ITEMS[@]}" -gt 0 ]; then
        echo "❌ Error: preflight check failed (不足項目あり)"
        for item in "${MISSING_ITEMS[@]}"; do
            echo "   - ${item}"
        done
        echo "   復旧手順: 不足項目を解消してから再実行してください。"
        print_help_hint
        exit 1
    fi
}

run_preflight

echo "🔍 Fetching OpenAPI schema from ${OPENAPI_URL}..."

SCHEMA_TMP="$(mktemp)"
GEN_LOG_TMP="$(mktemp)"
cleanup() {
    rm -f "${SCHEMA_TMP}" "${GEN_LOG_TMP}"
}
trap cleanup EXIT

HTTP_STATUS="$(curl -sS -o "${SCHEMA_TMP}" -w '%{http_code}' "${OPENAPI_URL}" || true)"

if [ "${HTTP_STATUS}" = "000" ]; then
    echo "❌ Error: Cannot reach ${OPENAPI_URL}"
    echo "   復旧手順: API を起動してから再実行してください (例: docker compose up -d api)"
    print_help_hint
    exit 1
fi

if [ "${HTTP_STATUS}" -ne 200 ]; then
    echo "❌ Error: OpenAPI endpoint returned HTTP ${HTTP_STATUS}"
    echo "   復旧手順: API のログと /openapi.json 応答を確認してください。"
    print_help_hint
    exit 1
fi

if [ ! -s "${SCHEMA_TMP}" ] || ! grep -Eq '"(openapi|swagger)"' "${SCHEMA_TMP}"; then
    echo "❌ Error: Invalid OpenAPI schema payload from ${OPENAPI_URL}"
    echo "   復旧手順: /openapi.json が JSON Schema を返すか確認してください。"
    print_help_hint
    exit 1
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Generate types
echo "📝 Generating TypeScript types..."
if ! npx openapi-typescript "${OPENAPI_URL}" -o "${OUTPUT_DIR}/api.d.ts" 2>"${GEN_LOG_TMP}"; then
    echo "❌ Error: Type generation failed"
    if grep -Eiq 'fetch failed|ECONNREFUSED|ENOTFOUND|network' "${GEN_LOG_TMP}"; then
        echo "   復旧手順: API 到達性と OPENAPI_URL=${OPENAPI_URL} を確認してください。"
    else
        echo "   復旧手順: openapi-typescript の実行ログを確認して依存とスキーマを修正してください。"
    fi
    print_help_hint
    echo "   --- openapi-typescript log (tail) ---"
    tail -n 10 "${GEN_LOG_TMP}" | sed 's/^/   /'
    exit 1
fi

echo "✅ Types generated at ${OUTPUT_DIR}/api.d.ts"
echo ""
echo "Usage in your frontend:"
echo ""
echo '  import type { paths, components } from "./types/api";'
echo '  '
echo '  type User = components["schemas"]["UserResponse"];'
echo '  type TokenPair = components["schemas"]["TokenPairResponse"];'
