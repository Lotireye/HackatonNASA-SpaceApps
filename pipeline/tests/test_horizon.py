import numpy as np
import pytest

from pipeline.config import Config
from pipeline.dem_loader import DemLoader
from pipeline.horizon import HorizonMask, azimuth_dir_xy, R_MOON_M
from pipeline.importer import DataImporter
from pipeline.models import DemPatch, Site

CFG = Config()
necesita_dem = pytest.mark.skipif(not CFG.dem_path.exists(), reason="falta el DEM")


def _patch(z, site, pix=100.0):
    n = z.shape[0]
    return DemPatch(
        site=site,
        elevation=z,
        pixel_m=pix,
        site_px=(n // 2, n // 2),
        radius_km=(n // 2) * pix / 1000.0,
    )


@necesita_dem
@pytest.mark.parametrize(
    "lat, lon", [(-85.0, 0.0), (-85.0, 90.0), (-88.0, -135.0), (-82.0, 170.0)]
)
def test_direcciones_coinciden_con_la_proyeccion(lat, lon):
    with DemLoader(CFG.dem_path) as dem:
        x0, y0 = dem.lonlat_to_xy(lat, lon)
        xn, yn = dem.lonlat_to_xy(lat + 0.01, lon)  # un poco al norte
        xe, ye = dem.lonlat_to_xy(lat, lon + 0.01)  # un poco al este
    norte = np.array([xn - x0, yn - y0])
    norte /= np.linalg.norm(norte)
    este = np.array([xe - x0, ye - y0])
    este /= np.linalg.norm(este)
    assert np.allclose(azimuth_dir_xy(0.0, lon), norte, atol=0.01)
    assert np.allclose(azimuth_dir_xy(90.0, lon), este, atol=0.01)


def test_terreno_plano_da_mascara_cero():
    m = HorizonMask.compute(
        _patch(np.zeros((401, 401), "float32"), Site("s", -85.0, 30.0))
    )
    assert m.n_az == 360
    assert np.all(np.abs(m.el_deg) < 0.01)


# (lon del sitio, (desplazamiento fila, columna) del muro en píxeles, azimut esperado)
CASOS = [
    (0.0, (0, 100), 90.0),  # este en lon 0 = derecha
    (90.0, (100, 0), 90.0),  # este en lon 90 = abajo
    (180.0, (0, -100), 90.0),  # este en lon 180 = izquierda
    (-90.0, (-100, 0), 90.0),  # este en lon -90 = arriba
    (0.0, (-100, 0), 0.0),  # norte en lon 0 = arriba
    (0.0, (100, 0), 180.0),  # sur en lon 0 = abajo (hacia el polo)
]


@pytest.mark.parametrize("lon, wall, az_esperado", CASOS)
def test_muro_aparece_en_el_azimut_correcto(lon, wall, az_esperado):
    z = np.zeros((401, 401), "float32")
    r, c = 200 + wall[0], 200 + wall[1]
    if wall[0] == 0:
        z[r - 5 : r + 6, c] = 1000.0
    else:
        z[r, c - 5 : c + 6] = 1000.0
    m = HorizonMask.compute(_patch(z, Site("s", -85.0, lon)))

    th = 10_000.0 / R_MOON_M  # el muro está a 10 km
    esperado = np.degrees(
        np.arctan2(
            (R_MOON_M + 1000) * np.cos(th) - R_MOON_M, (R_MOON_M + 1000) * np.sin(th)
        )
    )
    assert abs(m.el_deg[int(az_esperado)] - esperado) < 0.01
    assert (
        abs(m.elevation_at((az_esperado + 180.0) % 360.0)) < 0.01
    )  # lado opuesto: sin terreno


def test_elevation_at_interpola_de_forma_circular():
    el = np.zeros(360)
    el[359], el[0] = 10.0, 20.0
    m = HorizonMask(Site("s", -85.0, 0.0), el)
    assert m.elevation_at(359.0) == pytest.approx(10.0)
    assert m.elevation_at(359.5) == pytest.approx(15.0)
    assert m.elevation_at(0.0) == pytest.approx(20.0)
    assert m.elevation_at(360.0) == pytest.approx(20.0)
    assert np.allclose(m.elevation_at(np.array([359.0, 0.0])), [10.0, 20.0])


def test_to_list_convierte_nan_en_none():
    m = HorizonMask(Site("s", -85.0, 0.0), np.array([1.234, np.nan, -0.5]))
    assert m.to_list() == [1.23, None, -0.5]


@necesita_dem
def test_mascara_con_datos_reales():
    with DataImporter(CFG).import_all() as data:
        m = HorizonMask.compute(data.get_patch(data.sites[0]))
    assert m.n_az == 360
    assert np.isfinite(m.el_deg).mean() > 0.95
    assert -60.0 < np.nanmin(m.el_deg) and np.nanmax(m.el_deg) < 60.0
