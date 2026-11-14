import numpy as np
import pytest

from pipeline.config import Config
from pipeline.ephemeris import Ephemeris, local_basis
from pipeline.kernels import KernelManager
from pipeline.models import Site

CFG = Config()
HAY_KERNELS = not KernelManager(CFG.raw_dir, CFG.kernel_files).check_files()
necesita_kernels = pytest.mark.skipif(
    not HAY_KERNELS, reason="faltan kernels en data/raw"
)
POLO = Site("polo", -89.9, 0.0)


@pytest.fixture(scope="module")
def eph():
    with KernelManager(CFG.raw_dir, CFG.kernel_files):
        yield Ephemeris()


@pytest.fixture(scope="module")
def year(eph):
    ets = Ephemeris.time_grid("2027-01-01T00:00:00", 366, 1.0)
    return eph.sun_azel(POLO, ets), eph.earth_azel(POLO, ets)


def test_base_local_es_ortonormal():
    for lat, lon in [(-89.9, 0.0), (-85.0, 123.0), (-80.0, -45.0)]:
        e, n, u = local_basis(lat, lon)
        assert np.allclose([e @ e, n @ n, u @ u], 1.0)
        assert np.allclose([e @ n, e @ u, n @ u], 0.0)
        assert np.allclose(np.cross(e, n), u)


@necesita_kernels
def test_time_grid(eph):
    ets = Ephemeris.time_grid("2027-01-01T00:00:00", days=1, step_hours=1.0)
    assert len(ets) == 24
    assert np.allclose(np.diff(ets), 3600.0)
    assert Ephemeris.to_utc(ets[:1])[0] == "2027-01-01T00:00:00"


@necesita_kernels
def test_sol_elevacion_en_el_polo(year):
    sun, _ = year
    el = sun[:, 1]
    assert 1.0 < el.max() < 1.8  # el eje lunar se inclina unos 1.5°
    assert -1.8 < el.min() < -1.0


@necesita_kernels
def test_sol_da_una_vuelta_por_mes_lunar(year):
    sun, _ = year
    az = np.unwrap(np.radians(sun[:709, 0]))  # ~29.5 días
    assert abs(abs(az[-1] - az[0]) - 2 * np.pi) < 0.15


@necesita_kernels
def test_tierra_oscila_por_la_libracion(year):
    _, earth = year
    el = earth[:, 1]
    assert 5.0 < el.max() < 7.5  # libración en latitud, unos ±6.7°
    assert -8.0 < el.min() < -5.0


@necesita_kernels
def test_tierra_sobre_el_horizonte_casi_la_mitad(year):
    _, earth = year
    assert 0.40 < (earth[:, 1] > 0).mean() < 0.60


@necesita_kernels
def test_radios_angulares_del_sol_y_la_tierra(eph):
    ets = Ephemeris.time_grid("2027-01-01T00:00:00", 366, 6.0)
    sol = Ephemeris.angular_radius_deg("SUN", eph.observe("SUN", POLO, ets)[:, 2])
    tierra = Ephemeris.angular_radius_deg(
        "EARTH", eph.observe("EARTH", POLO, ets)[:, 2]
    )
    assert (
        0.258 < sol.min() and sol.max() < 0.275
    )  # ~0.262° en el afelio, ~0.271° en el perihelio
    assert (
        0.85 < tierra.min() and tierra.max() < 1.1
    )  # ~0.90° en el apogeo, ~1.03° en el perigeo


@necesita_kernels
def test_azel_es_la_parte_angular_de_observe(eph):
    ets = Ephemeris.time_grid("2027-01-01T00:00:00", 2, 1.0)
    assert np.array_equal(eph.sun_azel(POLO, ets), eph.observe("SUN", POLO, ets)[:, :2])
