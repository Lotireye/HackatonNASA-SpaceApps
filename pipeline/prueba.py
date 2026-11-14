import numpy as np, matplotlib.pyplot as plt
from pipeline.importer import DataImporter

with DataImporter().import_all() as data:
    fig, axs = plt.subplots(2, 3, figsize=(13, 8))
    for ax, s in zip(axs.flat, data.sites):
        p = data.get_patch(s)
        ax.imshow(p.elevation, cmap="terrain")
        ax.plot(*p.site_px, "r+", ms=14)
        ax.set_title(s.name)
        ax.axis("off")
plt.show()
