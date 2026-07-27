"""Pruebas de presentación de afluencia peatonal."""

from app.services.presentation.afluencia import (
    LABEL_NOCHE_PROMEDIO,
    NOTA_ESTABLECIMIENTO_REFERENCIA,
    calcular_desglose_noche,
    construir_filas_tabla_afluencia,
    texto_establecimiento_referencia,
)


def _curva_panaderia():
    curva = [0] * 24
    for h, v in {
        8: 45,
        9: 50,
        10: 60,
        11: 70,
        12: 80,
        13: 90,
        14: 90,
        15: 95,
        16: 95,
        17: 95,
        18: 95,
        19: 90,
        20: 70,
        21: 50,
        22: 0,
        23: 0,
    }.items():
        curva[h] = v
    return curva


def test_desglose_noche_excluye_ceros_del_promedio():
    noche = calcular_desglose_noche(_curva_panaderia())
    assert noche["por_hora"][20] == 70
    assert noche["por_hora"][22] == 0
    assert noche["promedio_con_dato"] == 60
    assert noche["horas_con_dato"] == 2


def test_tabla_incluye_desglose_y_promedio_nocturno():
    filas = construir_filas_tabla_afluencia(_curva_panaderia())
    assert filas[0][0].startswith("Mañana")
    assert any(f[0] == "  20:00" and f[1] == "70%" for f in filas)
    assert any(f[0] == "  22:00" and f[1] == "Sin dato" for f in filas)
    assert any(f[0] == LABEL_NOCHE_PROMEDIO and f[1] == "60%" for f in filas)


def test_textos_en_espanol_sin_venue():
    from app.services.presentation.afluencia import ACLARACION_HEATMAP_COMPETIDORES

    assert "venue" not in NOTA_ESTABLECIMIENTO_REFERENCIA.lower()
    assert "establecimiento" in NOTA_ESTABLECIMIENTO_REFERENCIA.lower()
    assert "competidor" in ACLARACION_HEATMAP_COMPETIDORES.lower()
    assert "atractor" in ACLARACION_HEATMAP_COMPETIDORES.lower()
    assert "Pastelería" in texto_establecimiento_referencia("Pastelería Lecaroz")
    assert "Competidor" in texto_establecimiento_referencia("Pastelería Lecaroz")
