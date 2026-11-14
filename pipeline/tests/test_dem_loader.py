import numpy as np
import pytest
import rasterio

from pipeline.config import Config
from pipeline.dem_loader import DemLoader
from pipeline.models import Site

CFG = Config()
pytestmark = pytest.mark.skipif(not CFG.dem_path.exists(), reason="falta el DEM")


def test_proyeccion_y_orientacion_de_longitud():
    # En lat -80 (borde del DEM) la distancia al polo es la mitad del lado.
    # Convención esperada en mapas LOLA: lon 0 arriba (+y), lon 90 E a la derecha (+x).
    with DemLoader(CFG.dem_path) as dem:
        b = dem.bounds
        x, y = dem.lonlat_to_xy(-80.0, 0.0)
        assert abs(x) < 500 and abs(y - b.top) < 500
        x, y = dem.lonlat_to_xy(-80.0, 90.0)
        assert abs(x - b.right) < 500 and abs(y) < 500


def test_forma_y_posicion_del_sitio():
    with DemLoader(CFG.dem_path) as dem:
        p = dem.crop(Site("t", -85.0, 0.0), radius_km=40)
        n = p.elevation.shape[0]
        assert p.elevation.shape == (n, n) and n % 2 == 1
        # el sitio debe caer cerca del centro del recorte
        assert abs(p.site_px[0] - n // 2) < 1 and abs(p.site_px[1] - n // 2) < 1
        assert np.isfinite(p.site_height) and abs(p.site_height) < 10_000


def test_el_recorte_coincide_con_el_archivo():
    with DemLoader(CFG.dem_path) as dem:
        s = Site("t", -85.0, 0.0)
        p = dem.crop(s, radius_km=40)
        x, y = dem.lonlat_to_xy(s.lat, s.lon)
        with rasterio.open(CFG.dem_path) as src:
            esperado = next(src.sample([(x, y)]))[0]
        i, j = int(round(p.site_px[1])), int(round(p.site_px[0]))
        assert np.isclose(p.elevation[i, j], esperado)


def test_guardar_y_cargar(tmp_path):
    with DemLoader(CFG.dem_path) as dem:
        p = dem.crop(Site("t", -85.0, 0.0), radius_km=10)
        DemLoader.save_patch(p, tmp_path / "t.npz")
    q = DemLoader.load_patch(tmp_path / "t.npz")
    assert np.array_equal(p.elevation, q.elevation, equal_nan=True)
    assert q.site.name == "t" and q.site_px == p.site_px


def test_limite_de_rayos_hacia_el_norte():
    with DemLoader(CFG.dem_path) as dem:
        s = Site("t", -85.0, 0.0)
        x0, y0 = dem.lonlat_to_xy(s.lat, s.lon)
        lim = dem.ray_limits_m(s, 360)
        assert lim[0] == pytest.approx(dem.bounds.top - y0)  # azimut 0 con lon 0 = +y
        assert lim.min() > 100_000  # a 85°S, 100 km caben en cualquier dirección
