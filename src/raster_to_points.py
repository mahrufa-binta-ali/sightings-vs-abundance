import io
import zipfile
import requests
import rasterio
import numpy as np
import pandas as pd
import geopandas as gpd

from pathlib import Path
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]

raster_path = (
    ROOT
    / "data"
    / "raw"
    / "cornell"
    / "NY_BREEDING_TIF"
    / "NY_Wood-Thrush_mean_breeding_abundance_2023.tif"
)

boundary_dir = (
    ROOT
    / "data"
    / "raw"
    / "boundaries"
)

boundary_zip = boundary_dir / "cb_2025_us_state_500k.zip"

output_path = (
    ROOT
    / "data"
    / "processed"
    / "wood_thrush_abundance_cells.csv"
)


# ---------------------------------------------------------
# 1. Download official Census state boundaries
# ---------------------------------------------------------

boundary_dir.mkdir(parents=True, exist_ok=True)

if not boundary_zip.exists():

    print("Downloading official U.S. Census state boundaries...")

    url = (
        "https://www2.census.gov/geo/tiger/GENZ2025/shp/"
        "cb_2025_us_state_500k.zip"
    )

    response = requests.get(url, timeout=60)
    response.raise_for_status()

    boundary_zip.write_bytes(response.content)

    print("Downloaded:", boundary_zip)


# ---------------------------------------------------------
# 2. Load New York boundary
# ---------------------------------------------------------

states = gpd.read_file(boundary_zip)

ny = states[states["NAME"] == "New York"].copy()

ny = ny.to_crs("EPSG:4326")

print("\nNew York boundary loaded.")


# ---------------------------------------------------------
# 3. Read Cornell raster
# ---------------------------------------------------------

with rasterio.open(raster_path) as src:

    data = src.read(1).astype(float)

    valid = np.isfinite(data)

    rows, cols = np.where(valid)

    abundance = data[rows, cols]

    xs, ys = rasterio.transform.xy(
        src.transform,
        rows,
        cols,
        offset="center"
    )

    xs = np.asarray(xs)
    ys = np.asarray(ys)

    transformer = Transformer.from_crs(
        src.crs,
        "EPSG:4326",
        always_xy=True
    )

    lons, lats = transformer.transform(xs, ys)


# ---------------------------------------------------------
# 4. Create geographic point layer
# ---------------------------------------------------------

df = pd.DataFrame({
    "row": rows,
    "col": cols,
    "lon": lons,
    "lat": lats,
    "relative_abundance": abundance
})

points = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(
        df["lon"],
        df["lat"]
    ),
    crs="EPSG:4326"
)


print("\nBefore New York clipping:", len(points))


# ---------------------------------------------------------
# 5. Keep ONLY raster-cell centres inside New York
# ---------------------------------------------------------

ny_geometry = ny.geometry.union_all()

inside_ny = points.geometry.within(ny_geometry)

points = points[inside_ny].copy()


# Remove geometry because PyDeck only needs lon / lat
df = pd.DataFrame(
    points.drop(columns="geometry")
)


# ---------------------------------------------------------
# 6. Save
# ---------------------------------------------------------

output_path.parent.mkdir(
    parents=True,
    exist_ok=True
)

df.to_csv(
    output_path,
    index=False
)


# ---------------------------------------------------------
# 7. Inspect
# ---------------------------------------------------------

print("After New York clipping:", len(df))

print("\nCoordinate ranges:")

print(
    "Longitude:",
    df["lon"].min(),
    "to",
    df["lon"].max()
)

print(
    "Latitude:",
    df["lat"].min(),
    "to",
    df["lat"].max()
)

print("\nAbundance:")

print(
    df["relative_abundance"].describe()
)

print("\nSaved:")
print(output_path)