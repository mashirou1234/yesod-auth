"""Internationalization (i18n) support for admin dashboard."""
import json
import os
from pathlib import Path
from typing import Any

# Supported languages with display names
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ja": "日本語",
    "fr": "Français",
    "ko": "한국어",
    "de": "Deutsch",
}

DEFAULT_LANGUAGE = "en"

# Cache for loaded translations
_translations_cache: dict[str, dict] = {}


def _get_locales_dir() -> Path:
    """Get the locales directory path."""
    return Path(__file__).parent / "locales"


def _load_translations(lang: str) -> dict:
    """Load translations for a specific language."""
    if lang in _translations_cache:
        return _translations_cache[lang]

    locales_dir = _get_locales_dir()
    file_path = locales_dir / f"{lang}.json"

    if not file_path.exists():
        # Fallback to default language
        file_path = locales_dir / f"{DEFAULT_LANGUAGE}.json"
        lang = DEFAULT_LANGUAGE

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            translations = json.load(f)
            _translations_cache[lang] = translations
            return translations
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def get_text(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    """Get translated text by key.

    Args:
        key: Dot-separated key path (e.g., "nav.overview")
        lang: Language code (e.g., "en", "ja")
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string, or the key if not found
    """
    translations = _load_translations(lang)

    # Navigate nested keys
    keys = key.split(".")
    value: Any = translations

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # Key not found, return the key itself
            return key

    if isinstance(value, str):
        # Apply format arguments if provided
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError:
                return value
        return value

    return key


def get_language_options() -> list[str]:
    """Get list of supported language codes."""
    return list(SUPPORTED_LANGUAGES.keys())


def get_language_display_name(lang: str) -> str:
    """Get display name for a language code."""
    return SUPPORTED_LANGUAGES.get(lang, lang)


def get_language_selector_options() -> dict[str, str]:
    """Get language options for selector (display_name -> code)."""
    return {v: k for k, v in SUPPORTED_LANGUAGES.items()}


class Translator:
    """Translator class for convenient access to translations."""

    def __init__(self, lang: str = DEFAULT_LANGUAGE):
        """Initialize translator with a language."""
        self.lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    def __call__(self, key: str, **kwargs: Any) -> str:
        """Get translated text."""
        return get_text(key, self.lang, **kwargs)

    def set_language(self, lang: str) -> None:
        """Set the current language."""
        if lang in SUPPORTED_LANGUAGES:
            self.lang = lang
