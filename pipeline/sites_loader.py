import json
from pathlib import Path

from .models import Site


class SiteError(ValueError):
    pass


class SiteLoader:
    LAT_MIN, LAT_MAX = -90.0, -80.0  # zona que cubre el DEM

    def validate(self, site: Site) -> None:
        if not site.name:
            raise SiteError("sitio sin nombre")
        if not (self.LAT_MIN <= site.lat <= self.LAT_MAX):
            raise SiteError(
                f"{site.name}: lat {site.lat} fuera de [{self.LAT_MIN}, {self.LAT_MAX}]"
            )
        if not (-180.0 <= site.lon <= 180.0):
            raise SiteError(f"{site.name}: lon {site.lon} fuera de [-180, 180]")

    def load(self, path: Path) -> list[Site]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        sites: list[Site] = []
        names: set[str] = set()
        for i, d in enumerate(data):
            try:
                site = Site(
                    name=d["name"],
                    lat=float(d["lat"]),
                    lon=float(d["lon"]),
                    note=d.get("note", ""),
                )
            except (KeyError, TypeError, ValueError) as e:
                raise SiteError(
                    f"sitio #{i}: datos incompletos o inválidos ({e})"
                ) from e
            self.validate(site)
            if site.name in names:
                raise SiteError(f"nombre repetido: {site.name}")
            names.add(site.name)
            sites.append(site)
        return sites
