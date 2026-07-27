"""Tests de estrategias de tier (entitlement server-side)."""

from app.services.tiers import get_tier_strategy


def test_tier_desconocido_cae_a_basico():
    strategy = get_tier_strategy("hacker_premium")
    assert strategy.tier_id == "basico"
    assert strategy.uses_bedrock() is False
    assert strategy.uses_aliados_guiados() is False
    assert strategy.includes_static_map() is False


def test_basico_sin_bedrock_ni_mapa():
    s = get_tier_strategy("basico")
    assert s.pdf_pages() == 6
    assert s.uses_bedrock() is False
    assert s.includes_static_map() is False


def test_pro_con_bedrock_sin_aliados_guiados():
    s = get_tier_strategy("PRO")
    assert s.tier_id == "pro"
    assert s.uses_bedrock() is True
    assert s.uses_aliados_guiados() is False
    assert s.includes_static_map() is True
    assert s.includes_aliados_on_map() is False
    assert s.pdf_pages() == 10


def test_premium_capacidades_completas():
    s = get_tier_strategy("premium")
    assert s.uses_bedrock() is True
    assert s.uses_aliados_guiados() is True
    assert s.includes_aliados_on_map() is True
    assert s.includes_multi_radio() is True
    assert s.pdf_pages() == 13
    assert "aliados" in s.report_sections()
