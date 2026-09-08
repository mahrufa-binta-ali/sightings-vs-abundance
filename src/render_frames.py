from pathlib import Path
from urllib.parse import urlencode
import shutil

from playwright.sync_api import sync_playwright


BASE_URL = "http://localhost:8501/"

OUT_DIR = Path("frames")
OUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH = 1600
HEIGHT = 1000

# Crop off the lower Streamlit explanatory sections.
SHOT_HEIGHT = 900


# =========================================================
# Helpers
# =========================================================

def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    """
    Smooth camera acceleration / deceleration.
    """
    return t * t * (3 - 2 * t)


def build_url(
    mode,
    lat,
    lon,
    zoom,
    pitch,
    bearing,
    abundance_threshold=0.10,
    divergence_threshold=0.60,
):
    params = {
        "capture": 1,
        "mode": mode,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "zoom": round(zoom, 3),
        "pitch": round(pitch, 2),
        "bearing": round(bearing, 2),
        "abundance_threshold": abundance_threshold,
        "divergence_threshold": divergence_threshold,
    }

    return BASE_URL + "?" + urlencode(params)


def wait_for_app(page, first_frame=False):

    page.wait_for_selector(
        '[data-testid="stAppViewContainer"]',
        state="visible",
        timeout=30000
    )

    page.get_by_text(
        "Sightings ≠ Abundance",
        exact=True
    ).wait_for(
        state="visible",
        timeout=30000
    )

    # Streamlit promo popup
    try:
        page.get_by_text(
            "Don't show again",
            exact=True
        ).click(timeout=1000)
    except Exception:
        pass

    # First frame of a scene gets longer because
    # map tiles / WebGL need to settle.
    if first_frame:
        page.wait_for_timeout(3500)
    else:
        page.wait_for_timeout(1600)


def screenshot(page, path):

    page.screenshot(
        path=str(path),
        clip={
            "x": 0,
            "y": 0,
            "width": WIDTH,
            "height": SHOT_HEIGHT,
        }
    )


# =========================================================
# Find DeckGL canvas
# =========================================================

def find_map_box(page):

    canvases = page.locator("canvas")

    best_box = None
    best_area = 0

    for i in range(canvases.count()):

        try:
            box = canvases.nth(i).bounding_box()
        except Exception:
            box = None

        if not box:
            continue

        area = box["width"] * box["height"]

        # Ignore tiny unrelated canvases
        if (
            box["width"] > 500
            and box["height"] > 300
            and area > best_area
        ):
            best_area = area
            best_box = box

    # Fallback based on our fixed animation layout
    if best_box is None:

        print("    Could not detect map canvas; using fallback area.")

        best_box = {
            "x": 100,
            "y": 165,
            "width": 1330,
            "height": 735,
        }

    return best_box


# =========================================================
# Tooltip detection
# =========================================================

def tooltip_is_visible(page):

    tooltips = page.locator(".deck-tooltip")

    for i in range(tooltips.count()):

        try:

            tooltip = tooltips.nth(i)

            if tooltip.is_visible():

                text = tooltip.inner_text().strip()

                if text:
                    return True

        except Exception:
            pass

    return False


def find_hover_target(page):

    box = find_map_box(page)

    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2

    # Search around center.
    # Camera is deliberately centered on our target geographic cell.
    offsets = []

    for dy in range(-160, 101, 20):
        for dx in range(-120, 121, 20):

            offsets.append(
                (
                    abs(dx) + abs(dy),
                    dx,
                    dy
                )
            )

    # Start close to center
    offsets.sort()

    for _, dx, dy in offsets:

        page.mouse.move(
            cx + dx,
            cy + dy
        )

        page.wait_for_timeout(45)

        if tooltip_is_visible(page):

            print(
                f"    Tooltip found at offset "
                f"({dx}, {dy})"
            )

            return True

    print("    Tooltip NOT found automatically.")

    return False


# =========================================================
# Camera motion scene
# =========================================================

