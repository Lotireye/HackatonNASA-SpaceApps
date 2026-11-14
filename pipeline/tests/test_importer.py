from dataclasses import replace

import numpy as np
import pytest

from pipeline.config import Config
from pipeline.dem_loader import DemError
from pipeline.importer import DataImporter, DataImportError
from pipeline.kernels import KernelManager

CFG = Config()
HAY_DATOS = (
    CFG.dem_path.exists()
    and not KernelManager(CFG.raw_dir, CFG.kernel_files).check_files()
)
necesita_datos = pytest.mark.skipif(
    not HAY_DATOS, reason="faltan datos reales en data/raw"
)


def test_error_junta_todos_los_problemas(tmp_path):
    cfg = replace(CFG, raw_dir=tmp_path / "raw", sites_file=tmp_path / "no.json")
    with pytest.raises(DataImportError) as e:
        DataImporter(cfg).import_all()
    msg = str(e.value)
    assert "No existe" in msg and "Falta el kernel" in msg and "Falta el DEM" in msg


@necesita_datos
def test_importa_todo_y_libera():
    with DataImporter(CFG).import_all() as data:
        assert len(data.sites) >= 1
        assert data.dem.pixel_m > 0
    with pytest.raises(DemError):  # tras salir, el DEM quedó cerrado
        _ = data.dem.bounds


@necesita_datos
def test_cache_de_recortes_y_su_invalidacion(tmp_path):
    cfg = replace(CFG, interim_dir=tmp_path, radius_km=10.0)
    with DataImporter(cfg).import_all() as data:
        s = data.sites[0]
        p1 = data.get_patch(s)
        assert (tmp_path / f"{s.name}.npz").exists()
        p2 = data.get_patch(s)  # esta vez sale del caché
        assert np.array_equal(p1.elevation, p2.elevation, equal_nan=True)

    # con otro radio, el recorte guardado ya no sirve y se recalcula
    with DataImporter(replace(cfg, radius_km=12.0)).import_all() as data:
        p3 = data.get_patch(data.sites[0])
        assert p3.radius_km == 12.0
        assert p3.elevation.shape != p1.elevation.shape
