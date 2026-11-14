import json
import pytest
from pipeline.sites_loader import SiteLoader, SiteError


def _write(tmp_path, data):
    p = tmp_path / "sitios.json"
    p.write_text(json.dumps(data))
    return p


def test_carga_sitios_validos(tmp_path):
    p = _write(tmp_path, [{"name": "a", "lat": -89.9, "lon": 0.0}])
    sites = SiteLoader().load(p)
    assert sites[0].name == "a" and sites[0].lat == -89.9


def test_rechaza_latitud_fuera_de_rango(tmp_path):
    p = _write(tmp_path, [{"name": "a", "lat": -50.0, "lon": 0.0}])
    with pytest.raises(SiteError):
        SiteLoader().load(p)


def test_rechaza_nombres_repetidos(tmp_path):
    p = _write(
        tmp_path,
        [
            {"name": "a", "lat": -89.0, "lon": 0.0},
            {"name": "a", "lat": -88.0, "lon": 10.0},
        ],
    )
    with pytest.raises(SiteError):
        SiteLoader().load(p)


def test_rechaza_campo_faltante(tmp_path):
    p = _write(tmp_path, [{"name": "a", "lat": -89.0}])
    with pytest.raises(SiteError):
        SiteLoader().load(p)
