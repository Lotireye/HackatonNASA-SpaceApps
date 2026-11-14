from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.io import DatasetReader
from rasterio.windows import Window
from .horizon import azimuth_dir_xy
from .models import DemPatch, Site


class DemError(RuntimeError):
    pass


class DemLoader:
    def __init__(self, tif_path: Path):
        self.tif_path = Path(tif_path)
        self._src: DatasetReader | None = None
        self._to_xy: Transformer | None = None

    # ---------- ciclo de vida ----------
    def open(self) -> "DemLoader":
        if not self.tif_path.exists():
            raise DemError(f"No existe el DEM: {self.tif_path}")
        self._src = rasterio.open(self.tif_path)
        # El CRS geográfico sale del propio archivo, así comparten esfera y datum
        crs = CRS.from_wkt(self._src.crs.to_wkt())
        self._to_xy = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
        return self

    def close(self) -> None:
        if self._src is not None:
            self._src.close()
        self._src = None
        self._to_xy = None

    def __enter__(self) -> "DemLoader":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def _require_open(self) -> tuple[DatasetReader, Transformer]:
        if self._src is None or self._to_xy is None:
            raise DemError("Llama a open() o usa 'with DemLoader(...)'")
        return self._src, self._to_xy

    # ---------- utilidades ----------
    @property
    def bounds(self):
        return self._require_open()[0].bounds

    @property
    def pixel_m(self) -> float:
        return float(self._require_open()[0].res[0])

    def lonlat_to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        _, to_xy = self._require_open()
        x, y = to_xy.transform(lon, lat)
        return float(x), float(y)

    def ray_limits_m(self, site: Site, n_az: int = 360) -> np.ndarray:
        """Distancia (m) que puede recorrer cada rayo antes de salir del DEM."""
        x0, y0 = self.lonlat_to_xy(site.lat, site.lon)
        b = self.bounds
        out = np.empty(n_az)
        for k in range(n_az):
            dx, dy = azimuth_dir_xy(k * 360.0 / n_az, site.lon)
            tx = (
                np.inf
                if abs(dx) < 1e-12
                else ((b.right - x0) if dx > 0 else (b.left - x0)) / dx
            )
            ty = (
                np.inf
                if abs(dy) < 1e-12
                else ((b.top - y0) if dy > 0 else (b.bottom - y0)) / dy
            )
            out[k] = min(tx, ty)
        return out

    # ---------- recorte ----------
    def crop(self, site: Site, radius_km: float = 40.0) -> DemPatch:
        src, _ = self._require_open()
        x, y = self.lonlat_to_xy(site.lat, site.lon)
        b = src.bounds
        if not (b.left <= x <= b.right and b.bottom <= y <= b.top):
            raise DemError(f"{site.name}: el sitio cae fuera del DEM")

        pix = float(src.res[0])  # m/píxel (píxeles cuadrados)
        col, row = (~src.transform) @ (x, y)  # píxel continuo, esquina sup-izq = 0
        half = int(np.ceil(radius_km * 1000.0 / pix))
        col0, row0 = int(round(col)) - half, int(round(row)) - half
        size = 2 * half + 1

        dem = src.read(
            1, window=Window(col0, row0, size, size), boundless=True, fill_value=np.nan
        ).astype("float32")
        # pasamos a la convención "el centro del elemento [i, j] está en (j, i)"
        site_px = (col - 0.5 - col0, row - 0.5 - row0)
        return DemPatch(
            site=site, elevation=dem, pixel_m=pix, site_px=site_px, radius_km=radius_km
        )

    # ---------- guardar / cargar (carpeta interim) ----------
    @staticmethod
    def save_patch(patch: DemPatch, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            elevation=patch.elevation,
            pixel_m=patch.pixel_m,
            site_px=np.array(patch.site_px),
            radius_km=patch.radius_km,
            name=patch.site.name,
            lat=patch.site.lat,
            lon=patch.site.lon,
            note=patch.site.note,
        )

    @staticmethod
    def load_patch(path: Path) -> DemPatch:
        d = np.load(path)
        site = Site(str(d["name"]), float(d["lat"]), float(d["lon"]), str(d["note"]))
        return DemPatch(
            site=site,
            elevation=d["elevation"],
            pixel_m=float(d["pixel_m"]),
            site_px=(float(d["site_px"][0]), float(d["site_px"][1])),
            radius_km=float(d["radius_km"]),
        )


if __name__ == "__main__":
    from .config import Config
    from .sites_loader import SiteLoader

    cfg = Config()
    with DemLoader(cfg.dem_path) as dem:
        for s in SiteLoader().load(cfg.sites_file):
            p = dem.crop(s, cfg.radius_km)
            dem.save_patch(p, cfg.interim_dir / f"{s.name}.npz")
            print(
                f"{s.name}: forma {p.elevation.shape}, "
                f"NaN {np.isnan(p.elevation).mean():.1%}, "
                f"altura del sitio {p.site_height:,.0f} m, "
                f"rango {np.nanmin(p.elevation):,.0f} a {np.nanmax(p.elevation):,.0f} m"
            )
