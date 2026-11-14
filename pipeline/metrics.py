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
