import argparse
from dataclasses import replace
from pathlib import Path

from .config import Config
from .ephemeris import Ephemeris
from .horizon import HorizonMask
from .importer import DataImporter
from .metrics import MetricsCalculator
from .results import SiteResult, write_index


class Pipeline:
    def __init__(
        self, config: Config | None = None, calculator: MetricsCalculator | None = None
    ):
        self.config = config or Config()
        self.calc = calculator or MetricsCalculator()

    def run(self) -> list[SiteResult]:
        cfg, calc = self.config, self.calc
        results: list[SiteResult] = []
        with DataImporter(cfg).import_all() as data:
            eph = Ephemeris()
            ets = Ephemeris.time_grid(cfg.start_utc, cfg.days, cfg.step_hours)
            t0 = Ephemeris.to_utc(ets[:1])[0] + "Z"
            for site in data.sites:
                patch = data.get_patch(site)
                mask = HorizonMask.compute(patch, cfg.n_azimuths)
                h = patch.site_height
                sun = eph.sun_azel(site, ets, h)
                earth = eph.earth_azel(site, ets, h)
                sun_vis = calc.visible(sun, mask, calc.radius["sun"])
                earth_vis = calc.visible(earth, mask, calc.radius["earth"])
                results.append(
                    SiteResult(
                        site=site,
                        t0_utc=t0,
                        step_h=cfg.step_hours,
                        horizon=mask,
                        sun_azel=sun,
                        earth_azel=earth,
                        sun_visible=sun_vis,
                        earth_visible=earth_vis,
                        metrics=calc.summarize(sun_vis, earth_vis, cfg.step_hours),
                        meta={
                            "dem": cfg.dem_file,
                            "pixel_m": float(patch.pixel_m),
                            "radius_km": float(patch.radius_km),
                            "site_height_m": round(float(h), 1),
                            "horizon_gaps": int(
                                mask.n_az - sum(v is not None for v in mask.to_list())
                            ),
                            "sun_radius_deg": calc.radius["sun"],
                            "earth_radius_deg": calc.radius["earth"],
                        },
                    )
                )
        return results

    def save(self, results: list[SiteResult]) -> Path:
        out = self.config.out_dir
        nombres = [r.filename for r in results]
        if len(set(nombres)) != len(nombres):
            raise ValueError(
                "Dos sitios generan el mismo nombre de archivo; cambia sus nombres"
            )
        for r in results:
            r.to_json(out / "sites" / r.filename)
        write_index(results, out)
        return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Genera los JSON por sitio para el frontend"
    )
    ap.add_argument("--start", help="inicio UTC, p. ej. 2027-03-01T00:00:00")
    ap.add_argument("--days", type=int, help="duración en días")
    ap.add_argument("--step", type=float, help="paso en horas")
    a = ap.parse_args()
    over = {
        k: v
        for k, v in {"start_utc": a.start, "days": a.days, "step_hours": a.step}.items()
        if v is not None
    }
    pipe = Pipeline(replace(Config(), **over))
    res = pipe.run()
    for r in res:
        m = r.metrics
        print(
            f"{r.site.name}: Sol {m['pct_sun']:.1f}% | Tierra {m['pct_earth']:.1f}% | "
            f"ambos {m['pct_both']:.1f}% | noche máx {m['max_dark_h']:.0f} h | "
            f"sin Tierra máx {m['max_no_earth_h']:.0f} h"
        )
    print(f"JSON escritos en {pipe.save(res)}")
