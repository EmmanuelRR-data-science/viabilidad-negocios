"""Pruebas de búsqueda unificada y filtro de giro para restaurantes."""

from unittest.mock import patch

from app.competencia_busqueda import (
    buscar_competidores_unificado,
    keyword_places_para_ia,
    keywords_busqueda_places,
)
from app.google_places import competidor_es_relevante_al_giro, filtrar_competidores_por_giro


def test_keywords_restaurante_carta_no_usa_slug():
    kws = keywords_busqueda_places("restaurante_carta", google_type="restaurant")
    assert None in kws
    assert "restaurante_carta" not in [k for k in kws if k]
    assert "restaurante" in kws


def test_keyword_ia_restaurante_carta_canonico():
    kw = keyword_places_para_ia("restaurante_carta", google_type="restaurant")
    assert kw == "restaurante"


def test_penelope_pasa_filtro_por_nombre():
    comp = {"nombre": "Penélope Restaurante", "tipo": "Restaurant", "rating": 4.4}
    assert competidor_es_relevante_al_giro("restaurante_carta", comp) is True


def test_banderillas_pasa_filtro_por_tipo_google():
    comp = {
        "nombre": "BANDERILLAS MASTER",
        "tipo": "Restaurant",
        "google_types": ["restaurant", "food", "point_of_interest"],
    }
    assert competidor_es_relevante_al_giro("restaurante_carta", comp) is True


def test_banderillas_pasa_filtro_por_nombre_antojo():
    comp = {"nombre": "Banderillas Master", "tipo": "Restaurant", "google_types": []}
    assert competidor_es_relevante_al_giro("restaurante_carta", comp) is True


@patch("app.google_places.buscar_competidores")
@patch("app.google_places.buscar_competidores_por_proximidad")
def test_buscar_unificado_merge_keywords(mock_prox, mock_nearby):
    mock_nearby.side_effect = [
        [{"nombre": "A", "latitud": 1.0, "longitud": 2.0, "google_types": ["restaurant"]}],
        [{"nombre": "B", "latitud": 3.0, "longitud": 4.0, "google_types": ["restaurant"]}],
        [],
    ]
    mock_prox.return_value = [
        {"nombre": "C", "latitud": 5.0, "longitud": 6.0, "google_types": ["restaurant"]},
    ]

    result = buscar_competidores_unificado(
        19.0,
        -99.0,
        1000,
        "restaurant",
        rubro="restaurante_carta",
    )
    assert len(result) == 3
    assert mock_nearby.call_count == 2
    mock_prox.assert_called_once()


def test_filtro_conserva_restaurante_con_nombre_generico_y_tipo_google():
    candidatos = [
        {
            "nombre": "BANDERILLAS MASTER",
            "google_types": ["restaurant", "food"],
            "rating": 4.5,
        },
        {"nombre": "City Market", "google_types": ["supermarket"], "rating": 4.0},
    ]
    filtrados = filtrar_competidores_por_giro("restaurante_carta", candidatos)
    assert len(filtrados) == 1
    assert filtrados[0]["nombre"] == "BANDERILLAS MASTER"
