import json, sys
from pathlib import Path
import numpy as np
import spiceypy as spice
import rasterio

RAW = Path("data/raw")
R = 1737400.0
ok = True


def paso(msg, cond, detalle=""):
    global ok
    print(
        ("[OK]    " if cond else "[FALLA]    ")
        + msg
        + (f" {detalle}" if detalle else "")
    )
    ok = ok and bool(cond)
    return bool(cond)


KERNELS = [
    RAW / "kernels/lsk/naif0012.tls",
    RAW / "kernels/spk/de440s.bsp",
    RAW / "kernels/pck/moon_pa_de440_200625.bpc",
    RAW / "kernels/fk/moon_de440_250416.tf",
]
todos = True
for k in KERNELS:
    existe = paso(f"existe {k}", k.exists())
    if existe:
        spice.furnsh(str(k))
    todos = todos and existe

if todos:
    try:
        et = spice.str2et("2027-01-01T00:00:00")
        pos, _ = spice.spkpos("EARTH", et, "J2000", "NONE", "MOON")
        dist = float(np.linalg.norm(pos))
        paso(
            "SPK: distancia Tierra-Luna razonable",
            350_000 < dist < 410_000,
            f"({dist:,.0f} km)",
        )
        rot = spice.pxform("J2000", "MOON_PA_DE440", et)
        paso("PCK + FK: rotación J2000 -> MOON_PA_DE440", np.shape(rot) == (3, 3))
    except Exception as e:
        paso("cálculo con los kernels", False, str(e))

tifs = sorted((RAW / "dem").glob("LDEM_80S_*MPP_ADJ.TIF"))
if paso("hay un DEM LDEM_80S_*MPP_ADJ.TIF", len(tifs) >= 1):
    tif = tifs[0]
    try:
        with rasterio.open(tif) as src:
            print(f"        archivo: {tif.name}")
            print(
                f"        tamaño: {src.width} x {src.height} px | res: {src.res} m/px"
            )
            print(f"        CRS: {src.crs}")
            print(
                f"        nodata: {src.nodata} | escala/offset: {src.scales[0]}/{src.offsets[0]}"
            )

            # punto de prueba a 0.1° del polo, proyección estereográfica polar sur
            lat, lon = -89.9, 0.0
            c = np.radians(90.0 + lat)  # colatitud desde el polo sur
            rho = 2 * R * np.tan(c / 2)
            x, y = rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
            b = src.bounds
            dentro = b.left < x < b.right and b.bottom < y < b.top
            paso("el punto (-89.9, 0) cae dentro del DEM", dentro)
            if dentro:
                v = next(src.sample([(x, y)]))[0] * src.scales[0] + src.offsets[0]
                paso(
                    "elevación válida en ese punto",
                    np.isfinite(v) and abs(v) < 10_000,
                    f"({v:,.0f} m)",
                )
    except Exception as e:
        paso("abrir el DEM", False, str(e))

# ---------- 3. sites.json ----------
try:
    sites = json.load(open("data/sitios.json"))
    nombres = [s["name"] for s in sites]
    paso("sites.json se lee", True, f"({nombres})")
    paso("nombres no repetidos", len(nombres) == len(set(nombres)))
    paso(
        "lat entre -90 y -80, lon entre -180 y 180",
        all(-90 <= s["lat"] <= -80 and -180 <= s["lon"] <= 180 for s in sites),
    )
except Exception as e:
    paso("leer sites.json", False, str(e))

spice.kclear()
print("\nTODO LISTO" if ok else "\nHAY FALLAS: revisa las líneas [FALLA]")
sys.exit(0 if ok else 1)
