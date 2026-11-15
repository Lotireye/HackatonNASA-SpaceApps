"""Exporta el relieve del polo sur (hillshade del DEM) como imagen de fondo del mapa web.

Uso:  python -m pipeline.export_map
Escribe web/data/map.png y web/data/map.json (límites del DEM en metros).
"""

import json

import numpy as np
import rasterio
from matplotlib import pyplot as plt
from rasterio.enums import Resampling

from .config import Config


def hillshade(
    z: np.ndarray,
    pix: float,
    vert_exag: float = 2.0,
    az_deg: float = 315.0,
    alt_deg: float = 25.0,
) -> np.ndarray:
    """Sombreado de relieve normalizado a [0, 1], con luz desde el noroeste."""
    dzdx = np.gradient(z, axis=1) / pix * vert_exag
    dzdy = -np.gradient(z, axis=0) / pix * vert_exag  # las filas crecen hacia el sur
    az, alt = np.radians(az_deg), np.radians(alt_deg)
    lx, ly, lz = np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)
    shade = (-dzdx * lx - dzdy * ly + lz) / np.sqrt(1.0 + dzdx**2 + dzdy**2)
    lo, hi = np.percentile(shade, [2, 98])
    return np.clip((shade - lo) / (hi - lo), 0.0, 1.0)


def main(size: int = 1200) -> None:
    cfg = Config()
    with rasterio.open(cfg.dem_path) as src:
        z = src.read(1, out_shape=(size, size), resampling=Resampling.average).astype(
            "float32"
        )
        b = src.bounds
    pix = (b.right - b.left) / size  # m/píxel tras reducir
    z = np.where(np.isfinite(z), z, np.nanmedian(z))
    img = hillshade(z, pix) ** 1.3 * 0.9  # algo más oscuro para el tema oscuro
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    plt.imsave(cfg.out_dir / "map.png", img, cmap="gray", vmin=0, vmax=1)
    (cfg.out_dir / "map.json").write_text(
        json.dumps(
            {"left_m": b.left, "right_m": b.right, "top_m": b.top, "bottom_m": b.bottom}
        ),
        encoding="utf-8",
    )
    print(f"map.png ({size}x{size}) y map.json escritos en {cfg.out_dir}")


if __name__ == "__main__":
    main()
