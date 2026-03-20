"""Tests for VALKEY reconnect wait settings."""
import os
import unittest
from unittest import mock

from config import read_bounded_float_env


class ValkeyReconnectWaitConfigTests(unittest.TestCase):
    def test_uses_default_when_unset(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VALKEY_RECONNECT_WAIT_SECONDS", None)
            value = read_bounded_float_env(
                "VALKEY_RECONNECT_WAIT_SECONDS",
                default=0.2,
                minimum=0.05,
                maximum=30.0,
            )
        self.assertEqual(value, 0.2)

    def test_uses_env_value_when_set(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"VALKEY_RECONNECT_WAIT_SECONDS": "1.5"},
            clear=False,
        ):
            value = read_bounded_float_env(
                "VALKEY_RECONNECT_WAIT_SECONDS",
                default=0.2,
                minimum=0.05,
                maximum=30.0,
            )
        self.assertEqual(value, 1.5)

    def test_raises_when_out_of_range(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"VALKEY_RECONNECT_WAIT_SECONDS": "0.001"},
            clear=False,
        ):
            with self.assertRaises(ValueError):
                read_bounded_float_env(
                    "VALKEY_RECONNECT_WAIT_SECONDS",
                    default=0.2,
                    minimum=0.05,
                    maximum=30.0,
                )


if __name__ == "__main__":
    unittest.main()
