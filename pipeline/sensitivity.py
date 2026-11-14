import argparse
from dataclasses import replace

import numpy as np
from .config import Config
from .ephemeris import Ephemeris
from .horizon import HorizonMask
from .importer import DataImporter
from .metrics import MetricsCalculator


def main() -> None:
    ap = argparse.ArgumentParser(
        description="¿Cuánto cambian las métricas con el radio y los azimuts?"
    )
    ap.add_argument("site", help="nombre del sitio, como en sites.json")
    ap.add_argument(
        "--days", type=int, help="duración en días (por defecto la de Config)"
    )
    ap.add_argument("--radii", type=float, nargs="+", default=[40, 100, 150])
    ap.add_argument("--azimuths", type=int, nargs="+", default=[360, 1440])
    ap.add_argument(
        "--dem", help="archivo DEM en data/raw/dem, p. ej. LDEM_80S_40MPP_ADJ.TIF"
    )
    a = ap.parse_args()

    cfg = Config() if a.days is None else replace(Config(), days=a.days)
    calc = MetricsCalculator()
    with DataImporter(cfg).import_all() as data:
        por_nombre = {s.name.lower(): s for s in data.sites}
        if a.site.lower() not in por_nombre:
            raise SystemExit(
                f"Sitio desconocido. Opciones: {sorted(s.name for s in data.sites)}"
            )
        site = por_nombre[a.site.lower()]

        eph = Ephemeris()
        ets = Ephemeris.time_grid(cfg.start_utc, cfg.days, cfg.step_hours)
        h = float(data.dem.crop(site, 1.0).site_height) + cfg.observer_height_m
        sun, earth = (
            eph.observe("SUN", site, ets, h),
            eph.observe("EARTH", site, ets, h),
        )
        r_sun = Ephemeris.angular_radius_deg("SUN", sun[:, 2])
        r_earth = Ephemeris.angular_radius_deg("EARTH", earth[:, 2])
        lims = data.dem.ray_limits_m(site, 360)

        print(
            f"{site.name} | {cfg.days} días desde {cfg.start_utc} | observador {cfg.observer_height_m} m | DEM {cfg.dem_file}"
        )
        print(
            f"{'radio km':>9} {'azimuts':>8} | {'Sol centro':>10} {'Sol energía':>11} "
            f"{'Tierra centro':>13} {'Tierra completa':>15}"
        )
        for radius in a.radii:
            trunc = 100.0 * float(np.mean(lims < radius * 1000.0))
            patch = data.dem.crop(site, radius)
            for n_az in a.azimuths:
                mask = HorizonMask.compute(patch, n_az, cfg.observer_height_m)
                sc = calc.percent(calc.visible(sun[:, :2], mask))
                ec = calc.percent(calc.visible(earth[:, :2], mask))
                sf = calc.visible_fraction(sun[:, :2], mask, r_sun)
                ef = calc.visible_fraction(earth[:, :2], mask, r_earth)
                print(
                    f"{radius:9.0f} {n_az:8d} {trunc:8.0f}% | {sc:9.1f}% {100 * sf.mean():10.1f}% "
                    f"{ec:12.1f}% {calc.percent(ef > 1 - 1e-9):14.1f}%"
                )


if __name__ == "__main__":
    main()
