"""Tests for admin i18n fallback behavior."""
import unittest

from i18n import Translator, get_text


class I18nFallbackTests(unittest.TestCase):
    def test_unknown_locale_falls_back_to_default_language(self) -> None:
        self.assertEqual(get_text("nav.overview", "zz"), "📊 Overview")

    def test_path_traversal_like_locale_falls_back_to_default_language(self) -> None:
        self.assertEqual(get_text("nav.overview", "../../secrets"), "📊 Overview")

    def test_known_locale_is_not_affected(self) -> None:
        self.assertEqual(get_text("nav.overview", "ja"), "📊 概要")
        self.assertEqual(Translator("ja").lang, "ja")


if __name__ == "__main__":
    unittest.main()
