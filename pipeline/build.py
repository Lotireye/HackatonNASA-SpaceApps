import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np

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
                mask = HorizonMask.compute(patch, cfg.n_azimuths, cfg.observer_height_m)
                ground = float(patch.site_height)
                h = ground + cfg.observer_height_m

                sun_o = eph.observe("SUN", site, ets, h)
                earth_o = eph.observe("EARTH", site, ets, h)
                sun, earth = sun_o[:, :2], earth_o[:, :2]

                # criterio del centro del disco (compatible con las corridas anteriores)
                sun_vis = calc.visible(sun, mask, calc.radius["sun"])
                earth_vis = calc.visible(earth, mask, calc.radius["earth"])

                # disco con su radio aparente real en cada instante
                sun_frac = calc.visible_fraction(
                    sun, mask, Ephemeris.angular_radius_deg("SUN", sun_o[:, 2])
                )
                earth_frac = calc.visible_fraction(
                    earth, mask, Ephemeris.angular_radius_deg("EARTH", earth_o[:, 2])
                )

                metrics = calc.summarize(sun_vis, earth_vis, cfg.step_hours)
                metrics.update(calc.summarize_disk(sun_frac, earth_frac))

                truncated = round(
                    100.0
                    * float(
                        np.mean(
                            data.dem.ray_limits_m(site, 360) < cfg.radius_km * 1000.0
                        )
                    ),
                    1,
                )

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
                        metrics=metrics,
                        meta={
                            "dem": cfg.dem_file,
                            "pixel_m": float(patch.pixel_m),
                            "radius_km": float(patch.radius_km),
                            "site_height_m": round(ground, 1),
                            "observer_height_m": cfg.observer_height_m,
                            "n_azimuths": cfg.n_azimuths,
                            "horizon_gaps": int(
                                mask.n_az - sum(v is not None for v in mask.to_list())
                            ),
                            "truncated_pct": truncated,
                            "visible_criterion": "centro del disco",
                            "fraction_model": "disco con radio aparente real (R_sol 695700 km, R_tierra 6378.137 km)",
                        },
                        sun_fraction=sun_frac,
                        earth_fraction=earth_frac,
                    )
                )

        for r in results:
            if r.meta["truncated_pct"] > 0:
                print(
                    f"AVISO {r.site.name}: {r.meta['truncated_pct']}% de los rayos sale del DEM "
                    f"con radio {cfg.radius_km:.0f} km"
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
            f"{r.site.name}: Sol centro {m['pct_sun']:.1f}% | energía {m['sun_energy_pct']:.1f}% "
            f"| Tierra centro {m['pct_earth']:.1f}% | completa {m['pct_earth_full']:.1f}% "
            f"| ambos (centro) {m['pct_both']:.1f}%"
        )
    print(f"JSON escritos en {pipe.save(res)}")
