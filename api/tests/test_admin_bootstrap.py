"""Input and HTTP contracts for first-administrator bootstrap."""

import secrets
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers.admin_bootstrap import router
from app.services.admin_bootstrap import BootstrapError, validate_registration


def valid_input():
    return {
        "capability": secrets.token_urlsafe(32),
        "username": "operator.one",
        "password": secrets.token_urlsafe(24),
    }


def test_valid_registration_and_password_boundaries():
    data = valid_input()
    for password in ("a" * 16, "界" * 128, "a" * 128):
        validate_registration({**data, "password": password})


@pytest.mark.parametrize(
    "case", ["short", "long", "blank", "same", "username", "capability", "extra", "type"]
)
def test_invalid_input_never_includes_input_in_error(case):
    data = valid_input()
    if case == "short":
        data["password"] = "x" * 15
    elif case == "long":
        data["password"] = "x" * 129
    elif case == "blank":
        data["password"] = " " * 16
    elif case == "same":
        data["username"] = "a" * 16
        data["password"] = data["username"]
    elif case == "username":
        data["username"] = "../operator"
    elif case == "capability":
        data["capability"] = "x"
    elif case == "extra":
        data["other"] = "not-accepted"
    else:
        data["password"] = ["not-a-string"]
    with pytest.raises(BootstrapError) as error:
        validate_registration(data)
    assert str(error.value) == "Invalid registration input"


@pytest.fixture
def bootstrap_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")
    return app


@pytest.mark.asyncio
async def test_json_response_and_logs_do_not_echo_secrets(bootstrap_app, caplog):
    data = valid_input()
    with patch("app.routers.admin_bootstrap.register_admin", new=AsyncMock()):
        async with AsyncClient(
            transport=ASGITransport(app=bootstrap_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/admin/bootstrap", json=data)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert all(data[key] not in response.text + caplog.text for key in ("capability", "password"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["malformed", "oversized", "query", "form", "extra", "origin", "fetchsite"]
)
async def test_invalid_http_requests_are_generic(bootstrap_app, case, caplog):
    data = valid_input()
    kwargs = {"json": data}
    path = "/api/v1/admin/bootstrap"
    if case == "malformed":
        kwargs = {"content": "{", "headers": {"content-type": "application/json"}}
    elif case == "oversized":
        kwargs = {"content": "x" * 4097, "headers": {"content-type": "application/json"}}
    elif case == "query":
        path += "?unexpected=1"
    elif case == "form":
        kwargs = {"data": data}
    elif case == "extra":
        data["extra"] = data["password"]
    elif case == "origin":
        kwargs["headers"] = {"origin": "https://different.example"}
    else:
        kwargs["headers"] = {"sec-fetch-site": "cross-site"}
    async with AsyncClient(
        transport=ASGITransport(app=bootstrap_app), base_url="http://test"
    ) as client:
        response = await client.post(path, **kwargs)
    assert response.status_code in (400, 403, 413, 415)
    assert all(data[key] not in response.text + caplog.text for key in ("capability", "password"))


@pytest.mark.asyncio
async def test_page_assets_and_closed_entry(bootstrap_app):
    async with AsyncClient(
        transport=ASGITransport(app=bootstrap_app), base_url="http://test"
    ) as client:
        with patch("app.routers.admin_bootstrap.is_initialized", new=AsyncMock(return_value=False)):
            response = await client.get("/api/v1/admin/bootstrap")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in response.headers["content-security-policy"]
        assert response.text.count('type="password"') == 2
        for asset in ("admin-bootstrap.js", "admin-bootstrap.css"):
            assert (await client.get("/api/v1/admin/bootstrap/assets/" + asset)).status_code == 200
        assert (await client.get("/api/v1/admin/bootstrap/assets/not-allowed")).status_code == 404
        with patch("app.routers.admin_bootstrap.is_initialized", new=AsyncMock(return_value=True)):
            assert (await client.get("/api/v1/admin/bootstrap")).status_code == 410


@pytest.mark.asyncio
async def test_unavailable_database_fails_closed_without_exception_detail(bootstrap_app, caplog):
    marker = secrets.token_urlsafe(32)
    from sqlalchemy.exc import SQLAlchemyError

    with patch(
        "app.routers.admin_bootstrap.register_admin",
        new=AsyncMock(side_effect=SQLAlchemyError(marker)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=bootstrap_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/admin/bootstrap", json=valid_input())
    assert response.status_code == 503
    assert marker not in response.text + caplog.text
