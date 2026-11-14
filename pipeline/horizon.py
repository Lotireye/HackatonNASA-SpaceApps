import numpy as np

from .models import DemPatch, Site

R_MOON_M = 1_737_400.0


class HorizonError(RuntimeError):
    pass


def azimuth_dir_xy(az_deg: float, lon_deg: float) -> np.ndarray:
    """Dirección unitaria (x, y) en el mapa polar sur para un azimut (0° N, 90° E) en un sitio de longitud lon.

    Norte = radial hacia afuera del polo; Este = sentido de lon creciente (horario visto desde arriba).
    """
    a, lam = np.radians(az_deg), np.radians(lon_deg)
    north = np.array([np.sin(lam), np.cos(lam)])
    east = np.array([np.cos(lam), -np.sin(lam)])
    return np.cos(a) * north + np.sin(a) * east


def _bilinear(z: np.ndarray, col: np.ndarray, row: np.ndarray) -> np.ndarray:
    """Interpolación bilineal; NaN fuera del recorte. El centro de z[i, j] está en (col=j, row=i)."""
    j0, i0 = np.floor(col).astype(int), np.floor(row).astype(int)
    ok = (i0 >= 0) & (j0 >= 0) & (i0 < z.shape[0] - 1) & (j0 < z.shape[1] - 1)
    i0c = np.clip(i0, 0, z.shape[0] - 2)
    j0c = np.clip(j0, 0, z.shape[1] - 2)
    fx, fy = col - j0, row - i0
    val = (
        z[i0c, j0c] * (1 - fy) * (1 - fx)
        + z[i0c, j0c + 1] * (1 - fy) * fx
        + z[i0c + 1, j0c] * fy * (1 - fx)
        + z[i0c + 1, j0c + 1] * fy * fx
    )
    return np.where(ok, val, np.nan)


class HorizonMask:
    """Perfil del horizonte: el_deg[k] = elevación máxima del terreno en el azimut k * 360/n_az."""

    def __init__(self, site: Site, el_deg: np.ndarray):
        self.site = site
        self.el_deg = np.asarray(el_deg, dtype=float)

    @property
    def n_az(self) -> int:
        return len(self.el_deg)

    @property
    def az_deg(self) -> np.ndarray:
        return np.arange(self.n_az) * (360.0 / self.n_az)

    def elevation_at(self, az_deg):
        """Elevación del horizonte (°) en cualquier azimut, interpolando de forma circular."""
        pos = (np.asarray(az_deg, dtype=float) % 360.0) / (360.0 / self.n_az)
        base = np.floor(pos)
        i0 = base.astype(int) % self.n_az
        i1 = (i0 + 1) % self.n_az
        f = pos - base
        out = self.el_deg[i0] * (1 - f) + self.el_deg[i1] * f
        return float(out) if out.ndim == 0 else out

    def to_list(self, ndigits: int = 2) -> list:
        """Para el JSON del frontend; NaN pasa a None."""
        return [
            round(float(v), ndigits) if np.isfinite(v) else None for v in self.el_deg
        ]

    @classmethod
    def compute(
        cls,
        patch: DemPatch,
        n_az: int = 360,
        observer_height_m: float = 0.0,
        step_factor: float = 1.0,
    ) -> "HorizonMask":
        h0 = patch.site_height
        if not np.isfinite(h0):
            raise HorizonError(
                f"{patch.site.name}: no hay dato de elevación en el sitio"
            )

        pix = patch.pixel_m
        step = pix * step_factor
        n_d = int(patch.radius_km * 1000.0 // step)
        if n_d < 2:
            raise HorizonError("El recorte es demasiado pequeño para trazar rayos")

        az = np.arange(n_az) * (360.0 / n_az)
        a = np.radians(az)[:, None]  # (n_az, 1)
        d = (np.arange(1, n_d + 1) * step)[
            None, :
        ]  # (1, n_d), distancia en el mapa (m)

        lam = np.radians(patch.site.lon)
        nx, ny = np.sin(lam), np.cos(lam)  # norte en (x, y)
        ex, ey = np.cos(lam), -np.sin(lam)  # este en (x, y)
        dx = np.cos(a) * nx + np.sin(a) * ex
        dy = np.cos(a) * ny + np.sin(a) * ey

        c0, r0 = patch.site_px
        col = c0 + dx * d / pix  # x crece con la columna
        row = r0 - dy * d / pix  # y crece hacia arriba = fila decreciente
        z = _bilinear(patch.elevation, col, row)  # (n_az, n_d)

        theta = d / R_MOON_M  # separación angular sitio -> punto
        r_site = R_MOON_M + h0 + observer_height_m
        r_pt = R_MOON_M + z
        ang = np.degrees(
            np.arctan2(r_pt * np.cos(theta) - r_site, r_pt * np.sin(theta))
        )
        el = np.fmax.reduce(ang, axis=1)  # máximo ignorando NaN
        return cls(patch.site, el)


if __name__ == "__main__":
    from .importer import DataImporter

    with DataImporter().import_all() as data:
        for s in data.sites:
            m = HorizonMask.compute(data.get_patch(s))
            print(
                f"{s.name}: horizonte de {np.nanmin(m.el_deg):.2f}° a {np.nanmax(m.el_deg):.2f}° "
                f"(media {np.nanmean(m.el_deg):.2f}°)"
            )
