from pathlib import Path
import json

import pandas as pd
from playwright.sync_api import sync_playwright

# Reuse all the working rendering functions
from render_frames import (
    OUT_DIR,
    WIDTH,
    HEIGHT,
    render_motion,
    render_hover_hold,
)


# =========================================================
# SETTINGS
# =========================================================

DATA_PATH = Path(
    "data/processed/wood_thrush_grid_divergence_2023.csv"
)

MANIFEST_PATH = (
    OUT_DIR
    / "showcase_manifest.json"
)

# Your existing cinematic render ends at frame 0509
START_FRAME = 510


# =========================================================
# HELPERS
# =========================================================

def geographic_band(df, lon_min, lon_max):

    return df[
        (df["lon"] >= lon_min)
        & (df["lon"] < lon_max)
    ].copy()


def pick_best(
    df,
    sort_column,
    ascending=False,
):

    if len(df) == 0:
        return None

    return (
        df
        .sort_values(
            sort_column,
            ascending=ascending
        )
        .iloc[0]
    )


# =========================================================
# SELECT 4 MODELED-ABUNDANCE CELLS
# =========================================================

def select_modeled_points(df):

    # We deliberately require:
    # 1. nonzero modeled abundance
    # 2. at least one eBird record
    #
    # So every tooltip looks meaningful.

    candidates = df[
        (df["relative_abundance"] > 0.10)
        & (df["report_count"] > 0)
    ].copy()

    regions = [
        (
            "Western New York",
            -79.80,
            -77.50
        ),
        (
            "Finger Lakes / Central NY",
            -77.50,
            -75.50
        ),
        (
            "Eastern / Capital Region",
            -75.50,
            -73.80
        ),
        (
            "Downstate / Long Island",
            -73.80,
            -71.80
        ),
    ]

    points = []

    for name, lon_min, lon_max in regions:

        subset = geographic_band(
            candidates,
            lon_min,
            lon_max
        )

        row = pick_best(
            subset,
            "relative_abundance",
            ascending=False
        )

        if row is not None:

            points.append({
                "name": name,
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "report_count": int(row["report_count"]),
                "relative_abundance": float(
                    row["relative_abundance"]
                ),
                "divergence": (
                    float(row["divergence"])
                    if pd.notna(row["divergence"])
                    else None
                ),
            })

    return points


# =========================================================
# SELECT 4 RAW-REPORTING CELLS
# =========================================================

def select_raw_points(df):

    # Require nonzero modeled abundance as well.
    # This avoids showcasing:
    #
    # 152 reports / abundance = 0
    #
    # which looked visually confusing.

    candidates = df[
        (df["report_count"] > 0)
        & (df["relative_abundance"] > 0.05)
    ].copy()

    regions = [
        (
            "Western New York",
            -79.80,
            -77.50
        ),
        (
            "Finger Lakes / Central NY",
            -77.50,
            -75.50
        ),
        (
            "Eastern / Capital Region",
            -75.50,
            -73.80
        ),
        (
            "Downstate / Long Island",
            -73.80,
            -71.80
        ),
    ]

    points = []

    for name, lon_min, lon_max in regions:

        subset = geographic_band(
            candidates,
            lon_min,
            lon_max
        )

        row = pick_best(
            subset,
            "report_count",
            ascending=False
        )

        if row is not None:

            points.append({
                "name": name,
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "report_count": int(row["report_count"]),
                "relative_abundance": float(
                    row["relative_abundance"]
                ),
                "divergence": (
                    float(row["divergence"])
                    if pd.notna(row["divergence"])
                    else None
                ),
            })

    return points


# =========================================================
# SELECT 4 DIVERGENCE CELLS
# =========================================================

def select_divergence_points(df):

    observed = df[
        (df["report_count"] > 0)
        & df["divergence"].notna()
    ].copy()

    # Require nonzero abundance for positive examples.
    positive = observed[
        (observed["divergence"] > 0.50)
        & (observed["relative_abundance"] > 0.05)
    ].copy()

    negative = observed[
        observed["divergence"] < -0.50
    ].copy()


    # Divide NY roughly into western and eastern halves.
    split_lon = -75.50

    positive_west = positive[
        positive["lon"] < split_lon
    ]

    positive_east = positive[
        positive["lon"] >= split_lon
    ]

    negative_west = negative[
        negative["lon"] < split_lon
    ]

    negative_east = negative[
        negative["lon"] >= split_lon
    ]


    selections = [
        (
            "Report-heavy — Western/Central NY",
            pick_best(
                positive_west,
                "divergence",
                ascending=False
            )
        ),
        (
            "Report-heavy — Eastern/Downstate NY",
            pick_best(
                positive_east,
                "divergence",
                ascending=False
            )
        ),
        (
            "Model-high — Western/Central NY",
            pick_best(
                negative_west,
                "divergence",
                ascending=True
            )
        ),
        (
            "Model-high — Eastern NY",
            pick_best(
                negative_east,
                "divergence",
                ascending=True
            )
        ),
    ]


    points = []

    for name, row in selections:

        if row is not None:

            points.append({
                "name": name,
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "report_count": int(row["report_count"]),
                "relative_abundance": float(
                    row["relative_abundance"]
                ),
                "divergence": float(
                    row["divergence"]
                ),
            })

    return points


