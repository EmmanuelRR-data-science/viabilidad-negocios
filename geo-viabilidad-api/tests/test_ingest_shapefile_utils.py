"""Pruebas de detección de capas AGEB en shapefiles INEGI."""

import os
import tempfile

from geo_viabilidad_data.ingest_shapefile_utils import find_ageb_shapefile, is_ageb_shapefile, normalize_cvegeo


def test_is_ageb_shapefile_rejects_wrong_layers():
    assert is_ageb_shapefile("14a.shp")
    assert is_ageb_shapefile("01a.shp")
    assert not is_ageb_shapefile("14ar.shp")
    assert not is_ageb_shapefile("14fm.shp")
    assert not is_ageb_shapefile("14m.shp")
    assert not is_ageb_shapefile("09sia.shp")


def test_normalize_cvegeo_truncates_manzana_keys():
    assert normalize_cvegeo("1408300010560004") == "1408300010560"
    assert normalize_cvegeo("140210001020A") == "140210001020A"


def test_find_ageb_shapefile_picks_urban_layer():
    with tempfile.TemporaryDirectory() as tmp:
        dataset = os.path.join(tmp, "conjunto_de_datos")
        os.makedirs(dataset)
        open(os.path.join(dataset, "14fm.shp"), "w", encoding="utf-8").close()
        open(os.path.join(dataset, "14m.shp"), "w", encoding="utf-8").close()
        open(os.path.join(dataset, "14a.shp"), "w", encoding="utf-8").close()

        picked = find_ageb_shapefile(tmp)
        assert picked is not None
        assert picked.endswith(f"{os.sep}14a.shp")
