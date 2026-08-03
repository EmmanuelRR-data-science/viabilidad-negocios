"""Tests de sesión de aplicación, descarga firmada y webhook MP."""

from __future__ import annotations

import hashlib
import hmac

from fastapi.testclient import TestClient

from app.core.download_tokens import crear_download_token, verificar_download_token
from app.core.security import get_current_user
from app.core.session_tokens import crear_session_token, revoke_session_token, verificar_session_token
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_session_token_roundtrip():
    token, expires_in = crear_session_token(
        google_sub="sub_123",
        email="user@example.com",
        nombre="User",
        roles=["user"],
    )
    assert expires_in > 0
    claims = verificar_session_token(token)
    assert claims is not None
    assert claims["sub"] == "sub_123"
    assert claims["email"] == "user@example.com"
    assert claims["typ"] == "session"
    assert claims.get("jti")


def test_session_revoke_blocks_token():
    token, _ = crear_session_token(google_sub="sub_rev", email="r@ex.com")
    assert verificar_session_token(token) is not None
    revoke_session_token(token)
    assert verificar_session_token(token) is None


def test_protected_endpoint_accepts_session_bearer():
    token, _ = crear_session_token(
        google_sub="sub_abc",
        email="abc@example.com",
        nombre="Abc",
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["google_sub"] == "sub_abc"
    assert body["email"] == "abc@example.com"


def test_protected_endpoint_accepts_session_cookie():
    token, _ = crear_session_token(
        google_sub="sub_cookie",
        email="cookie@example.com",
        nombre="Cookie",
    )
    client.cookies.set("gv_session", token)
    try:
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "cookie@example.com"
    finally:
        client.cookies.clear()


def test_logout_revokes_and_clears_cookie():
    token, _ = crear_session_token(google_sub="sub_out", email="out@ex.com")
    client.cookies.set("gv_session", token)
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert verificar_session_token(token) is None
    client.cookies.clear()


def test_download_token_one_time():
    token, ttl = crear_download_token(orden_id=42, cognito_user_id="usr_1")
    assert ttl > 0
    claims = verificar_download_token(token, orden_id=42, consume=True)
    assert claims["sub"] == "usr_1"
    try:
        verificar_download_token(token, orden_id=42, consume=True)
        raise AssertionError("expected reuse to fail")
    except ValueError:
        pass


def _fake_request():
    from starlette.datastructures import Headers
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": Headers({}).raw,
        "client": ("test", 50000),
        "server": ("test", 80),
    }
    return Request(scope)


def test_get_current_user_rejects_non_session_jwt_when_google_configured(monkeypatch):
    monkeypatch.setattr("app.core.security.google_auth_habilitado", lambda: True)
    monkeypatch.setattr("app.core.security.DEV_MODE", False)

    from fastapi import HTTPException

    class Creds:
        credentials = "eyJhbGciOiJSUzI1NiJ9.e30.sig"

    import pytest

    with pytest.raises(HTTPException) as exc:
        get_current_user(_fake_request(), Creds())  # type: ignore[arg-type]
    assert exc.value.status_code == 401


def test_mock_tokens_rejected_when_dev_mode_false(monkeypatch):
    monkeypatch.setattr("app.core.security.DEV_MODE", False)
    monkeypatch.setattr("app.core.security.google_auth_habilitado", lambda: True)

    import pytest
    from fastapi import HTTPException

    for mock in ("mock-token", "mock-jwt-user", "mock-jwt-admin"):

        class Creds:
            credentials = mock

        with pytest.raises(HTTPException) as exc:
            get_current_user(_fake_request(), Creds())  # type: ignore[arg-type]
        assert exc.value.status_code == 401, mock


def test_mock_token_accepted_when_dev_mode_true(monkeypatch):
    monkeypatch.setattr("app.core.security.DEV_MODE", True)

    class Creds:
        credentials = "mock-token"

    user = get_current_user(_fake_request(), Creds())  # type: ignore[arg-type]
    assert user.cognito_user_id == "usr_mock_123"
    assert "admin" not in user.roles


def test_webhook_signature_validation(monkeypatch):
    from starlette.datastructures import Headers
    from starlette.requests import Request

    from app.clients.v0.mercadopago.mercadopago_webhook_signature import validar_firma_webhook_mp

    secret = "test_webhook_secret_value"
    monkeypatch.setattr(
        "app.clients.v0.mercadopago.mercadopago_webhook_signature.MERCADOPAGO_WEBHOOK_SECRET",
        secret,
    )
    monkeypatch.setattr(
        "app.clients.v0.mercadopago.mercadopago_webhook_signature.DEV_MODE",
        False,
    )

    data_id = "12345"
    request_id = "req-abc"
    ts = "1700000000"
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    headers = Headers(
        {
            "x-signature": f"ts={ts},v1={v1}",
            "x-request-id": request_id,
        }
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/pagos/webhook",
        "raw_path": b"/api/pagos/webhook",
        "query_string": f"data.id={data_id}".encode(),
        "headers": headers.raw,
        "client": ("test", 50000),
        "server": ("test", 80),
    }
    assert validar_firma_webhook_mp(Request(scope)) is True

    bad_scope = dict(scope)
    bad_scope["headers"] = Headers({"x-signature": f"ts={ts},v1=deadbeef", "x-request-id": request_id}).raw
    assert validar_firma_webhook_mp(Request(bad_scope)) is False
