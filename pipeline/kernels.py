from pathlib import Path
from typing import Iterable

import numpy as np
import spiceypy as spice


class KernelError(RuntimeError):
    pass


class KernelManager:
    FRAME = "MOON_PA_DE440"

    def __init__(self, base_dir: Path, kernel_files: Iterable[str]):
        self.base_dir = Path(base_dir)
        self.kernel_files = tuple(kernel_files)
        self._loaded: list[Path] = []

    @property
    def paths(self) -> list[Path]:
        return [self.base_dir / k for k in self.kernel_files]

    def check_files(self) -> list[Path]:
        """Devuelve los kernels que faltan (lista vacía si están todos)."""
        return [p for p in self.paths if not p.exists()]

    def load_all(self) -> None:
        missing = self.check_files()
        if missing:
            lista = "\n  ".join(str(p) for p in missing)
            raise KernelError(f"Faltan kernels:\n  {lista}")
        for p in self.paths:
            if p not in self._loaded:
                spice.furnsh(str(p))
                self._loaded.append(p)

    def unload_all(self) -> None:
        for p in reversed(self._loaded):
            spice.unload(str(p))
        self._loaded.clear()

    def verify(self) -> float:
        """Comprueba que los kernels trabajan juntos. Devuelve la distancia Tierra-Luna (km)."""
        if not self._loaded:
            raise KernelError("Llama a load_all() antes de verify()")
        try:
            if spice.namfrm(self.FRAME) == 0:
                raise KernelError(
                    f"SPICE no reconoce el marco {self.FRAME}: revisa el .tf"
                )
            et = float(spice.str2et("2027-01-01T00:00:00"))
            pos, _ = spice.spkpos("EARTH", et, "J2000", "NONE", "MOON")
            dist = float(np.linalg.norm(pos))
            spice.pxform("J2000", self.FRAME, et)  # falla si falta el PCK
        except KernelError:
            raise
        except Exception as e:
            raise KernelError(
                f"Los kernels cargan pero no funcionan juntos: {e}"
            ) from e
        if not 350_000 < dist < 410_000:
            raise KernelError(f"Distancia Tierra-Luna absurda: {dist:,.0f} km")
        return dist

    def __enter__(self) -> "KernelManager":
        self.load_all()
        return self

    def __exit__(self, *exc) -> None:
        self.unload_all()


if __name__ == "__main__":
    from .config import Config

    cfg = Config()
    with KernelManager(cfg.raw_dir, cfg.kernel_files) as km:
        print(f"Kernels OK. Distancia Tierra-Luna: {km.verify():,.0f} km")
