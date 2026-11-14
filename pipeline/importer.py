from dataclasses import dataclass

from .config import Config
from .dem_loader import DemLoader
from .kernels import KernelManager
from .models import DemPatch, Site
from .sites_loader import SiteLoader


class DataImportError(RuntimeError):
    pass


@dataclass
class ImportedData:
    config: Config
    sites: list[Site]
    kernels: KernelManager
    dem: DemLoader

    def get_patch(self, site: Site, use_cache: bool = True) -> DemPatch:
        """Recorte del DEM del sitio. Usa data/interim/ si el recorte guardado sigue valiendo."""
        cfg = self.config
        path = cfg.interim_dir / f"{site.name}.npz"
        if use_cache and path.exists():
            try:
                p = DemLoader.load_patch(path)
                if (
                    p.radius_km == cfg.radius_km
                    and p.pixel_m == self.dem.pixel_m
                    and (p.site.lat, p.site.lon) == (site.lat, site.lon)
                ):
                    return p
            except Exception:
                pass  # caché ilegible o corrupta: se recalcula
        p = self.dem.crop(site, cfg.radius_km)
        DemLoader.save_patch(p, path)
        return p

    def close(self) -> None:
        self.dem.close()
        self.kernels.unload_all()

    def __enter__(self) -> "ImportedData":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class DataImporter:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def import_all(self, verify: bool = True) -> ImportedData:
        cfg = self.config
        problems: list[str] = []

        # 1) sitios
        sites: list[Site] = []
        if not cfg.sites_file.exists():
            problems.append(f"No existe {cfg.sites_file}")
        else:
            try:
                sites = SiteLoader().load(cfg.sites_file)
                if not sites:
                    problems.append("sites.json no tiene ningún sitio")
            except ValueError as e:  # SiteError y JSON mal formado
                problems.append(f"sites.json: {e}")

        # 2) kernels y 3) DEM: solo existencia, para juntar todos los problemas de una vez
        kernels = KernelManager(cfg.raw_dir, cfg.kernel_files)
        problems += [f"Falta el kernel {p}" for p in kernels.check_files()]
        if not cfg.dem_path.exists():
            problems.append(f"Falta el DEM {cfg.dem_path}")

        if problems:
            raise DataImportError(
                "No se pudo importar:\n  - " + "\n  - ".join(problems)
            )

        # 4) abrir recursos; si algo falla, se deja todo cerrado
        dem = DemLoader(cfg.dem_path)
        try:
            kernels.load_all()
            if verify:
                kernels.verify()
            dem.open()
            b = dem.bounds
            fuera = []
            for s in sites:
                x, y = dem.lonlat_to_xy(s.lat, s.lon)
                if not (b.left <= x <= b.right and b.bottom <= y <= b.top):
                    fuera.append(s.name)
            if fuera:
                raise DataImportError(f"Sitios fuera del DEM: {fuera}")
        except Exception:
            dem.close()
            kernels.unload_all()
            raise
        return ImportedData(cfg, sites, kernels, dem)


if __name__ == "__main__":
    with DataImporter().import_all() as data:
        print(f"Sitios: {[s.name for s in data.sites]}")
        print(f"Kernels cargados: {len(data.kernels.paths)}")
        print(f"DEM: {data.dem.tif_path.name} a {data.dem.pixel_m:.0f} m/px")
        for s in data.sites:
            p = data.get_patch(s)
            print(
                f"  {s.name}: recorte {p.elevation.shape}, altura {p.site_height:,.0f} m"
            )
