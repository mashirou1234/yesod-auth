"""Property-based tests for WebhookConfigLoader."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

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
