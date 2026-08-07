"""Validación de PAYMENTS_MODE y retrocompatibilidad con flags legacy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_BASE_DEV = {"DEV_MODE": True, "SESSION_SECRET": "dev-insecure-session-secret-change-me"}


def test_payments_mode_mock_explicit():
    s = Settings(PAYMENTS_MODE="mock", **_BASE_DEV)
    assert s.PAYMENTS_MODE == "mock"
    assert s.PAYMENTS_MOCK is True
    assert s.MERCADOPAGO_SANDBOX is False


def test_payments_mode_legacy_mock_flag():
    s = Settings(PAYMENTS_MOCK=True, **_BASE_DEV)
    assert s.PAYMENTS_MODE == "mock"
    assert s.PAYMENTS_MOCK is True


def test_payments_mode_legacy_sandbox_flags(monkeypatch):
    monkeypatch.delenv("PAYMENTS_MODE", raising=False)
    s = Settings(
        PAYMENTS_MODE="",
        PAYMENTS_MOCK=False,
        MERCADOPAGO_SANDBOX=True,
        MERCADOPAGO_ACCESS_TOKEN="TEST-token",
        MERCADOPAGO_PUBLIC_KEY="TEST-pub",
        MERCADOPAGO_WEBHOOK_SECRET="whsec",
        PUBLIC_APP_URL="https://staging.example.com",
        **_BASE_DEV,
    )
    assert s.PAYMENTS_MODE == "sandbox"
    assert s.MERCADOPAGO_SANDBOX is True


def test_payments_mode_legacy_live_flags(monkeypatch):
    monkeypatch.delenv("PAYMENTS_MODE", raising=False)
    s = Settings(
        PAYMENTS_MODE="",
        PAYMENTS_MOCK=False,
        MERCADOPAGO_SANDBOX=False,
        MERCADOPAGO_ACCESS_TOKEN="APP_USR-live-token",
        MERCADOPAGO_PUBLIC_KEY="APP_USR-live-pub",
        MERCADOPAGO_WEBHOOK_SECRET="whsec",
        PUBLIC_APP_URL="https://app.geoviabilidad.com",
        **_BASE_DEV,
    )
    assert s.PAYMENTS_MODE == "live"
    assert s.MERCADOPAGO_SANDBOX is False


def test_payments_mode_invalid():
    with pytest.raises(ValidationError, match="PAYMENTS_MODE debe ser mock"):
        Settings(PAYMENTS_MODE="staging", **_BASE_DEV)


def test_sandbox_requires_mp_credentials(monkeypatch):
    monkeypatch.delenv("MERCADOPAGO_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MERCADOPAGO_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("MERCADOPAGO_WEBHOOK_SECRET", raising=False)
    with pytest.raises(ValidationError, match="obligatorios"):
        Settings(
            PAYMENTS_MODE="sandbox",
            PUBLIC_APP_URL="https://staging.example.com",
            **_BASE_DEV,
        )


def test_sandbox_requires_https_public_url():
    with pytest.raises(ValidationError, match="PUBLIC_APP_URL"):
        Settings(
            PAYMENTS_MODE="sandbox",
            MERCADOPAGO_ACCESS_TOKEN="TEST-token",
            MERCADOPAGO_PUBLIC_KEY="TEST-pub",
            MERCADOPAGO_WEBHOOK_SECRET="whsec",
            PUBLIC_APP_URL="http://localhost:8000",
            **_BASE_DEV,
        )


def test_live_rejects_test_token():
    with pytest.raises(ValidationError, match="TEST-"):
        Settings(
            PAYMENTS_MODE="live",
            MERCADOPAGO_ACCESS_TOKEN="TEST-should-not-be-live",
            MERCADOPAGO_PUBLIC_KEY="APP_USR-pub",
            MERCADOPAGO_WEBHOOK_SECRET="whsec",
            PUBLIC_APP_URL="https://app.geoviabilidad.com",
            **_BASE_DEV,
        )


def test_pagos_config_exposes_payments_mode():
    from app.services.v0.payments.payment_service import obtener_config_pagos

    cfg = obtener_config_pagos()
    assert cfg.payments_mode == "mock"
    assert cfg.payments_mock is True
    assert cfg.checkout_pro is False