def render_motion(
    page,
    frame_index,
    name,
    mode,
    start,
    end,
    frames,
    abundance_threshold=0.08,
    divergence_threshold=0.60,
):

    print(f"\n🎬 Scene: {name}")

    last_url = None

    for i in range(frames):

        t = i / max(frames - 1, 1)

        t = smoothstep(t)

        lat = lerp(
            start["lat"],
            end["lat"],
            t
        )

        lon = lerp(
            start["lon"],
            end["lon"],
            t
        )

        zoom = lerp(
            start["zoom"],
            end["zoom"],
            t
        )

        pitch = lerp(
            start["pitch"],
            end["pitch"],
            t
        )

        bearing = lerp(
            start["bearing"],
            end["bearing"],
            t
        )

        url = build_url(
            mode=mode,
            lat=lat,
            lon=lon,
            zoom=zoom,
            pitch=pitch,
            bearing=bearing,
            abundance_threshold=abundance_threshold,
            divergence_threshold=divergence_threshold,
        )

        print(
            f"  frame {i + 1:03d}/{frames} | "
            f"zoom={zoom:.2f} | "
            f"bearing={bearing:.2f}"
        )

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        wait_for_app(
            page,
            first_frame=(i == 0)
        )

        path = (
            OUT_DIR
            / f"frame_{frame_index:04d}.png"
        )

        screenshot(
            page,
            path
        )

        frame_index += 1

        last_url = url

    return frame_index, last_url


# =========================================================
# Hover + hold
# =========================================================

def render_hover_hold(
    page,
    frame_index,
    url,
    hold_frames=12
):

    print("\n    🔍 Searching for tooltip...")

    # We are already on the final camera position,
    # but reload once cleanly.
    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    wait_for_app(
        page,
        first_frame=True
    )

    found = find_hover_target(page)

    if found:
        page.wait_for_timeout(800)

    first_path = (
        OUT_DIR
        / f"frame_{frame_index:04d}.png"
    )

    screenshot(
        page,
        first_path
    )

    frame_index += 1

    # Duplicate same hover frame.
    # No need to reload Streamlit 12 times.
    for _ in range(hold_frames - 1):

        next_path = (
            OUT_DIR
            / f"frame_{frame_index:04d}.png"
        )

        shutil.copy(
            first_path,
            next_path
        )

        frame_index += 1

    return frame_index


# =========================================================
# CAMERA TARGETS FOR FINAL VIDEO
# =========================================================

# Rich modeled abundance + decent reporting
MODEL_SHOWCASE_TARGET = {
    "lat": 42.336250,
    "lon": -76.351542,
    "zoom": 9.15,
    "pitch": 60,
    "bearing": 11,
}

# Strong raw-reporting hotspot + nonzero modeled abundance
RAW_TARGET = {
    "lat": 42.479522,
    "lon": -76.462152,
    "zoom": 9.25,
    "pitch": 60,
    "bearing": 12,
}

# Strong positive divergence, but abundance is NOT zero
RED_TARGET = {
    "lat": 40.671872,
    "lon": -73.971963,
    "zoom": 9.35,
    "pitch": 60,
    "bearing": 14,
}

# Strong model-heavy divergence with one actual report
BLUE_TARGET = {
    "lat": 42.346549,
    "lon": -76.426408,
    "zoom": 9.20,
    "pitch": 60,
    "bearing": 11,
}


# Medium regional cameras
MID_CENTRAL = {
    "lat": 42.55,
    "lon": -76.20,
    "zoom": 7.55,
    "pitch": 56,
    "bearing": 12,
}

MID_DOWNSTATE = {
    "lat": 41.15,
    "lon": -73.85,
    "zoom": 7.65,
    "pitch": 56,
    "bearing": 14,
}


# =========================================================
# MAIN — FINAL CINEMATIC RENDER
# =========================================================

