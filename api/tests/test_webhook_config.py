"""Property-based tests for WebhookConfigLoader."""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

import app.webhooks.config as config_module
from app.webhooks.config import WebhookConfigLoader

# Strategies for generating test data
valid_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=50,
)

valid_https_urls = st.builds(
    lambda domain, path: f"https://{domain}.example.com/{path}",
    domain=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=20),
    path=st.text(alphabet="abcdefghijklmnopqrstuvwxyz/", min_size=0, max_size=30),
)

invalid_http_urls = st.builds(
    lambda domain: f"http://{domain}.example.com/webhook",
    domain=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=20),
)

valid_secrets = st.text(min_size=8, max_size=64)

event_types = st.lists(
    st.sampled_from(
        [
            "user.created",
            "user.updated",
            "user.deleted",
            "user.login",
            "user.oauth_linked",
            "user.oauth_unlinked",
        ]
    ),
    min_size=1,
    max_size=6,
    unique=True,
)


class TestWebhookConfigValidation:
    """Tests for webhook configuration validation."""

    @settings(max_examples=100)
    @given(
        endpoint_id=valid_ids,
        url=valid_https_urls,
        secret=valid_secrets,
        events=event_types,
    )
    def test_valid_config_is_accepted(
        self,
        endpoint_id: str,
        url: str,
        secret: str,
        events: list[str],
    ):
        """
        Property 8: Configuration Validation (positive case)

        Valid configurations with HTTPS URL, non-empty secret, and
        non-empty events list SHALL be accepted.

        **Validates: Requirements 2.2, 2.3**
        """
        config = {
            "endpoints": [
                {
                    "id": endpoint_id,
                    "url": url,
                    "secret": secret,  # Literal secret for testing
                    "events": events,
                    "enabled": True,
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()

            assert len(result.endpoints) == 1
            assert result.endpoints[0].id == endpoint_id
            assert result.endpoints[0].url == url
            assert result.endpoints[0].events == events
        finally:
            config_path.unlink()

    @settings(max_examples=50)
    @given(
        endpoint_id=valid_ids,
        url=invalid_http_urls,
        secret=valid_secrets,
        events=event_types,
    )
    def test_http_url_is_rejected(
        self,
        endpoint_id: str,
        url: str,
        secret: str,
        events: list[str],
    ):
        """
        Property 8: Configuration Validation (HTTP rejection)

        Configurations with HTTP (non-HTTPS) URLs SHALL be rejected.

        **Validates: Requirements 2.3**
        """
        config = {
            "endpoints": [
                {
                    "id": endpoint_id,
                    "url": url,
                    "secret": secret,
                    "events": events,
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()

            # Endpoint should be rejected (not in list)
            assert len(result.endpoints) == 0
        finally:
            config_path.unlink()

    def test_missing_secret_is_rejected(self):
        """
        Property 8: Configuration Validation (missing secret)

        Configurations without a secret key SHALL be rejected.

        **Validates: Requirements 4.6**
        """
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    # secret is missing
                    "events": ["user.created"],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()

            assert len(result.endpoints) == 0
        finally:
            config_path.unlink()

    def test_empty_events_is_rejected(self):
        """
        Property 8: Configuration Validation (empty events)

        Configurations with empty events list SHALL be rejected.

        **Validates: Requirements 7.3**
        """
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "test-secret",
                    "events": [],  # Empty events
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()

            assert len(result.endpoints) == 0
        finally:
            config_path.unlink()

    def test_events_with_empty_element_is_rejected(self):
        """events 配列に空要素がある endpoint は読み込み対象外にする。"""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "test-secret",
                    "events": ["user.created", "  ", "user.updated"],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()
            assert len(result.endpoints) == 0
        finally:
            config_path.unlink()

    def test_events_with_duplicated_element_is_rejected(self):
        """events 配列に重複がある endpoint は読み込み対象外にする。"""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "test-secret",
                    "events": ["user.created", "user.created"],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()
            assert len(result.endpoints) == 0
        finally:
            config_path.unlink()

    def test_env_var_secret_resolution(self):
        """Test that environment variable secrets are resolved."""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "${TEST_WEBHOOK_SECRET}",
                    "events": ["user.created"],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with (
                patch.object(config_module, "CONFIG_PATH", config_path),
                patch.dict(os.environ, {"TEST_WEBHOOK_SECRET": "resolved-secret"}),
            ):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()

            assert len(result.endpoints) == 1
            assert result.endpoints[0].secret == "resolved-secret"
        finally:
            config_path.unlink()

    def test_missing_config_file_disables_webhooks(self):
        """Test that missing config file results in empty config."""
        with patch.object(config_module, "CONFIG_PATH", Path("/nonexistent/webhooks.yaml")):
            WebhookConfigLoader._config = None
            result = WebhookConfigLoader.load()

        assert len(result.endpoints) == 0

    def test_invalid_yaml_is_logged_and_disables_webhooks(self, caplog):
        """Invalid YAML should be logged and result in disabled webhooks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("endpoints:\n  - id: broken\n    url: [unterminated\n")
            config_path = Path(f.name)

        try:
            with (
                patch.object(config_module, "CONFIG_PATH", config_path),
                caplog.at_level(logging.ERROR, logger=config_module.__name__),
            ):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()

            assert len(result.endpoints) == 0
            assert "Failed to parse webhook configuration" in caplog.text
        finally:
            config_path.unlink()

    def test_unresolved_secret_is_logged_and_endpoint_skipped(self, caplog):
        """Unresolved secret reference should be logged and endpoint skipped."""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "${MISSING_WEBHOOK_SECRET}",
                    "events": ["user.created"],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with (
                patch.object(config_module, "CONFIG_PATH", config_path),
                patch.dict(os.environ, {}, clear=True),
                caplog.at_level(logging.WARNING, logger=config_module.__name__),
            ):
                WebhookConfigLoader._config = None
                result = WebhookConfigLoader.load()

            assert len(result.endpoints) == 0
            assert "Skipping invalid endpoint" in caplog.text
            assert "secret could not be resolved" in caplog.text
        finally:
            config_path.unlink()

    def test_duplicate_endpoint_id_is_rejected(self):
        """Duplicate endpoint IDs should fail load to avoid ambiguous routing."""
        config = {
            "endpoints": [
                {
                    "id": "duplicate-id",
                    "url": "https://example.com/webhook-a",
                    "secret": "secret-a",
                    "events": ["user.created"],
                },
                {
                    "id": "duplicate-id",
                    "url": "https://example.com/webhook-b",
                    "secret": "secret-b",
                    "events": ["user.updated"],
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                with pytest.raises(
                    ValueError,
                    match="Duplicate webhook endpoint id detected: duplicate-id",
                ):
                    WebhookConfigLoader.load()
        finally:
            config_path.unlink()

    def test_get_endpoints_for_event(self):
        """Test filtering endpoints by event type."""
        config = {
            "endpoints": [
                {
                    "id": "endpoint-1",
                    "url": "https://example1.com/webhook",
                    "secret": "secret1",
                    "events": ["user.created", "user.deleted"],
                    "enabled": True,
                },
                {
                    "id": "endpoint-2",
                    "url": "https://example2.com/webhook",
                    "secret": "secret2",
                    "events": ["user.login"],
                    "enabled": True,
                },
                {
                    "id": "endpoint-3",
                    "url": "https://example3.com/webhook",
                    "secret": "secret3",
                    "events": ["user.created"],
                    "enabled": False,  # Disabled
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                WebhookConfigLoader.load()

                # user.created should match endpoint-1 only (endpoint-3 is disabled)
                endpoints = WebhookConfigLoader.get_endpoints_for_event("user.created")
                assert len(endpoints) == 1
                assert endpoints[0].id == "endpoint-1"

                # user.login should match endpoint-2
                endpoints = WebhookConfigLoader.get_endpoints_for_event("user.login")
                assert len(endpoints) == 1
                assert endpoints[0].id == "endpoint-2"

                # user.updated should match none
                endpoints = WebhookConfigLoader.get_endpoints_for_event("user.updated")
                assert len(endpoints) == 0
        finally:
            config_path.unlink()

    def test_retry_max_delay_setting_defaults_and_override(self):
        """retry_max_delay_seconds は既定値と設定値の両方を反映する。"""
        default_config = {
            "endpoints": [
                {
                    "id": "default-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "secret",
                    "events": ["user.created"],
                }
            ]
        }
        override_config = {
            "endpoints": [
                {
                    "id": "override-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "secret",
                    "events": ["user.created"],
                }
            ],
            "settings": {
                "retry_max_delay_seconds": 7,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f_default:
            yaml.dump(default_config, f_default)
            default_path = Path(f_default.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f_override:
            yaml.dump(override_config, f_override)
            override_path = Path(f_override.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", default_path):
                WebhookConfigLoader._config = None
                result_default = WebhookConfigLoader.load()
            assert result_default.settings.retry_max_delay_seconds == 60

            with patch.object(config_module, "CONFIG_PATH", override_path):
                WebhookConfigLoader._config = None
                result_override = WebhookConfigLoader.load()
            assert result_override.settings.retry_max_delay_seconds == 7
        finally:
            default_path.unlink()
            override_path.unlink()

    @pytest.mark.parametrize("invalid_backoff_ms", [0, -1])
    def test_retry_backoff_ms_non_positive_raises_startup_error(self, invalid_backoff_ms: int):
        """retry_backoff_ms が 0/負値なら起動時に設定エラーとする。"""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "secret",
                    "events": ["user.created"],
                }
            ],
            "settings": {
                "retry_backoff_ms": invalid_backoff_ms,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                with pytest.raises(ValueError, match="settings\\.retry_backoff_ms"):
                    WebhookConfigLoader.load()
        finally:
            config_path.unlink()

    @pytest.mark.parametrize(
        ("retry_backoff_ms", "error_key"),
        [
            ([], "settings.retry_backoff_ms"),
            ([0, 100, 300], "settings.retry_backoff_ms\\[0\\]"),
            ([100, -1, 300], "settings.retry_backoff_ms\\[1\\]"),
            ([300, 100, 500], "settings.retry_backoff_ms\\[1\\]"),
        ],
    )
    def test_retry_backoff_ms_list_invalid_cases_raise_startup_error(
        self,
        retry_backoff_ms: list[int],
        error_key: str,
    ):
        """retry_backoff_ms 配列が正の整数・単調増加でなければ起動時に設定エラーとする。"""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "secret",
                    "events": ["user.created"],
                }
            ],
            "settings": {
                "retry_backoff_ms": retry_backoff_ms,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                with pytest.raises(ValueError, match=error_key):
                    WebhookConfigLoader.load()
        finally:
            config_path.unlink()

    def test_retry_backoff_ms_list_non_decreasing_is_accepted(self):
        """retry_backoff_ms 配列が正の整数かつ単調増加なら設定を受理する。"""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "secret",
                    "events": ["user.created"],
                }
            ],
            "settings": {
                "retry_backoff_ms": [100, 100, 300, 500],
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                loaded = WebhookConfigLoader.load()
            assert loaded.settings.retry_base_delay_seconds == 2
        finally:
            config_path.unlink()

    def test_retry_delay_bounds_invalid_order_raises_startup_error(self):
        """retry_max_delay_seconds が retry_base_delay_seconds 未満なら設定エラーにする。"""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "secret",
                    "events": ["user.created"],
                }
            ],
            "settings": {
                "retry_base_delay_seconds": 10,
                "retry_max_delay_seconds": 5,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                with pytest.raises(ValueError, match="settings\\.retry_max_delay_seconds"):
                    WebhookConfigLoader.load()
        finally:
            config_path.unlink()

    @pytest.mark.parametrize("invalid_jitter_ratio", [-0.1, 1.1, "0.5"])
    def test_retry_jitter_ratio_invalid_raises_startup_error(self, invalid_jitter_ratio):
        """retry_jitter_ratio が範囲外または非数値なら設定エラーにする。"""
        config = {
            "endpoints": [
                {
                    "id": "test-endpoint",
                    "url": "https://example.com/webhook",
                    "secret": "secret",
                    "events": ["user.created"],
                }
            ],
            "settings": {
                "retry_jitter_ratio": invalid_jitter_ratio,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = Path(f.name)

        try:
            with patch.object(config_module, "CONFIG_PATH", config_path):
                WebhookConfigLoader._config = None
                with pytest.raises(ValueError, match="settings\\.retry_jitter_ratio"):
                    WebhookConfigLoader.load()
        finally:
            config_path.unlink()
