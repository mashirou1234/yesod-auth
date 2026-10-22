"""Explicit non-production configuration before admin module imports."""

import os

os.environ["RUNTIME_MODE"] = "test"
