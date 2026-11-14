from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Site:
    name: str
    lat: float
    lon: float
    note: str = ""


@dataclass(frozen=True, eq=False)
class DemPatch:
    """Recorte del DEM alrededor de un sitio.

    elevation: metros, NaN donde no hay dato. Fila 0 = arriba (y mayor).
    site_px:   (col, fila) continuas del sitio dentro del recorte. El centro
               del elemento [i, j] está en (col=j, fila=i).
    """
    site: Site
    elevation: np.ndarray
    pixel_m: float
    site_px: tuple[float, float]
    radius_km: float

    def sample(self, col: float, row: float) -> float:
        """Altura (m) por interpolación bilineal en coordenadas del recorte."""
        j0, i0 = int(np.floor(col)), int(np.floor(row))
        if i0 < 0 or j0 < 0:
            return float("nan")
        z = self.elevation[i0:i0 + 2, j0:j0 + 2]
        if z.shape != (2, 2):
            return float("nan")
        fx, fy = col - j0, row - i0
        w = np.array([[(1 - fy) * (1 - fx), (1 - fy) * fx],
                      [fy * (1 - fx),       fy * fx]])
        return float((z * w).sum())

    @property
    def site_height(self) -> float:
        return self.sample(*self.site_px)