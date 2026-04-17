"""Tests for admin i18n fallback behavior."""
import unittest
from unittest.mock import patch

from i18n import Translator, get_text


class I18nFallbackTests(unittest.TestCase):
    def test_unknown_locale_falls_back_to_default_language(self) -> None:
        self.assertEqual(get_text("nav.overview", "zz"), "📊 Overview")

    def test_path_traversal_like_locale_falls_back_to_default_language(self) -> None:
        self.assertEqual(get_text("nav.overview", "../../secrets"), "📊 Overview")

    def test_unknown_locale_emits_warning_log(self) -> None:
        with self.assertLogs("i18n", level="WARNING") as captured:
            self.assertEqual(get_text("nav.overview", "zz"), "📊 Overview")
        self.assertTrue(
            any("Unsupported locale 'zz' requested." in message for message in captured.output)
        )

    def test_known_locale_is_not_affected(self) -> None:
        self.assertEqual(get_text("nav.overview", "ja"), "📊 概要")
        self.assertEqual(Translator("ja").lang, "ja")

    def test_untranslated_key_falls_back_to_default_language(self) -> None:
        mock_catalog = {
            "ja": {"nav": {"overview": "📊 概要"}},
            "en": {
                "nav": {"overview": "📊 Overview"},
                "messages": {"greeting": "Hello {name}"},
            },
        }

        with patch("i18n._load_translations", side_effect=lambda lang: mock_catalog[lang]):
            self.assertEqual(
                get_text("messages.greeting", "ja", name="Alice"),
                "Hello Alice",
            )

    def test_missing_key_in_all_locales_returns_key(self) -> None:
        mock_catalog = {
            "ja": {"nav": {"overview": "📊 概要"}},
            "en": {"nav": {"overview": "📊 Overview"}},
        }

        with patch("i18n._load_translations", side_effect=lambda lang: mock_catalog[lang]):
            self.assertEqual(get_text("messages.unknown", "ja"), "messages.unknown")


if __name__ == "__main__":
    unittest.main()
