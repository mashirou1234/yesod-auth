"""Tests for admin guided tour asset and text safety contracts."""
import json
import pathlib
import unittest

import tour_runtime


ADMIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
TOUR_SOURCE = ADMIN_ROOT / "tour"
TOUR_STATIC = ADMIN_ROOT / "static" / "tour"
LOCALES = ADMIN_ROOT / "locales"


class TourAssetTests(unittest.TestCase):
    def test_tour_source_assets_match_static_outputs(self) -> None:
        for filename in ("admin-tour.js", "admin-tour.css"):
            with self.subTest(filename=filename):
                self.assertEqual(
                    (TOUR_SOURCE / filename).read_text(),
                    (TOUR_STATIC / filename).read_text(),
                )

    def test_tour_runtime_uses_stable_page_allowlist(self) -> None:
        self.assertEqual(tour_runtime.PAGE_ORDER, list(tour_runtime.PAGE_LABEL_KEYS))
        self.assertEqual(
            {step["pageId"] for step in tour_runtime.TOUR_STEPS},
            set(tour_runtime.PAGE_ORDER),
        )

    def test_tour_translations_do_not_contain_markup(self) -> None:
        for locale_path in sorted(LOCALES.glob("*.json")):
            with self.subTest(locale=locale_path.name):
                catalog = json.loads(locale_path.read_text())
                for key, value in self._flatten(catalog):
                    if key.startswith("tour."):
                        self.assertNotRegex(value, r"[<>&]")

    def test_tour_source_escapes_driver_html_sinks(self) -> None:
        source = (TOUR_SOURCE / "admin-tour.js").read_text()
        self.assertIn("function escapeHtml", source)
        self.assertIn("escapeHtml(step.title)", source)
        self.assertIn("escapeHtml(step.description)", source)
        self.assertIn("escapeHtml(config.labels.next)", source)

    def test_tour_runtime_uses_current_streamlit_html_api(self) -> None:
        source = (ADMIN_ROOT / "tour_runtime.py").read_text()
        self.assertIn("st.html(", source)
        self.assertNotIn("components.html(", source)

    def _flatten(self, node: object, prefix: tuple[str, ...] = ()) -> list[tuple[str, str]]:
        if isinstance(node, dict):
            return [
                item
                for key, value in node.items()
                for item in self._flatten(value, (*prefix, key))
            ]
        if isinstance(node, str):
            return [(".".join(prefix), node)]
        return []


if __name__ == "__main__":
    unittest.main()
