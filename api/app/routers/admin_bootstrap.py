"""Small same-origin registration surface; no remote capability issuance."""

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from app.services.admin_bootstrap import (
    BootstrapError,
    is_initialized,
    register_admin,
    validate_registration,
)

router = APIRouter()
_static = Path(__file__).resolve().parent.parent / "static"
_headers = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
}


def _error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status, headers=_headers)


@router.get("/bootstrap", response_class=HTMLResponse)
async def bootstrap_page(request: Request):
    if request.url.query:
        return _error("Query parameters are not accepted", 400)
    try:
        if await is_initialized():
            return _error("Registration is closed", 410)
    except BootstrapError as error:
        return _error(str(error), error.status)
    except SQLAlchemyError:
        return _error("Registration unavailable", 503)
    return HTMLResponse((_static / "admin-bootstrap.html").read_text(), headers=_headers)


@router.get("/bootstrap/assets/{asset}", include_in_schema=False)
async def bootstrap_asset(asset: str):
    types = {"admin-bootstrap.js": "text/javascript", "admin-bootstrap.css": "text/css"}
    if asset not in types:
        return _error("Not found", 404)
    return Response((_static / asset).read_bytes(), media_type=types[asset], headers=_headers)


@router.post("/bootstrap", status_code=201)
async def bootstrap_register(request: Request):
    if request.url.query:
        return _error("Query parameters are not accepted", 400)
    origin = request.headers.get("origin")
    if (origin is not None and origin != str(request.base_url).rstrip("/")) or request.headers.get(
        "sec-fetch-site"
    ) == "cross-site":
        return _error("Same-origin request required", 403)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        return _error("JSON body required", 415)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 4096:
            return _error("Request too large", 413)
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        return _error("Invalid registration input", 400)
    finally:
        body.clear()
    try:
        validate_registration(data)
        await register_admin(data)
    except BootstrapError as error:
        return _error(str(error), error.status)
    except SQLAlchemyError:
        return _error("Registration unavailable", 503)
    return JSONResponse({"status": "created"}, status_code=201, headers=_headers)
