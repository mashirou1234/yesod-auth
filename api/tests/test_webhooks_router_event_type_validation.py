"""Webhook admin router event_type validation tests."""

import pytest


@pytest.mark.asyncio
async def test_list_deliveries_rejects_unsupported_event_type(client):
    response = await client.get(
        "/api/v1/admin/webhooks/deliveries",
        params={"event_type": "user.unknown"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "unsupported_event_type",
            "message": "Unsupported webhook event_type",
            "event_type": "user.unknown",
            "supported_event_types": [
                "user.created",
                "user.updated",
                "user.deleted",
                "user.login",
                "user.oauth_linked",
                "user.oauth_unlinked",
            ],
        }
    }


@pytest.mark.asyncio
async def test_list_deliveries_allows_supported_event_type(client):
    response = await client.get(
        "/api/v1/admin/webhooks/deliveries",
        params={"event_type": "user.created"},
    )

    assert response.status_code == 200
    assert response.json() == []
