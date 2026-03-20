"""Tests for SESSION_EXPIRY_HOURS parsing and fallback behavior."""
import os
import unittest
from unittest import mock

from config import read_session_expiry_hours_env


class SessionExpiryHoursConfigTests(unittest.TestCase):
    def test_uses_default_when_unset(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SESSION_EXPIRY_HOURS", None)
            value = read_session_expiry_hours_env()
        self.assertEqual(value, 24)

    def test_uses_env_value_when_valid_positive_integer(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"SESSION_EXPIRY_HOURS": "12"},
            clear=False,
        ):
            value = read_session_expiry_hours_env()
        self.assertEqual(value, 12)

    def test_falls_back_to_default_and_warns_when_invalid_text(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"SESSION_EXPIRY_HOURS": "abc"},
            clear=False,
        ):
            with self.assertLogs("config", level="WARNING") as captured:
                value = read_session_expiry_hours_env()
        self.assertEqual(value, 24)
        self.assertTrue(
            any(
                "SESSION_EXPIRY_HOURS is invalid ('abc'); using default value 24" in message
                for message in captured.output
            )
        )

    def test_falls_back_to_default_and_warns_when_non_positive(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"SESSION_EXPIRY_HOURS": "0"},
            clear=False,
        ):
            with self.assertLogs("config", level="WARNING") as captured:
                value = read_session_expiry_hours_env()
        self.assertEqual(value, 24)
        self.assertTrue(
            any(
                "SESSION_EXPIRY_HOURS is invalid ('0'); using default value 24" in message
                for message in captured.output
            )
        )


if __name__ == "__main__":
    unittest.main()
