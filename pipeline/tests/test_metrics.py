import numpy as np
import pytest

from pipeline.config import Config
from pipeline.ephemeris import Ephemeris
from pipeline.horizon import HorizonMask
from pipeline.kernels import KernelManager
from pipeline.metrics import MetricsCalculator, longest_run
from pipeline.models import Site

CFG = Config()
SITE = Site("s", -85.0, 0.0)
necesita_kernels = pytest.mark.skipif(
    bool(KernelManager(CFG.raw_dir, CFG.kernel_files).check_files()),
    reason="faltan kernels en data/raw",
)


def _plano():
    return HorizonMask(SITE, np.zeros(360))


def test_longest_run():
    assert longest_run([]) == 0
    assert longest_run([False, False]) == 0
    assert longest_run([True, True, False, True]) == 2
    assert longest_run([True] * 5) == 5


def test_visible_respeta_el_terreno():
    el = np.zeros(360)
    el[90] = 3.0  # colina de 3° al este
    azel = np.array([[90.0, 1.2], [270.0, 1.2]])
    v = MetricsCalculator().visible(azel, HorizonMask(SITE, el))
    assert v.tolist() == [False, True]


def test_horizonte_con_nan_se_trata_como_plano():
    m = HorizonMask(SITE, np.full(360, np.nan))
    v = MetricsCalculator().visible(np.array([[10.0, 1.0], [10.0, -1.0]]), m)
    assert v.tolist() == [True, False]


def test_radio_del_disco_cuenta_el_limbo():
    azel = np.array([[0.0, -0.5]])
    assert not MetricsCalculator().visible(azel, _plano())[0]
    assert MetricsCalculator().visible(azel, _plano(), body_radius_deg=1.0)[0]


def test_summarize():
    sun = [True, True, False, False]
    earth = [True, False, True, False]
    m = MetricsCalculator().summarize(sun, earth, step_h=2.0)
    assert m == {
        "pct_sun": 50.0,
        "pct_earth": 50.0,
        "pct_both": 25.0,
        "max_dark_h": 4.0,
        "max_no_earth_h": 2.0,
    }


@necesita_kernels
def test_horizonte_plano_en_el_polo_da_cerca_de_la_mitad():
    with KernelManager(CFG.raw_dir, CFG.kernel_files):
        eph = Ephemeris()
        ets = Ephemeris.time_grid("2027-01-01T00:00:00", 365, 1.0)
        polo = Site("polo", -89.9, 0.0)
        sun, earth = eph.sun_azel(polo, ets), eph.earth_azel(polo, ets)
    calc = MetricsCalculator()
    m = calc.summarize(calc.visible(sun, _plano()), calc.visible(earth, _plano()), 1.0)
    assert 40 < m["pct_sun"] < 60
    assert 40 < m["pct_earth"] < 60
    assert m["pct_both"] <= min(m["pct_sun"], m["pct_earth"])
