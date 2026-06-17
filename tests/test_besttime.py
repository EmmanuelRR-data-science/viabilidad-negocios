import os
import sys
from unittest.mock import MagicMock, patch

# Configure python path to resolve imports from root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.besttime import (
    DIAS_SEMANA_ESP,
    _normalizar_curva_a_medianoche,
    _parsear_analysis_besttime,
    obtener_afluencia,
)


def _build_day(day_int: int, day_mean: int, peak_max: int | None = None) -> dict:
    """
    Builds a realistic BestTime 'analysis' day object. 'day_raw' contains 24 hourly
    values starting at 6:00 AM, as delivered by the real BestTime forecast API.
    """
    day_raw = [min(100, (i * 5 + day_mean) % 101) for i in range(24)]
    day = {
        "day_info": {
            "day_int": day_int,
            "day_text": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day_int],
            "day_mean": day_mean,
            "day_max": min(100, day_mean + 30),
            "day_rank_mean": 7 - day_int,
            "venue_open": 6,
            "venue_closed": 23,
        },
        "day_raw": day_raw,
    }
    if peak_max is not None:
        day["peak_hours"] = [{"peak_start": peak_max - 1, "peak_max": peak_max, "peak_end": peak_max + 2}]
    return day


def test_normalizar_curva_desplaza_inicio_6am():
    """day_raw[0] corresponds to 6:00 AM and must land on index 6 of the normalized curve."""
    day_raw = list(range(24))  # value i == position i in BestTime's 6AM-based window
    curva = _normalizar_curva_a_medianoche(day_raw)

    assert curva[6] == 0  # 6:00 AM = first BestTime value
    assert curva[7] == 1
    assert curva[23] == 17
    assert curva[0] == 18  # midnight = BestTime index 18 (6AM + 18h)
    assert curva[5] == 23
    assert len(curva) == 24


def test_parsear_analysis_estructura_completa():
    """A full 7-day analysis list must produce the complete internal structure."""
    analysis = [_build_day(i, day_mean=30 + i * 5, peak_max=18) for i in range(7)]
    parsed = _parsear_analysis_besttime(analysis)

    assert parsed is not None
    assert set(parsed["afluencia_semanal"].keys()) == set(DIAS_SEMANA_ESP)
    assert all(len(curva) == 24 for curva in parsed["afluencia_semanal"].values())
    # Sunday (day_int=6) has the highest day_mean (60) → peak day
    assert parsed["dia_pico"] == "Domingo"
    assert parsed["hora_pico"] == "18:00"
    assert parsed["saturación_promedio"] == 45.0  # mean of 30,35,...,60
    assert parsed["afluencia_horaria"] == parsed["afluencia_semanal"]["Domingo"]


def test_parsear_analysis_sin_peak_hours_usa_argmax():
    """Without 'peak_hours', the peak hour falls back to the curve's argmax."""
    analysis = [_build_day(0, day_mean=50)]
    parsed = _parsear_analysis_besttime(analysis)

    assert parsed is not None
    curva = parsed["afluencia_semanal"]["Lunes"]
    hora_esperada = curva.index(max(curva))
    assert parsed["hora_pico"] == f"{hora_esperada:02d}:00"


def test_parsear_analysis_dias_invalidos_retorna_none():
    """Days without valid day_int/day_raw are skipped; empty result returns None."""
    analysis = [
        {"day_info": {"day_int": None}, "day_raw": [1] * 24},
        {"day_info": {"day_int": 2}, "day_raw": [1] * 10},  # incomplete curve
        "garbage",
    ]
    assert _parsear_analysis_besttime(analysis) is None


@patch("app.besttime.requests.post")
@patch("app.besttime.BESTTIME_API_KEY", "pri_test_key_realistic")
def test_obtener_afluencia_parsea_respuesta_real(mock_post):
    """
    The real BestTime forecast response ('analysis' as a LIST of day objects)
    must be parsed into status=success instead of crashing into no_data.
    Regression test for: 'list' object has no attribute 'get'.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "venue_info": {"venue_name": "Xibalba Norte Crossfit"},
        "analysis": [_build_day(i, day_mean=40 + i, peak_max=19) for i in range(7)],
    }
    mock_post.return_value = mock_response

    result = obtener_afluencia(19.475074, -99.132128, "gimnasio")

    assert result["status"] == "success"
    assert result["venue_name"] == "Xibalba Norte Crossfit"
    assert len(result["afluencia_semanal"]) == 7
    assert result["dia_pico"] == "Domingo"
    assert result["hora_pico"] == "19:00"


@patch("app.besttime.requests.post")
@patch("app.besttime.BESTTIME_API_KEY", "pri_test_key_realistic")
def test_obtener_afluencia_respuesta_sin_analysis_retorna_no_data(mock_post):
    """A response without a usable 'analysis' list must degrade to no_data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "error", "message": "venue not found"}
    mock_post.return_value = mock_response

    result = obtener_afluencia(19.475074, -99.132128, "cafeteria")

    assert result["status"] == "no_data"
    assert result["afluencia_horaria"] == []


