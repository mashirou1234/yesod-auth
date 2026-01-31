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

set -e

OUTPUT_DIR="${1:-./generated}"
API_URL="${API_URL:-http://localhost:8000}"
OPENAPI_URL="${API_URL}/openapi.json"

echo "🔍 Fetching OpenAPI schema from ${OPENAPI_URL}..."

# Check if API is running
if ! curl -s "${OPENAPI_URL}" > /dev/null 2>&1; then
    echo "❌ Error: Cannot reach ${OPENAPI_URL}"
    echo "   Make sure the API is running: docker compose up -d api"
    exit 1
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Generate types
echo "📝 Generating TypeScript types..."
npx openapi-typescript "${OPENAPI_URL}" -o "${OUTPUT_DIR}/api.d.ts"

echo "✅ Types generated at ${OUTPUT_DIR}/api.d.ts"
echo ""
echo "Usage in your frontend:"
echo ""
echo '  import type { paths, components } from "./types/api";'
echo '  '
echo '  type User = components["schemas"]["UserResponse"];'
echo '  type TokenPair = components["schemas"]["TokenPairResponse"];'
