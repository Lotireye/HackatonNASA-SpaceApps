import numpy as np

from .horizon import HorizonMask

SUN_RADIUS_DEG = 0.267  # radio aparente del Sol (referencia, no se usa por defecto)
EARTH_RADIUS_DEG = 0.95  # radio aparente de la Tierra vista desde la Luna (idem)


def longest_run(flags) -> int:
    """Largo, en pasos, de la racha más larga de True."""
    f = np.asarray(flags, dtype=bool)
    if not f.any():
        return 0
    d = np.diff(np.concatenate(([False], f, [False])).astype(int))
    return int((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).max())


class MetricsCalculator:
    def __init__(self, sun_radius_deg: float = 0.0, earth_radius_deg: float = 0.0):
        """radio 0 = se usa el centro del disco; con radio r, basta que asome el borde superior."""
        self.radius = {"sun": sun_radius_deg, "earth": earth_radius_deg}

    @staticmethod
    def _horizon(azel: np.ndarray, mask: HorizonMask) -> np.ndarray:
        h = np.asarray(mask.elevation_at(azel[:, 0]), dtype=float)
        return np.where(np.isfinite(h), h, 0.0)  # sin dato de terreno: se asume plano

    def visible(
        self, azel: np.ndarray, mask: HorizonMask, body_radius_deg: float = 0.0
    ) -> np.ndarray:
        """bool (N,): True si el astro queda por encima del horizonte del terreno."""
        return (azel[:, 1] + body_radius_deg) > self._horizon(azel, mask)

    @staticmethod
    def percent(flags) -> float:
        return float(np.mean(np.asarray(flags, dtype=bool)) * 100.0)

    def summarize(self, sun_vis, earth_vis, step_h: float) -> dict:
        sun, earth = np.asarray(sun_vis, bool), np.asarray(earth_vis, bool)
        return {
            "pct_sun": round(self.percent(sun), 2),
            "pct_earth": round(self.percent(earth), 2),
            "pct_both": round(self.percent(sun & earth), 2),
            "max_dark_h": round(longest_run(~sun) * step_h, 2),
            "max_no_earth_h": round(longest_run(~earth) * step_h, 2),
        }

    def visible_fraction(
        self, azel: np.ndarray, mask: HorizonMask, radius_deg, n_cols: int = 41
    ) -> np.ndarray:
        """Fracción (0 a 1) del disco por encima del horizonte, en cada instante.

        radius_deg: radio aparente en grados (un valor, o un arreglo con uno por instante).
        """
        r = np.broadcast_to(np.asarray(radius_deg, dtype=float), (len(azel),))
        if np.all(r <= 0):
            return (azel[:, 1] > self._horizon(azel, mask)).astype(float)
        k = (np.arange(n_cols) + 0.5) / n_cols * 2.0 - 1.0  # franjas en [-1, 1]
        u = r[:, None] * k[None, :]  # (T, K) desplazamiento horizontal (°)
        w = np.sqrt(np.maximum(r[:, None] ** 2 - u**2, 0.0))  # semicuerda vertical (°)
        el_c = azel[:, 1][:, None]
        az_k = azel[:, 0][:, None] + u / np.cos(
            np.radians(el_c)
        )  # azimut de cada franja
        h = np.asarray(mask.elevation_at(az_k), dtype=float)
        h = np.where(np.isfinite(h), h, 0.0)
        vis = np.clip(el_c + w - np.maximum(h, el_c - w), 0.0, 2.0 * w)
        return vis.sum(axis=1) / np.maximum((2.0 * w).sum(axis=1), 1e-12)

    def summarize_disk(self, sun_frac, earth_frac) -> dict:
        sf, ef = np.asarray(sun_frac, dtype=float), np.asarray(earth_frac, dtype=float)
        eps = 1e-9
        return {
            "sun_energy_pct": round(
                float(sf.mean() * 100.0), 2
            ),  # luz recibida, proporcional al disco visible
            "pct_sun_any": round(
                self.percent(sf > eps), 2
            ),  # al menos un pedazo del Sol
            "pct_sun_full": round(self.percent(sf > 1 - eps), 2),  # Sol completo
            "pct_earth_any": round(
                self.percent(ef > eps), 2
            ),  # al menos un pedazo de la Tierra
            "pct_earth_full": round(self.percent(ef > 1 - eps), 2),  # Tierra completa
        }
