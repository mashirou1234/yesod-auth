#!/usr/bin/env bash
# Run from any directory; keep dependencies isolated from the system Python.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin="${PYTHON_BIN:-python3}"
"$python_bin" -c 'import sys; assert sys.version_info >= (3, 11), "Python >= 3.11 is required"'
"$python_bin" -m venv .venv
.venv/bin/python -m pip install -r api/requirements.txt ruff
.venv/bin/python -m pip check