# =========================================================
# CAMERA BUILDERS
# =========================================================

def regional_camera(point, bearing):

    return {
        "lat": point["lat"],
        "lon": point["lon"],
        "zoom": 7.65,
        "pitch": 53,
        "bearing": bearing,
    }


def close_camera(point, bearing):

    return {
        "lat": point["lat"],
        "lon": point["lon"],
        "zoom": 10.25,
        "pitch": 59,
        "bearing": bearing,
    }


# =========================================================
# RENDER ONE SHOWCASE POINT
# =========================================================

def render_showcase_point(
    page,
    frame_index,
    point,
    mode,
    bearing,
    abundance_threshold=0.08,
    divergence_threshold=0.60,
):

    start_frame = frame_index

    regional = regional_camera(
        point,
        bearing
    )

    close = close_camera(
        point,
        bearing
    )


    # -----------------------------------------------------
    # Regional → close-up
    # -----------------------------------------------------

    frame_index, final_url = render_motion(
        page,
        frame_index,
        name=f"{mode} — {point['name']}",
        mode=mode,
        start=regional,
        end=close,
        frames=10,
        abundance_threshold=abundance_threshold,
        divergence_threshold=divergence_threshold,
    )

    hover_start = frame_index


    # -----------------------------------------------------
    # Hover + value hold
    # -----------------------------------------------------

    frame_index = render_hover_hold(
        page,
        frame_index,
        final_url,
        hold_frames=14
    )

    hover_end = frame_index - 1

    return (
        frame_index,
        {
            "segment": mode,
            "name": point["name"],
            "start_frame": start_frame,
            "hover_start": hover_start,
            "hover_end": hover_end,
            "end_frame": frame_index - 1,
            "lat": point["lat"],
            "lon": point["lon"],
            "report_count": point["report_count"],
            "relative_abundance": point[
                "relative_abundance"
            ],
            "divergence": point[
                "divergence"
            ],
        }
    )


# =========================================================
# MAIN
# =========================================================

def main():

    df = pd.read_csv(
        DATA_PATH
    )


    modeled_points = select_modeled_points(
        df
    )

    raw_points = select_raw_points(
        df
    )

    divergence_points = select_divergence_points(
        df
    )


    # -----------------------------------------------------
    # Print exactly what was selected
    # -----------------------------------------------------

    print("\n======================================")
    print("MODELED SHOWCASE POINTS")
    print("======================================")

    for p in modeled_points:
        print(p)


    print("\n======================================")
    print("RAW REPORTING SHOWCASE POINTS")
    print("======================================")

    for p in raw_points:
        print(p)


    print("\n======================================")
    print("DIVERGENCE SHOWCASE POINTS")
    print("======================================")

    for p in divergence_points:
        print(p)


    frame_index = START_FRAME

    manifest = []


    # Bearings vary slightly so every stop
    # does not look identical.
    bearings = [
        12,
        22,
        16,
        28,
    ]


    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--enable-webgl",
                "--ignore-gpu-blocklist",
                "--use-angle=swiftshader",
            ]
        )

        page = browser.new_page(
            viewport={
                "width": WIDTH,
                "height": HEIGHT
            }
        )

        page.set_default_timeout(
            30000
        )

        page.set_default_navigation_timeout(
            60000
        )


        # =================================================
        # MODELED ABUNDANCE — 4 stops
        # =================================================

        print("\n🐦 Rendering modeled abundance showcase...")

        for point, bearing in zip(
            modeled_points,
            bearings
        ):

            frame_index, info = (
                render_showcase_point(
                    page,
                    frame_index,
                    point,
                    mode="Modeled abundance",
                    bearing=bearing,
                    abundance_threshold=0.08,
                )
            )

            manifest.append(
                info
            )


        # =================================================
        # RAW REPORTING — 4 stops
        # =================================================

        print("\n📍 Rendering raw reporting showcase...")

        for point, bearing in zip(
            raw_points,
            bearings
        ):

            frame_index, info = (
                render_showcase_point(
                    page,
                    frame_index,
                    point,
                    mode="Raw reporting",
                    bearing=bearing,
                )
            )

            manifest.append(
                info
            )


        # =================================================
        # DIVERGENCE — 4 stops
        # =================================================

        print("\n🔴🔵 Rendering divergence showcase...")

        for point, bearing in zip(
            divergence_points,
            bearings
        ):

            frame_index, info = (
                render_showcase_point(
                    page,
                    frame_index,
                    point,
                    mode="Reporting–abundance divergence",
                    bearing=bearing,
                    divergence_threshold=0.50,
                )
            )

            manifest.append(
                info
            )


        browser.close()


    # =====================================================
    # SAVE MANIFEST
    # =====================================================

    with open(
        MANIFEST_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2
        )


    print()
    print("======================================")
    print("🎉 SHOWCASE RENDER COMPLETE")
    print("======================================")
    print(
        f"New frame range: "
        f"{START_FRAME}–{frame_index - 1}"
    )
    print(
        f"Manifest: "
        f"{MANIFEST_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()