"""Tests for SESSION_COOKIE_SAMESITE warning behavior."""
import unittest
from unittest.mock import Mock

from config import warn_if_session_cookie_samesite_unset


class SessionCookieSameSiteWarningTests(unittest.TestCase):
    def test_warns_when_samesite_is_unset(self) -> None:
        logger = Mock()

        warned = warn_if_session_cookie_samesite_unset(
            logger,
            environment="staging",
            session_cookie_samesite="",
        )

        self.assertTrue(warned)
        logger.warning.assert_called_once_with(
            "SESSION_COOKIE_SAMESITE is not configured for admin session cookie (environment=%s)",
            "staging",
        )

    def test_does_not_warn_for_supported_samesite_values(self) -> None:
        for value in ("lax", "Strict", "NONE"):
            with self.subTest(value=value):
                logger = Mock()

                warned = warn_if_session_cookie_samesite_unset(
                    logger,
                    environment="staging",
                    session_cookie_samesite=value,
                )

                self.assertFalse(warned)
                logger.warning.assert_not_called()

    def test_warns_when_samesite_none_and_secure_is_false(self) -> None:
        logger = Mock()

        warned = warn_if_session_cookie_samesite_unset(
            logger,
            environment="staging",
            session_cookie_samesite="None",
            session_cookie_secure=False,
        )

        self.assertTrue(warned)
        logger.warning.assert_called_once_with(
            "SESSION_COOKIE_SAMESITE=None requires SESSION_COOKIE_SECURE=true for admin session cookie (environment=%s)",
            "staging",
        )

    def test_warns_with_production_when_environment_is_empty(self) -> None:
        logger = Mock()

        warned = warn_if_session_cookie_samesite_unset(
            logger,
            environment="",
            session_cookie_samesite="",
        )

        self.assertTrue(warned)
        logger.warning.assert_called_once_with(
            "SESSION_COOKIE_SAMESITE is not configured for admin session cookie (environment=%s)",
            "production",
        )

    def test_warns_and_falls_back_when_samesite_is_unknown(self) -> None:
        logger = Mock()

        warned = warn_if_session_cookie_samesite_unset(
            logger,
            environment="staging",
            session_cookie_samesite="cross-site",
        )

        self.assertTrue(warned)
        logger.warning.assert_called_once_with(
            "SESSION_COOKIE_SAMESITE=%r is unsupported; falling back to framework default (environment=%s)",
            "cross-site",
            "staging",
        )


if __name__ == "__main__":
    unittest.main()