def _mock_404_response():
    import requests as _requests

    resp = MagicMock()
    resp.status_code = 404
    resp.raise_for_status.side_effect = _requests.HTTPError("404 Client Error: Not Found")
    return resp


@patch("app.besttime.requests.post")
@patch("app.besttime.BESTTIME_API_KEY", "pri_test_key_realistic")
def test_obtener_afluencia_reintenta_con_venue_mas_popular(mock_post):
    """
    When the first candidate venue returns 404 (no BestTime coverage), the next
    candidate must be tried. Candidates are ordered by user_ratings_total (desc),
    not by distance, since popular venues are the ones BestTime can forecast.
    """
    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.json.return_value = {
        "status": "OK",
        "venue_info": {"venue_name": "Cafetito"},
        "analysis": [_build_day(i, day_mean=50, peak_max=17) for i in range(7)],
    }
    mock_post.side_effect = [_mock_404_response(), ok_response]

    competidores = [
        {"nombre": "casa", "direccion": "Calle Norte 178 519, CDMX", "user_ratings_total": 2},
        {"nombre": "Starbucks Reforma", "direccion": "Paseo de la Reforma 222, CDMX", "user_ratings_total": 1500},
        {"nombre": "Cafetito", "direccion": "Av. Juarez 10, CDMX", "user_ratings_total": 80},
    ]

    result = obtener_afluencia(19.43, -99.13, "cafeteria", competidores=competidores)

    assert result["status"] == "success"
    assert result["venue_name"] == "Cafetito"
    # First attempt must be the most-reviewed venue (Starbucks), second the next one (Cafetito)
    first_call_params = mock_post.call_args_list[0].kwargs["params"]
    second_call_params = mock_post.call_args_list[1].kwargs["params"]
    assert first_call_params["venue_name"] == "Starbucks Reforma"
    assert second_call_params["venue_name"] == "Cafetito"


@patch("app.besttime.requests.post")
@patch("app.besttime.BESTTIME_API_KEY", "pri_test_key_realistic")
def test_obtener_afluencia_todos_los_venues_fallan_retorna_no_data(mock_post):
    """If every candidate venue fails (max 3 attempts), the result must be no_data."""
    mock_post.side_effect = [_mock_404_response() for _ in range(3)]

    competidores = [
        {"nombre": f"Negocio {i}", "direccion": f"Calle {i}, CDMX", "user_ratings_total": i * 10} for i in range(5)
    ]

    result = obtener_afluencia(19.43, -99.13, "cafeteria", competidores=competidores)

    assert result["status"] == "no_data"
    assert mock_post.call_count == 3  # capped at _BESTTIME_MAX_INTENTOS


def test_construir_filas_horas_pico_desde_curvas_reales():
    """Las ventanas horarias del PDF deben derivarse de afluencia_semanal, no de plantillas."""
    from app.besttime import construir_filas_horas_pico

    afl = {
        "status": "success",
        "afluencia_semanal": {
            "Lunes": [0, 0, 0, 0, 0, 0, 0, 0, 5, 15, 40, 55, 50, 45, 30, 25, 20, 15, 10, 5, 0, 0, 0, 0],
            "Martes": [0, 0, 0, 0, 0, 0, 0, 0, 10, 20, 30, 35, 40, 45, 50, 55, 40, 30, 20, 10, 5, 0, 0, 0],
        },
    }
    filas = construir_filas_horas_pico(afl)
    assert len(filas) == 2
    assert filas[0][0] == "Lunes"
    assert "11:00" in filas[0][1]
    assert filas[1][0] == "Martes"
    assert "15:00" in filas[1][1]
