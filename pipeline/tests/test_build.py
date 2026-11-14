import json
from dataclasses import replace

import numpy as np
import pytest

from pipeline.build import Pipeline
from pipeline.config import Config
from pipeline.horizon import HorizonMask
from pipeline.kernels import KernelManager
from pipeline.models import Site
from pipeline.results import SiteResult, slug

CFG = Config()
HAY_DATOS = (
    CFG.dem_path.exists()
    and not KernelManager(CFG.raw_dir, CFG.kernel_files).check_files()
)
necesita_datos = pytest.mark.skipif(
    not HAY_DATOS, reason="faltan datos reales en data/raw"
)


def _resultado(n=24, azel=None):
    azel = np.zeros((n, 2)) if azel is None else azel
    vis = np.zeros(n, bool)
    return SiteResult(
        Site("Sitio Uno", -85.0, 0.0),
        "2027-01-01T00:00:00Z",
        1.0,
        HorizonMask(Site("Sitio Uno", -85.0, 0.0), np.zeros(360)),
        azel,
        azel,
        vis,
        vis,
        {"pct_sun": 0.0},
    )


def test_slug():
    assert slug("Shackleton Rim #1") == "shackleton-rim-1"
    assert slug("???") == "sitio"


def test_json_tiene_la_estructura_del_contrato(tmp_path):
    r = _resultado()
    r.to_json(tmp_path / "a.json")
    d = json.loads((tmp_path / "a.json").read_text())
    assert d["schema"] == 1 and d["n"] == 24 and len(d["horizon"]) == 360
    for b in ("sun", "earth"):
        assert len(d[b]["az"]) == len(d[b]["el"]) == len(d[b]["visible"]) == 24
    assert r.filename == "sitio-uno.json"


def test_json_rechaza_nan(tmp_path):
    azel = np.zeros((24, 2))
    azel[3, 0] = np.nan
    with pytest.raises(ValueError):
        _resultado(azel=azel).to_json(tmp_path / "a.json")


@necesita_datos
def test_pipeline_escribe_json_consistente(tmp_path):
    cfg = replace(
        CFG, out_dir=tmp_path / "web", interim_dir=tmp_path / "interim", days=10
    )
    pipe = Pipeline(cfg)
    out = pipe.save(pipe.run())
    index = json.loads((out / "sites.json").read_text())
    assert len(index) >= 1
    for entry in index:
        d = json.loads((out / entry["file"]).read_text())
        assert d["n"] == 240 and len(d["horizon"]) == 360
        for b in ("sun", "earth"):
            assert len(d[b]["az"]) == len(d[b]["el"]) == len(d[b]["visible"]) == 240
        m = d["metrics"]
        assert 0 <= m["pct_both"] <= min(m["pct_sun"], m["pct_earth"]) <= 100
