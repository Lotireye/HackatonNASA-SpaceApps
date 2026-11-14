import pytest
from pipeline.config import Config
from pipeline.kernels import KernelManager, KernelError

CFG = Config()
FALTAN_REALES = bool(KernelManager(CFG.raw_dir, CFG.kernel_files).check_files())


def test_check_files_detecta_faltantes(tmp_path):
    (tmp_path / "a.tls").write_text("x")
    km = KernelManager(tmp_path, ["a.tls", "b.bsp"])
    assert km.check_files() == [tmp_path / "b.bsp"]


def test_load_all_falla_si_faltan(tmp_path):
    km = KernelManager(tmp_path, ["no_existe.bsp"])
    with pytest.raises(KernelError):
        km.load_all()


@pytest.mark.skipif(FALTAN_REALES, reason="faltan los kernels reales en data/raw")
def test_verify_con_kernels_reales():
    with KernelManager(CFG.raw_dir, CFG.kernel_files) as km:
        assert 350_000 < km.verify() < 410_000
