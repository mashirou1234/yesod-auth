#!/usr/bin/env bash
# The same Python and admin asset gates run locally, on GitHub, and on Woodpecker.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python}"
phase="${1:-all}"

# Synthetic, non-production credentials for every supported provider, never real secrets.
export RUNTIME_MODE=test TESTING=1 MOCK_OAUTH_ENABLED=1 DEBUG_OAUTH_ENABLED=0
export JWT_SECRET=ci-only-jwt-signing-fixture-0123456789abcdef
export ADMIN_USER=admin ADMIN_PASSWORD=admin
for provider in GOOGLE GITHUB X LINKEDIN FACEBOOK DISCORD SLACK TWITCH; do
  export "${provider}_CLIENT_ID=ci-${provider}-id"
  export "${provider}_CLIENT_SECRET=ci-${provider}-secret"
done

lint() {
  "$PYTHON_BIN" -m ruff check api admin
  "$PYTHON_BIN" -m ruff format --check api
}

unit() {
  (cd api && "$PYTHON_BIN" -m pytest tests)
  (cd admin && "$PYTHON_BIN" -m pytest tests)
}

assets() {
  cmp admin/tour/admin-tour.js admin/static/tour/admin-tour.js
  cmp admin/tour/admin-tour.css admin/static/tour/admin-tour.css
  cmp admin/node_modules/driver.js/dist/driver.js.iife.js admin/static/tour/vendor/driver.js
  cmp admin/node_modules/driver.js/dist/driver.css admin/static/tour/vendor/driver.css
  cmp admin/node_modules/driver.js/license admin/static/tour/vendor/driver.LICENSE
}

build() {
  (cd admin && bun install --frozen-lockfile && bun run build:tour)
  assets
  "$PYTHON_BIN" -m compileall -q api/app admin
  (cd api && RUNTIME_MODE=test "$PYTHON_BIN" -c 'from app.main import app; assert app.openapi()["paths"]')
}

integration() {
  # These URLs must point to disposable CI services, never a developer/production DB.
  : "${FOUNDATION_TEST_DATABASE_URL:?Set a disposable PostgreSQL URL}"
  : "${FOUNDATION_TEST_VALKEY_URL:?Set a disposable Valkey URL}"
  case "$FOUNDATION_TEST_DATABASE_URL" in
    postgresql+asyncpg://*/yesod_foundation_test) ;;
    *) echo 'Integration requires a dedicated database named yesod_foundation_test' >&2; exit 2 ;;
  esac
  (
    cd api
    export RUNTIME_MODE=test TESTING=0 MOCK_OAUTH_ENABLED=0 DEBUG_OAUTH_ENABLED=0
    export DATABASE_URL="$FOUNDATION_TEST_DATABASE_URL" VALKEY_URL="$FOUNDATION_TEST_VALKEY_URL"
    "$PYTHON_BIN" -m integration.wait_services
    "$PYTHON_BIN" -m alembic upgrade head
    "$PYTHON_BIN" -m pytest integration
  )
}

case "$phase" in
  lint|unit|build|assets|integration) "$phase" ;;
  all) lint; build; unit; integration ;;
  *) echo "Usage: $0 [all|lint|unit|build|assets|integration]" >&2; exit 2 ;;
esac
