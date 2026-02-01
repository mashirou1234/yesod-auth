"""Property-based tests for WebhookEvent."""

import uuid
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from app.webhooks.event import WebhookEvent

# Strategies for generating test data
event_types = st.sampled_from(
    [
        "user.created",
        "user.updated",
        "user.deleted",
        "user.login",
        "user.oauth_linked",
        "user.oauth_unlinked",
    ]
)

user_ids = st.uuids()

simple_data = st.fixed_dictionaries(
    {
        "user_id": st.uuids().map(str),
    }
).map(dict)


class TestWebhookEventSerialization:
    """Tests for WebhookEvent serialization."""

    @settings(max_examples=100)
    @given(event_type=event_types, data=simple_data)
    def test_payload_serialization_roundtrip(self, event_type: str, data: dict):
        """
        Property 2: Payload Serialization Round-Trip

        For any valid WebhookEvent object, serializing to JSON and then
        deserializing SHALL produce an equivalent object with identical
        event_id, event_type, timestamp, and data.

        **Validates: Requirements 3.5, 3.6**
        """
        # Create original event
        original = WebhookEvent(event_type=event_type, data=data)

        # Serialize to payload
        payload = original.to_payload()

        # Deserialize back
        restored = WebhookEvent.from_payload(payload)

        # Verify equivalence
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.timestamp == original.timestamp
        assert restored.data == original.data

    def test_payload_contains_required_fields(self):
        """
        Property 3: Payload Structure Completeness (partial)

        Verify payload contains all required fields.

        **Validates: Requirements 3.2, 3.3, 3.4**
        """
        event = WebhookEvent(
            event_type="user.created",
            data={"user_id": str(uuid.uuid4())},
        )

        payload = event.to_payload()

        # Check required fields exist
        assert "event_id" in payload
        assert "event_type" in payload
        assert "timestamp" in payload
        assert "data" in payload

        # Validate types
        assert uuid.UUID(payload["event_id"])  # Valid UUID
        assert isinstance(payload["event_type"], str)
        assert len(payload["event_type"]) > 0
        assert datetime.fromisoformat(payload["timestamp"])  # Valid ISO 8601
        assert "user_id" in payload["data"]

    def test_timestamp_is_utc(self):
        """Verify timestamp is in UTC timezone."""
        event = WebhookEvent(
            event_type="user.created",
            data={"user_id": str(uuid.uuid4())},
        )

        assert event.timestamp.tzinfo == UTC
