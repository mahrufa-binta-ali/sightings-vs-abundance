import rasterio
import numpy as np
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[1]

raster_path = (
    ROOT
    / "data"
    / "raw"
    / "cornell"
    / "NY_BREEDING_TIF"
    / "NY_Wood-Thrush_mean_breeding_abundance_2023.tif"
)

print("\nReading:")
print(raster_path)

with rasterio.open(raster_path) as src:

    data = src.read(1)

    print("\n--- RASTER INFO ---")
    print("CRS:", src.crs)
    print("Width:", src.width)
    print("Height:", src.height)
    print("Bounds:", src.bounds)
    print("Resolution:", src.res)
    print("NoData value:", src.nodata)

    # remove NoData / invalid cells
    valid = data.astype(float)

    if src.nodata is not None:
        valid[valid == src.nodata] = np.nan

    valid[~np.isfinite(valid)] = np.nan

    print("\n--- WOOD THRUSH ABUNDANCE ---")
    print("Minimum:", np.nanmin(valid))
    print("Maximum:", np.nanmax(valid))
    print("Mean:", np.nanmean(valid))
    print("Valid cells:", np.sum(~np.isnan(valid)))