def main():

    frame_index = 0

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

        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)


        # =================================================
        # 1 — MODELED ABUNDANCE
        # Wide -> medium -> showcase cell -> hover
        # =================================================

        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Modeled abundance — wide landscape",
            mode="Modeled abundance",
            start={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.05,
                "pitch": 50,
                "bearing": 3,
            },
            end={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.45,
                "pitch": 57,
                "bearing": 20,
            },
            frames=48,
            abundance_threshold=0.08,
        )


        # Move into Finger Lakes / Central NY
        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Modeled abundance — regional detail",
            mode="Modeled abundance",
            start={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.45,
                "pitch": 57,
                "bearing": 20,
            },
            end=MID_CENTRAL,
            frames=30,
            abundance_threshold=0.08,
        )


        # Zoom into a useful nonzero example
        frame_index, final_url = render_motion(
            page,
            frame_index,
            name="Modeled abundance — cell focus",
            mode="Modeled abundance",
            start=MID_CENTRAL,
            end=MODEL_SHOWCASE_TARGET,
            frames=26,
            abundance_threshold=0.08,
        )


        frame_index = render_hover_hold(
            page,
            frame_index,
            final_url,
            hold_frames=22
        )


        # =================================================
        # 2 — RAW REPORTING
        # Wide -> medium -> strong hotspot -> hover
        # =================================================

        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Raw reporting — wide landscape",
            mode="Raw reporting",
            start={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.05,
                "pitch": 50,
                "bearing": 4,
            },
            end={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.45,
                "pitch": 57,
                "bearing": 20,
            },
            frames=48,
        )


        # Show regional reporting structure clearly
        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Raw reporting — regional detail",
            mode="Raw reporting",
            start={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.45,
                "pitch": 57,
                "bearing": 20,
            },
            end=MID_CENTRAL,
            frames=30,
        )


        # High-report cell with nonzero modeled abundance
        frame_index, final_url = render_motion(
            page,
            frame_index,
            name="Raw reporting — hotspot focus",
            mode="Raw reporting",
            start=MID_CENTRAL,
            end=RAW_TARGET,
            frames=26,
        )


        frame_index = render_hover_hold(
            page,
            frame_index,
            final_url,
            hold_frames=24
        )


        # =================================================
        # 3 — DIVERGENCE
        #
        # First show MORE cells using |D| >= 0.45.
        # Then switch to stronger |D| >= 0.60 examples.
        # =================================================

        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Divergence — broad spatial overview",
            mode="Reporting–abundance divergence",
            start={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.05,
                "pitch": 50,
                "bearing": 4,
            },
            end={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.45,
                "pitch": 57,
                "bearing": 21,
            },
            frames=52,
            divergence_threshold=0.45,
        )


        # Medium overview before individual examples
        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Divergence — central New York detail",
            mode="Reporting–abundance divergence",
            start={
                "lat": 42.85,
                "lon": -75.15,
                "zoom": 6.45,
                "pitch": 57,
                "bearing": 21,
            },
            end=MID_CENTRAL,
            frames=30,
            divergence_threshold=0.45,
        )


        # =================================================
        # 3A — REPORT-HEAVY / RED EXAMPLE
        # =================================================

        # Move back slightly before travelling downstate
        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Divergence — moving toward report-heavy region",
            mode="Reporting–abundance divergence",
            start=MID_CENTRAL,
            end=MID_DOWNSTATE,
            frames=28,
            divergence_threshold=0.50,
        )


        frame_index, final_url = render_motion(
            page,
            frame_index,
            name="Divergence — report-heavy focus",
            mode="Reporting–abundance divergence",
            start=MID_DOWNSTATE,
            end=RED_TARGET,
            frames=24,
            divergence_threshold=0.60,
        )


        frame_index = render_hover_hold(
            page,
            frame_index,
            final_url,
            hold_frames=24
        )


        # =================================================
        # 3B — MODEL-HIGH / BLUE EXAMPLE
        # =================================================

        # Pull out before crossing the state.
        # This is much nicer than flying directly from NYC to Ithaca.
        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Divergence — pull back",
            mode="Reporting–abundance divergence",
            start=RED_TARGET,
            end={
                "lat": 41.75,
                "lon": -75.10,
                "zoom": 7.15,
                "pitch": 56,
                "bearing": 12,
            },
            frames=24,
            divergence_threshold=0.60,
        )


        frame_index, _ = render_motion(
            page,
            frame_index,
            name="Divergence — moving toward model-heavy region",
            mode="Reporting–abundance divergence",
            start={
                "lat": 41.75,
                "lon": -75.10,
                "zoom": 7.15,
                "pitch": 56,
                "bearing": 12,
            },
            end=MID_CENTRAL,
            frames=26,
            divergence_threshold=0.60,
        )


        frame_index, final_url = render_motion(
            page,
            frame_index,
            name="Divergence — model-heavy focus",
            mode="Reporting–abundance divergence",
            start=MID_CENTRAL,
            end=BLUE_TARGET,
            frames=24,
            divergence_threshold=0.60,
        )


        frame_index = render_hover_hold(
            page,
            frame_index,
            final_url,
            hold_frames=24
        )


        browser.close()


    print()
    print("======================================")
    print("🎉 FINAL CINEMATIC FRAME RENDER COMPLETE")
    print("======================================")
    print(f"Total frames: {frame_index}")
    print(f"Saved in: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()