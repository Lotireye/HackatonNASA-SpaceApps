import numpy as np
import spiceypy as spice

from .models import Site


class EphemerisError(RuntimeError):
    pass


def local_basis(
    lat_deg: float, lon_deg: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectores unitarios (este, norte, arriba) del sitio, en el marco fijo a la Luna."""
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    north = np.array(
        [-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)]
    )
    return east, north, up


class Ephemeris:
    R_MOON_M = 1_737_400.0
    FRAME = "MOON_ME_DE440_ME421"

    def __init__(self) -> None:
        if spice.namfrm(self.FRAME) == 0:
            raise EphemerisError(
                f"SPICE no reconoce el marco {self.FRAME}. "
                "¿Cargaste los kernels (KernelManager.load_all) y el .tf correcto?"
            )

    # ---------- tiempo ----------
    @staticmethod
    def time_grid(start_utc: str, days: float, step_hours: float = 1.0) -> np.ndarray:
        """Instantes ET (segundos SPICE) desde start_utc, cada step_hours, sin incluir el final."""
        et0 = float(spice.str2et(start_utc))
        n = int(round(days * 24.0 / step_hours))
        return et0 + np.arange(n) * step_hours * 3600.0

    @staticmethod
    def to_utc(ets) -> list[str]:
        return [str(spice.et2utc(float(e), "ISOC", 0)) for e in ets]

    # ---------- cálculo ----------
    def azel(self, target: str, site: Site, ets, height_m: float = 0.0) -> np.ndarray:
        """Array (N, 2): columna 0 = azimut (0° N, 90° E), columna 1 = elevación (°)."""
        east, north, up = local_basis(site.lat, site.lon)
        r_site_km = up * (self.R_MOON_M + height_m) / 1000.0
        out = np.empty((len(ets), 2))
        for k, et in enumerate(ets):
            t = float(et)
            pos, _ = spice.spkpos(target, t, "J2000", "LT+S", "MOON")
            rot = spice.pxform("J2000", self.FRAME, t)
            v = np.asarray(rot) @ np.asarray(pos) - r_site_km  # vector sitio -> astro
            e, n, u = v @ east, v @ north, v @ up
            out[k, 0] = np.degrees(np.arctan2(e, n)) % 360.0
            out[k, 1] = np.degrees(np.arctan2(u, np.hypot(e, n)))
        return out

    def sun_azel(self, site: Site, ets, height_m: float = 0.0) -> np.ndarray:
        return self.azel("SUN", site, ets, height_m)

    def earth_azel(self, site: Site, ets, height_m: float = 0.0) -> np.ndarray:
        return self.azel("EARTH", site, ets, height_m)


if __name__ == "__main__":
    from .importer import DataImporter

    with DataImporter().import_all() as data:
        eph = Ephemeris()
        ets = Ephemeris.time_grid("2027-01-01T00:00:00", days=365, step_hours=1.0)
        for s in data.sites:
            sun, earth = eph.sun_azel(s, ets), eph.earth_azel(s, ets)
            print(
                f"{s.name}: Sol el [{sun[:, 1].min():.2f}, {sun[:, 1].max():.2f}]°  "
                f"Tierra el [{earth[:, 1].min():.2f}, {earth[:, 1].max():.2f}]°  "
                f"Tierra sobre el horizonte plano: {(earth[:, 1] > 0).mean():.0%}"
            )
