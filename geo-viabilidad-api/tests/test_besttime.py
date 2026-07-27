import os
import sys
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.clients.v0.besttime.besttime_client_processed import (
    DIAS_SEMANA_ESP,
    _normalizar_curva_a_medianoche,
    _parsear_analysis_besttime,
    obtener_afluencia,
)
from app.schemas.v0.besttime.besttime_dto_schemas import BestTimeDayDTO


def _build_day(day_int: int, day_mean: int, peak_max: int | None = None) -> BestTimeDayDTO:
    """Builds a BestTimeDayDTO matching the v0 processed layer expectation."""
    day_raw = [min(100, (i * 5 + day_mean) % 101) for i in range(24)]
    return BestTimeDayDTO(
        day_info={
            "day_int": day_int,
            "day_text": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day_int],
            "day_mean": day_mean,
            "day_max": min(100, day_mean + 30),
            "day_rank_mean": 7 - day_int,
            "venue_open": 6,
            "venue_closed": 23,
        },
        day_raw=day_raw,
    )


def _build_day_dict(day_int: int, day_mean: int, peak_max: int | None = None) -> dict:
    """Builds a raw dict for mocking API JSON responses."""
    day_raw = [min(100, (i * 5 + day_mean) % 101) for i in range(24)]
    d = {
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
        d["peak_hours"] = [{"peak_start": peak_max - 1, "peak_max": peak_max, "peak_end": peak_max + 2}]
    return d


def test_normalizar_curva_desplaza_inicio_6am():
    day_raw = list(range(24))
    curva = _normalizar_curva_a_medianoche(day_raw)

    assert curva[6] == 0
    assert curva[7] == 1
    assert curva[23] == 17
    assert curva[0] == 18
    assert curva[5] == 23
    assert len(curva) == 24


def test_parsear_analysis_estructura_completa():
    analysis = [_build_day(i, day_mean=30 + i * 5, peak_max=18) for i in range(7)]
    parsed = _parsear_analysis_besttime(analysis)

    assert parsed is not None
    assert set(parsed["afluencia_semanal"].keys()) == set(DIAS_SEMANA_ESP)
    assert all(len(curva) == 24 for curva in parsed["afluencia_semanal"].values())
    assert parsed["dia_pico"] == "Domingo"
    assert parsed["afluencia_horaria"] == parsed["afluencia_semanal"]["Domingo"]


def test_parsear_analysis_sin_peak_hours_usa_argmax():
    analysis = [_build_day(0, day_mean=50)]
    parsed = _parsear_analysis_besttime(analysis)

    assert parsed is not None
    curva = parsed["afluencia_semanal"]["Lunes"]
    hora_esperada = curva.index(max(curva))
    assert parsed["hora_pico"] == f"{hora_esperada:02d}:00"


def test_parsear_analysis_dias_invalidos_retorna_none():
    from app.schemas.v0.besttime.besttime_dto_schemas import BestTimeDayInfoDTO

    analysis = [
        BestTimeDayDTO(day_info=BestTimeDayInfoDTO(day_int=None), day_raw=[1] * 24),
        BestTimeDayDTO(day_info=BestTimeDayInfoDTO(day_int=2), day_raw=[1] * 10),
    ]
    assert _parsear_analysis_besttime(analysis) is None


@patch("app.clients.v0.besttime.besttime_client_processed.solicitar_forecast_besttime_raw")
@patch("app.clients.v0.besttime.besttime_client_processed.api_key_besttime_valida", return_value=True)
def test_obtener_afluencia_parsea_respuesta_real(mock_valid, mock_forecast):
    from app.schemas.v0.besttime.besttime_dto_schemas import BestTimeForecastDTO

    mock_forecast.return_value = BestTimeForecastDTO(
        status="OK",
        venue_info={"venue_name": "Xibalba Norte Crossfit"},
        analysis=[_build_day(i, day_mean=40 + i, peak_max=19) for i in range(7)],
    )

    result = obtener_afluencia(19.475074, -99.132128, "gimnasio")

    assert result["status"] == "success"
    assert result["venue_name"] == "Xibalba Norte Crossfit"
    assert len(result["afluencia_semanal"]) == 7
    assert result["dia_pico"]


@patch("app.clients.v0.besttime.besttime_client_processed.solicitar_forecast_besttime_raw")
@patch("app.clients.v0.besttime.besttime_client_processed.api_key_besttime_valida", return_value=True)
def test_obtener_afluencia_respuesta_sin_analysis_retorna_no_data(mock_valid, mock_forecast):
    mock_forecast.return_value = None

    result = obtener_afluencia(19.475074, -99.132128, "cafeteria")

    assert result["status"] == "no_data"


@patch("app.clients.v0.besttime.besttime_client_processed.solicitar_forecast_besttime_raw")
@patch("app.clients.v0.besttime.besttime_client_processed.api_key_besttime_valida", return_value=True)
def test_obtener_afluencia_reintenta_con_venue_mas_popular(mock_valid, mock_forecast):
    from app.schemas.v0.besttime.besttime_dto_schemas import BestTimeForecastDTO

    ok_dto = BestTimeForecastDTO(
        status="OK",
        venue_info={"venue_name": "Cafetito"},
        analysis=[_build_day(i, day_mean=50, peak_max=17) for i in range(7)],
    )
    mock_forecast.side_effect = [None, ok_dto]

    competidores = [
        {"nombre": "casa", "direccion": "Calle Norte 178 519, CDMX", "user_ratings_total": 2},
        {"nombre": "Starbucks Reforma", "direccion": "Paseo de la Reforma 222, CDMX", "user_ratings_total": 1500},
        {"nombre": "Cafetito", "direccion": "Av. Juarez 10, CDMX", "user_ratings_total": 80},
    ]

    result = obtener_afluencia(19.43, -99.13, "cafeteria", competidores=competidores)
    assert result["status"] == "success"
    assert result["venue_name"] == "Cafetito"


@patch("app.clients.v0.besttime.besttime_client_processed.solicitar_forecast_besttime_raw")
@patch("app.clients.v0.besttime.besttime_client_processed.api_key_besttime_valida", return_value=True)
def test_obtener_afluencia_todos_los_venues_fallan_retorna_no_data(mock_valid, mock_forecast):
    mock_forecast.return_value = None

    competidores = [
        {"nombre": f"Negocio {i}", "direccion": f"Calle {i}, CDMX", "user_ratings_total": i * 10} for i in range(5)
    ]

    result = obtener_afluencia(19.43, -99.13, "cafeteria", competidores=competidores)
    assert result["status"] == "no_data"
    assert mock_forecast.call_count == 3


def test_construir_filas_horas_pico_desde_curvas_reales():
    from app.clients.v0.besttime.besttime_client_processed import construir_filas_horas_pico

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


@patch("app.clients.v0.besttime.besttime_client_processed.DEV_MODE", False)
@patch("app.clients.v0.besttime.besttime_client_raw.api_key_besttime_valida", return_value=False)
def test_obtener_afluencia_rechaza_clave_publica(mock_valid):
    with patch("app.clients.v0.besttime.besttime_client_raw.solicitar_forecast_besttime_raw") as mock_forecast:
        result = obtener_afluencia(19.43, -99.13, "restaurante")
    mock_forecast.assert_not_called()
    assert result["status"] == "no_data"
