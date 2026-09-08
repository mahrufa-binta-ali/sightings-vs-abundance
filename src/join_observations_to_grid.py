import rasterio
import pandas as pd
import numpy as np

from pathlib import Path
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

raster_path = (
    ROOT
    / "data"
    / "raw"
    / "cornell"
    / "NY_BREEDING_TIF"
    / "NY_Wood-Thrush_mean_breeding_abundance_2023.tif"
)

observation_path = (
    ROOT
    / "data"
    / "raw"
    / "gbif"
    / "wood_thrush_ebird_ny_2023_breeding.csv"
)

abundance_path = (
    ROOT
    / "data"
    / "processed"
    / "wood_thrush_abundance_cells.csv"
)

output_path = (
    ROOT
    / "data"
    / "processed"
    / "wood_thrush_grid_2023.csv"
)


# ---------------------------------------------------------
# 1. Load observations and Cornell abundance cells
# ---------------------------------------------------------

obs = pd.read_csv(observation_path)
cells = pd.read_csv(abundance_path)

print("\nObservation records:", len(obs))
print("Cornell NY cells:", len(cells))


# ---------------------------------------------------------
# 2. Convert observation lon/lat -> Cornell raster CRS
# ---------------------------------------------------------

with rasterio.open(raster_path) as src:

    transformer = Transformer.from_crs(
        "EPSG:4326",
        src.crs,
        always_xy=True
    )

    xs, ys = transformer.transform(
        obs["lon"].to_numpy(),
        obs["lat"].to_numpy()
    )

    # Find raster row / column containing each observation
    rows, cols = rasterio.transform.rowcol(
        src.transform,
        xs,
        ys
    )


obs["row"] = np.asarray(rows)
obs["col"] = np.asarray(cols)


# ---------------------------------------------------------
# 3. Count observation records in each raster cell
# ---------------------------------------------------------

report_counts = (
    obs.groupby(["row", "col"])
    .size()
    .reset_index(name="report_count")
)

print("\nRaster cells containing >=1 eBird record:")
print(len(report_counts))


# ---------------------------------------------------------
# 4. Join counts onto Cornell NY cells
# ---------------------------------------------------------

merged = cells.merge(
    report_counts,
    on=["row", "col"],
    how="left"
)

merged["report_count"] = (
    merged["report_count"]
    .fillna(0)
    .astype(int)
)


# ---------------------------------------------------------
# 5. Check how many observations matched valid NY cells
# ---------------------------------------------------------

matched_records = merged["report_count"].sum()
unmatched_records = len(obs) - matched_records

print("\nMatched observation records:", matched_records)
print("Unmatched observation records:", unmatched_records)

print("\nCells with observations:")
print((merged["report_count"] > 0).sum())

print("\nReport-count statistics:")
print(
    merged.loc[
        merged["report_count"] > 0,
        "report_count"
    ].describe()
)


# ---------------------------------------------------------
# 6. Show busiest reporting cells
# ---------------------------------------------------------

print("\nTop 10 reporting cells:")

print(
    merged[
        [
            "row",
            "col",
            "lon",
            "lat",
            "report_count",
            "relative_abundance"
        ]
    ]
    .sort_values(
        "report_count",
        ascending=False
    )
    .head(10)
)


# ---------------------------------------------------------
# 7. Save
# ---------------------------------------------------------

output_path.parent.mkdir(
    parents=True,
    exist_ok=True
)

merged.to_csv(
    output_path,
    index=False
)

print("\nSaved:")
print(output_path)