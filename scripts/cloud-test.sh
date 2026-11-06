#!/usr/bin/env bash
# SQLite and mocked provider/Valkey tests; never start a deployment.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Run bash scripts/cloud-setup.sh first.' >&2
  exit 1
fi
export TESTING=1 MOCK_OAUTH_ENABLED=1
export JWT_SECRET=cloud-tests-only-not-for-production
export DATABASE_URL=sqlite+aiosqlite:///:memory:
export VALKEY_URL=redis://127.0.0.1:6379/15
# Do not inherit real provider credentials from a developer's shell.
for provider in GOOGLE GITHUB DISCORD X LINKEDIN FACEBOOK SLACK TWITCH; do
  export "${provider}_CLIENT_ID=" "${provider}_CLIENT_SECRET="
done
cd api
exec ../.venv/bin/python -m pytest "$@"
