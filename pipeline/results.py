import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .horizon import HorizonMask
from .models import Site

SCHEMA = 1


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "sitio"


def _r(a, nd: int = 2) -> list:
    return np.round(np.asarray(a, dtype=float), nd).tolist()


@dataclass
class SiteResult:
    site: Site
    t0_utc: str
    step_h: float
    horizon: HorizonMask
    sun_azel: np.ndarray
    earth_azel: np.ndarray
    sun_visible: np.ndarray
    earth_visible: np.ndarray
    metrics: dict
    meta: dict = field(default_factory=dict)
    sun_fraction: np.ndarray | None = None
    earth_fraction: np.ndarray | None = None

    @property
    def filename(self) -> str:
        return f"{slug(self.site.name)}.json"

    def to_dict(self) -> dict:
        def body(azel, vis, frac=None):
            d = {
                "az": _r(azel[:, 0]),
                "el": _r(azel[:, 1]),
                "visible": np.asarray(vis, dtype=int).tolist(),
            }
            if frac is not None:
                d["fraction"] = _r(frac, 2)
            return d

        return {
            "schema": SCHEMA,
            "site": {
                "name": self.site.name,
                "lat": self.site.lat,
                "lon": self.site.lon,
                "note": self.site.note,
            },
            "t0": self.t0_utc,
            "step_h": self.step_h,
            "n": int(len(self.sun_visible)),
            "horizon": self.horizon.to_list(),
            "sun": body(self.sun_azel, self.sun_visible, self.sun_fraction),
            "earth": body(self.earth_azel, self.earth_visible, self.earth_fraction),
            "metrics": self.metrics,
            "meta": self.meta,
        }

    def to_json(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), separators=(",", ":"), allow_nan=False),
            encoding="utf-8",
        )


def write_index(results: list[SiteResult], out_dir: Path) -> None:
    """sites.json: lo que el frontend carga primero (mapa y comparador)."""
    index = [
        {
            "name": r.site.name,
            "lat": r.site.lat,
            "lon": r.site.lon,
            "note": r.site.note,
            "file": f"sites/{r.filename}",
            "metrics": r.metrics,
        }
        for r in results
    ]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sites.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
