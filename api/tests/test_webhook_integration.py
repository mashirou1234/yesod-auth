"""Integration tests for webhook event emission."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.webhooks.config import WebhookConfig, WebhookEndpoint, WebhookSettings
from app.webhooks.emitter import WebhookEmitter


@pytest.fixture
def sample_endpoint():
    """Sample webhook endpoint subscribing to all user events."""
    return WebhookEndpoint(
        id="test-endpoint",
        url="https://example.com/webhook",
        secret="test-secret",
        events=[
            "user.created",
            "user.updated",
            "user.deleted",
            "user.login",
            "user.oauth_linked",
            "user.oauth_unlinked",
        ],
        enabled=True,
    )


@pytest.fixture
def sample_config(sample_endpoint):
    """Sample webhook config."""
    return WebhookConfig(
        endpoints=[sample_endpoint],
        settings=WebhookSettings(),
    )


@pytest.fixture
def mock_valkey():
    """Mock Valkey client."""
    mock = AsyncMock()
    mock.rpush = AsyncMock(return_value=1)
    return mock


class TestUserLifecycleEvents:
    """Tests for user lifecycle event emission."""

    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        event_type=st.sampled_from(
            [
                "user.created",
                "user.updated",
                "user.deleted",
                "user.login",
                "user.oauth_linked",
                "user.oauth_unlinked",
            ]
        ),
        user_id=st.uuids(),
    )
    @pytest.mark.asyncio
    async def test_user_events_trigger_webhooks(
        self,
        event_type: str,
        user_id: uuid.UUID,
        mock_valkey,
        sample_config,
    ):
        """
        Property 1: User Lifecycle Events Trigger Webhooks

        For any user lifecycle action (create, update, delete, oauth_link,
        oauth_unlink, login), the WebhookEmitter SHALL emit an event with
        the corresponding event type and user_id.

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**
        """
        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit_user_event(
                event_type,
                user_id,
                extra_data={"provider": "google"}
                if "oauth" in event_type or event_type == "user.login"
                else None,
            )

            # Event should be created
            assert event is not None
            assert event.event_type == event_type
            assert event.data["user_id"] == str(user_id)

            # Event should be queued
            mock_valkey.rpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_created_event_includes_provider(self, mock_valkey, sample_config):
        """Test user.created event includes provider info."""
        user_id = uuid.uuid4()

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit_user_event(
                "user.created",
                user_id,
                extra_data={"provider": "google", "email": "test@example.com"},
            )

            assert event is not None
            assert event.data["provider"] == "google"
            assert event.data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_user_updated_event_includes_changes(self, mock_valkey, sample_config):
        """Test user.updated event includes changed fields."""
        user_id = uuid.uuid4()

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit_user_event(
                "user.updated",
                user_id,
                extra_data={"changes": ["display_name", "avatar_url"]},
            )

            assert event is not None
            assert event.data["changes"] == ["display_name", "avatar_url"]

    @pytest.mark.asyncio
    async def test_user_deleted_event_includes_email(self, mock_valkey, sample_config):
        """Test user.deleted event includes email for reference."""
        user_id = uuid.uuid4()

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit_user_event(
                "user.deleted",
                user_id,
                extra_data={"email": "deleted@example.com", "oauth_providers": ["google"]},
            )

            assert event is not None
            assert event.data["email"] == "deleted@example.com"
            assert event.data["oauth_providers"] == ["google"]

    @pytest.mark.asyncio
    async def test_oauth_linked_event_includes_provider(self, mock_valkey, sample_config):
        """Test user.oauth_linked event includes provider."""
        user_id = uuid.uuid4()

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit_user_event(
                "user.oauth_linked",
                user_id,
                extra_data={"provider": "discord"},
            )

            assert event is not None
            assert event.data["provider"] == "discord"
