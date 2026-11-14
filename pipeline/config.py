from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    raw_dir: Path = ROOT / "data" / "raw"
    interim_dir: Path = ROOT / "data" / "interim"
    sites_file: Path = ROOT / "data" / "sitios.json"
    out_dir: Path = ROOT / "web" / "data"
    dem_file: str = "LDEM_80S_80MPP_ADJ.TIF"
    kernel_files: tuple[str, ...] = (
        "kernels/lsk/naif0012.tls",
        "kernels/spk/de440s.bsp",
        "kernels/pck/moon_pa_de440_200625.bpc",
        "kernels/fk/moon_de440_250416.tf",
    )
    radius_km: float = 40.0
    step_hours: float = 1.0
    n_azimuths: int = 360

    @property
    def dem_path(self) -> Path:
        return self.raw_dir / "dem" / self.dem_file
