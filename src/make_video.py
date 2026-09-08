from pathlib import Path
import json
import textwrap

import imageio.v2 as imageio
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# =========================================================
# SETTINGS
# =========================================================

DATA_CSV = Path("data/processed/wood_thrush_grid_divergence_2023.csv")
FRAMES_DIR = Path("frames")
SHOWCASE_MANIFEST = FRAMES_DIR / "showcase_manifest.json"

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_VIDEO = OUTPUT_DIR / "sightings_vs_abundance_final.mp4"

FPS = 40
WIDTH = 1600
HEIGHT = 900


# =========================================================
# FONTS
# =========================================================

def load_font(preferred_paths, size):
    for p in preferred_paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


# Prefer more modern Windows fonts first; Arial is only fallback.
FONT_BOLD_PATHS = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\bahnschrift.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]

FONT_REGULAR_PATHS = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\bahnschrift.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]

APP_HEADER_FONT = load_font(FONT_BOLD_PATHS, 42)
HERO_FONT = load_font(FONT_BOLD_PATHS, 64)
TITLE_FONT = load_font(FONT_BOLD_PATHS, 52)
LABEL_FONT = load_font(FONT_BOLD_PATHS, 31)
SUBTITLE_FONT = load_font(FONT_REGULAR_PATHS, 24)
SMALL_FONT = load_font(FONT_REGULAR_PATHS, 18)
STAT_FONT = load_font(FONT_BOLD_PATHS, 36)
BIG_STAT_FONT = load_font(FONT_BOLD_PATHS, 42)
TITLE_FONT_MED = load_font(FONT_BOLD_PATHS, 44)
TITLE_FONT_SMALL = load_font(FONT_BOLD_PATHS, 38)


# =========================================================
# COLOR SYSTEM
# =========================================================

ACCENT_STYLES = {
    "modeled": {
        "bar": (34, 176, 116),
        "glow": (92, 244, 181),
        "title": (18, 39, 52),
        "subtitle": (52, 71, 84),
    },
    "raw": {
        "bar": (45, 133, 255),
        "glow": (95, 190, 255),
        "title": (18, 39, 52),
        "subtitle": (52, 71, 84),
    },
    "divergence": {
        "bar": (255, 176, 54),
        "glow": (255, 221, 125),
        "title": (18, 39, 52),
        "subtitle": (52, 71, 84),
    },
    "report-heavy": {
        "bar": (255, 82, 67),
        "glow": (255, 148, 131),
        "title": (18, 39, 52),
        "subtitle": (52, 71, 84),
    },
    "model-high": {
        "bar": (126, 88, 255),
        "glow": (185, 159, 255),
        "title": (18, 39, 52),
        "subtitle": (52, 71, 84),
    },
    "scatter": {
        "bar": (163, 94, 230),
        "glow": (218, 174, 255),
        "title": (18, 39, 52),
        "subtitle": (52, 71, 84),
    },
    "default": {
        "bar": (255, 143, 70),
        "glow": (255, 204, 135),
        "title": (18, 39, 52),
        "subtitle": (52, 71, 84),
    },
}


def get_label_style(title):
    t = title.lower()
    if "model-high" in t:
        return ACCENT_STYLES["model-high"]
    if "report-heavy" in t:
        return ACCENT_STYLES["report-heavy"]
    if "raw reporting" in t:
        return ACCENT_STYLES["raw"]
    if "modeled abundance" in t:
        return ACCENT_STYLES["modeled"]
    if "weak overall" in t or "association" in t:
        return ACCENT_STYLES["scatter"]
    if "divergence" in t:
        return ACCENT_STYLES["divergence"]
    return ACCENT_STYLES["default"]


# =========================================================
# BASIC IMAGE HELPERS
# =========================================================

def load_frame(index):
    path = FRAMES_DIR / f"frame_{index:04d}.png"
    return Image.open(path).convert("RGB")


def resize_to_fill(img, target_w, target_h):
    scale = max(target_w / img.width, target_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def resize_to_fit(img, max_w, max_h):
    scale = min(max_w / img.width, max_h / img.height)
    size = (int(img.width * scale), int(img.height * scale))
    return img.resize(size, Image.LANCZOS)


def choose_font_to_fit(text, fonts, max_width):
    probe = Image.new("RGB", (10, 10), "white")
    draw = ImageDraw.Draw(probe)
    for font in fonts:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return fonts[-1]


def draw_glow_text(base, xy, text, font, fill_rgb, glow_rgb, blur_radius=10, glow_alpha=120):
    """Crisp text plus a restrained, luminous halo."""
    if base.mode != "RGBA":
        base = base.convert("RGBA")

    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text(xy, text, font=font, fill=glow_rgb + (glow_alpha,))
    glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
    base.alpha_composite(glow)

    draw = ImageDraw.Draw(base)
    # very subtle light ridge; avoids a flat solid-black look
    draw.text((xy[0], xy[1] + 1), text, font=font, fill=(255, 255, 255, 35))
    draw.text(xy, text, font=font, fill=fill_rgb + (255,))
    return base


def draw_wrapped_text(draw, x, y, text, font, fill, max_width_px, line_gap=6):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = word if not current else current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width_px:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    yy = y
    for line in lines:
        # tiny pale edge for legibility over map tiles, no box
        draw.text((x + 1, yy + 1), line, font=font, fill=(255, 255, 255, 105))
        draw.text((x, yy), line, font=font, fill=fill)
        bbox = draw.textbbox((x, yy), line, font=font)
        yy += (bbox[3] - bbox[1]) + line_gap

    return yy


def add_radiant_header(frame):
    """
    Clean branded header.

    Covers the original Streamlit title/subtitle completely so
    none of the old captured text leaks through.
    """

    base = frame.convert("RGBA")
    draw = ImageDraw.Draw(base)

    # IMPORTANT:
    # Increased from ~126 px to 142 px.
    # This hides the original Streamlit subtitle completely.
    draw.rectangle(
        (0, 0, WIDTH, 142),
        fill=(250, 251, 253, 255)
    )

    # Main project title
    draw_glow_text(
        base,
        (58, 18),
        "Sightings ≠ Abundance",
        APP_HEADER_FONT,
        fill_rgb=(18, 35, 56),
        glow_rgb=(117, 177, 255),
        blur_radius=5,
        glow_alpha=45,
    )

    draw = ImageDraw.Draw(base)

    # Only OUR clean subtitle remains
    draw.text(
        (58, 72),
        "Exploring raw eBird reporting and modeled Wood Thrush abundance in New York",
        font=SMALL_FONT,
        fill=(104, 114, 128, 255),
    )

    return base


# =========================================================
# MAP / SCENE LABEL — NO WHITE CARD
# =========================================================

def add_label(
    frame,
    title,
    subtitle=None,
    accent=None,
    position="top_left"
):
    """
    Scene heading area:
    - no white card
    - no border
    - no blurred decorative lines
    - title/subtitle sit in a soft transition area above the map
    """

    base = add_radiant_header(frame)
    style = get_label_style(title)

    if accent is not None:
        accent_rgb = tuple(accent[:3])

        style = dict(style)
        style["bar"] = accent_rgb
        style["glow"] = accent_rgb


    # =====================================================
    # SOFT LABEL ZONE
    # =====================================================
    #
    # This is NOT a white box.
    # It creates a subtle fade between the header and map
    # so the text does not sit directly on map graphics.
    #

    label_zone = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    zone_draw = ImageDraw.Draw(label_zone)

    zone_top = 136
    zone_bottom = 260

    # Gradually fade from almost-white to transparent
    for y in range(zone_top, zone_bottom):

        t = (
            (y - zone_top)
            / max(zone_bottom - zone_top - 1, 1)
        )

        alpha = int(
            245 * (1 - t)
            + 90 * t
        )

        zone_draw.line(
            (0, y, WIDTH, y),
            fill=(250, 251, 253, alpha)
        )

    base = Image.alpha_composite(
        base,
        label_zone
    )


    # =====================================================
    # LABEL POSITION
    # =====================================================

    x0 = 72

    # Previously ~145.
    # Moving upward slightly keeps the words away
    # from the actual map content.
    y0 = 145


    # =====================================================
    # COLORED ACCENT PILL
    # =====================================================

    draw = ImageDraw.Draw(base)

    pill = (
        x0 - 22,
        y0 + 4,
        x0 - 10,
        y0 + 68
    )

    draw.rounded_rectangle(
        pill,
        radius=7,
        fill=style["bar"] + (255,)
    )


    # =====================================================
    # TITLE
    # =====================================================

    title_font = choose_font_to_fit(
        title,
        [
            LABEL_FONT,
            TITLE_FONT_SMALL,
            TITLE_FONT_MED
        ],
        WIDTH - x0 - 80
    )

    draw_glow_text(
        base,
        (x0, y0),
        title,
        title_font,
        fill_rgb=style["title"],
        glow_rgb=style["glow"],

        # restrained glow
        blur_radius=4,
        glow_alpha=38,
    )


    # =====================================================
    # SUBTITLE
    # =====================================================

    if subtitle:

        draw = ImageDraw.Draw(base)

        draw_wrapped_text(
            draw,
            x0,
            y0 + 54,
            subtitle,
            SUBTITLE_FONT,

            fill=style["subtitle"] + (255,),

            max_width_px=WIDTH - x0 - 85,

            line_gap=4,
        )


    return base.convert("RGB")

# =========================================================
# OPENING CARD
# =========================================================

def opening_card():
    bg = load_frame(20)
    bg = resize_to_fill(bg, WIDTH, HEIGHT).convert("RGBA")

    # Dark gradient: strongest on left, lighter over the 3D map to the right.
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(WIDTH):
        t = x / max(WIDTH - 1, 1)
        alpha = int(205 * (1 - t) + 70 * t)
        od.line((x, 0, x, HEIGHT), fill=(6, 16, 27, alpha))
    bg = Image.alpha_composite(bg, overlay)

    # Three luminous rods representing the three visual layers.
    rods = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rods)
    rod_specs = [
        (120, ACCENT_STYLES["modeled"]),
        (150, ACCENT_STYLES["raw"]),
        (180, ACCENT_STYLES["report-heavy"]),
    ]
    for x, style in rod_specs:
        rd.rounded_rectangle((x, 182, x + 16, 472), radius=8, fill=style["glow"] + (115,))
    rods = rods.filter(ImageFilter.GaussianBlur(7))
    bg.alpha_composite(rods)

    draw = ImageDraw.Draw(bg)
    for x, style in rod_specs:
        draw.rounded_rectangle((x, 182, x + 16, 472), radius=8, fill=style["bar"] + (255,))

    draw_glow_text(
        bg,
        (235, 195),
        "Sightings ≠ Abundance",
        HERO_FONT,
        fill_rgb=(255, 255, 255),
        glow_rgb=(108, 176, 255),
        blur_radius=15,
        glow_alpha=145,
    )

    draw = ImageDraw.Draw(bg)
    draw.text(
        (240, 325),
        "Wood Thrush  •  New York  •  2023 breeding season",
        font=SUBTITLE_FONT,
        fill=(237, 243, 248, 255),
    )
    draw.text(
        (240, 390),
        "Raw eBird reporting vs. modeled relative abundance",
        font=SUBTITLE_FONT,
        fill=(237, 243, 248, 255),
    )
    draw.text(
        (240, 455),
        "An interactive 3D spatial comparison",
        font=SUBTITLE_FONT,
        fill=(213, 227, 238, 255),
    )

    return bg.convert("RGB")


# =========================================================
# SCATTER / ASSOCIATION CARD — NO OVERLAP
# =========================================================

def scatter_card():
    df = pd.read_csv(DATA_CSV)
    observed = df[df["report_count"] > 0].copy()

    # Render only the plot first.
    fig, ax = plt.subplots(figsize=(10.6, 7.0), dpi=140)
    ax.scatter(
        observed["abundance_score"],
        observed["report_score"],
        alpha=0.22,
        s=18,
    )
    ax.set_xlabel("Modeled abundance percentile", fontsize=15)
    ax.set_ylabel("Reporting percentile", fontsize=15)
    ax.set_title("Reporting vs. modeled abundance rank", fontsize=22, pad=14)
    ax.tick_params(labelsize=11)
    fig.tight_layout()

    temp_path = OUTPUT_DIR / "scatter_plot_temp.png"
    fig.savefig(temp_path, facecolor="white")
    plt.close(fig)

    plot = Image.open(temp_path).convert("RGB")
    plot = resize_to_fit(plot, 1080, 760)

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (247, 249, 252, 255))
    draw = ImageDraw.Draw(canvas)

    # Left information panel, visually separate from the plot.
    style = ACCENT_STYLES["scatter"]
    scatter_title_font = choose_font_to_fit(
        "Weak overall rank association",
        [TITLE_FONT, TITLE_FONT_MED, TITLE_FONT_SMALL, LABEL_FONT],
        390,
    )
    draw_glow_text(
        canvas,
        (78, 85),
        "Weak overall rank association",
        scatter_title_font,
        fill_rgb=(22, 32, 50),
        glow_rgb=style["glow"],
        blur_radius=7,
        glow_alpha=60,
    )

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((78, 170, 90, 255), radius=7, fill=style["bar"] + (255,))
    draw.text((116, 170), "Spearman ρ", font=SUBTITLE_FONT, fill=(94, 100, 114, 255))
    draw.text((116, 205), "0.119", font=BIG_STAT_FONT, fill=(25, 35, 53, 255))

    draw.text((116, 282), "Observed grid cells", font=SUBTITLE_FONT, fill=(94, 100, 114, 255))
    draw.text((116, 317), "2,590", font=STAT_FONT, fill=(25, 35, 53, 255))

    draw.text((78, 405), "Interpretation", font=LABEL_FONT, fill=(25, 35, 53, 255))
    draw_wrapped_text(
        draw,
        78,
        452,
        "Raw reporting concentration only weakly tracks modeled relative abundance across observed cells.",
        SUBTITLE_FONT,
        fill=(64, 72, 88, 255),
        max_width_px=410,
        line_gap=8,
    )

    draw_wrapped_text(
        draw,
        78,
        610,
        "The very small p-value reflects statistical detectability, not a strong relationship.",
        SMALL_FONT,
        fill=(106, 112, 124, 255),
        max_width_px=410,
        line_gap=6,
    )

    # Plot on the right, safely away from the text.
    plot_x = 500
    plot_y = (HEIGHT - plot.height) // 2
    canvas.paste(plot, (plot_x, plot_y))

    return canvas.convert("RGB")

# =========================================================
# QUANTITATIVE DIAGNOSTICS
# =========================================================

def compute_diagnostics():

    df = pd.read_csv(DATA_CSV)

    obs = df[
        (df["report_count"] > 0)
        & df["divergence"].notna()
    ].copy()

    D = obs["divergence"].to_numpy(dtype=float)

    N = len(D)

    mean_d = np.mean(D)
    std_d = np.std(D, ddof=1)

    mae_d = np.mean(
        np.abs(D)
    )

    rmse_d = np.sqrt(
        np.mean(D ** 2)
    )

    peak_d = np.max(
        np.abs(D)
    )

    q90_d = np.quantile(
        np.abs(D),
        0.90
    )

    exceed_060 = np.mean(
        np.abs(D) >= 0.60
    )

    positive_share = np.mean(
        D > 0
    )

    negative_share = np.mean(
        D < 0
    )

    # Top-decile spatial overlap
    top_report = (
        obs["report_score"] >= 0.90
    )

    top_abundance = (
        obs["abundance_score"] >= 0.90
    )

    intersection = (
        top_report
        & top_abundance
    ).sum()

    union = (
        top_report
        | top_abundance
    ).sum()

    jaccard_top10 = (
        intersection / union
        if union > 0
        else 0
    )

    # Reporting concentration
    reports_mean = (
        obs["report_count"].mean()
    )

    reports_std = (
        obs["report_count"].std()
    )

    report_cv = (
        reports_std / reports_mean
        if reports_mean > 0
        else 0
    )

    # Spearman from the rank scores themselves
    rho = obs[
        [
            "report_score",
            "abundance_score"
        ]
    ].corr(
        method="spearman"
    ).iloc[0, 1]

    return {
        "N": N,
        "rho": rho,

        # Already established from your analysis
        "p": 1.091073490549408e-09,

        "mean_d": mean_d,
        "std_d": std_d,
        "mae_d": mae_d,
        "rmse_d": rmse_d,
        "peak_d": peak_d,
        "q90_d": q90_d,

        "exceed_060": exceed_060,
        "positive_share": positive_share,
        "negative_share": negative_share,

        "jaccard_top10": jaccard_top10,

        "reports_mean": reports_mean,
        "reports_std": reports_std,
        "report_cv": report_cv,
    }


# =========================================================
# VISUAL RECAP CARD
# =========================================================

def insight_card():
    img = Image.new("RGBA", (WIDTH, HEIGHT), (247, 249, 252, 255))
    draw_glow_text(
        img,
        (78, 60),
        "Three views of the same system",
        TITLE_FONT,
        fill_rgb=(22, 32, 50),
        glow_rgb=(118, 177, 255),
        blur_radius=11,
        glow_alpha=90,
    )
    draw = ImageDraw.Draw(img)
    draw.text(
        (80, 126),
        "Each layer reveals a different part of the Wood Thrush spatial story in New York.",
        font=SUBTITLE_FONT,
        fill=(82, 91, 106, 255),
    )

    cards = [
        ("Modeled abundance", "Continuous modeled spatial surface", 125, ACCENT_STYLES["modeled"]),
        ("Raw reporting", "Wood Thrush-positive reporting cells", 253, ACCENT_STYLES["raw"]),
        ("Divergence", "Where the two spatial rankings disagree", 411, ACCENT_STYLES["report-heavy"]),
    ]

    x_positions = [80, 555, 1030]
    y_top = 205
    thumb_w = 400
    thumb_h = 255

    for (title, subtitle, frame_idx, style), x in zip(cards, x_positions):
        # Card shadow
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((x + 6, y_top + 8, x + thumb_w + 6, y_top + thumb_h + 108), radius=22, fill=(0, 0, 0, 28))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        img.alpha_composite(shadow)

        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            (x, y_top, x + thumb_w, y_top + thumb_h + 100),
            radius=22,
            fill=(255, 255, 255, 255),
            outline=style["glow"] + (120,),
            width=2,
        )

        frame = resize_to_fill(load_frame(frame_idx), thumb_w - 20, thumb_h - 20)
        img.paste(frame, (x + 10, y_top + 10))

        # colored pill + label
        draw.rounded_rectangle((x + 18, y_top + thumb_h + 24, x + 30, y_top + thumb_h + 76), radius=6, fill=style["bar"] + (255,))
        draw.text((x + 48, y_top + thumb_h + 18), title, font=LABEL_FONT, fill=(22, 32, 50, 255))
        draw.text((x + 48, y_top + thumb_h + 58), subtitle, font=SMALL_FONT, fill=(91, 98, 112, 255))

    # =====================================================
    # QUANTITATIVE FORMULATION
    # =====================================================

    stats = compute_diagnostics()

    box = (
        80,
        640,
        1520,
        835
    )

    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        box,
        radius=24,
        fill=(255, 255, 255, 245),
        outline=(216, 223, 234, 255),
        width=2,
    )

    draw.text(
        (110, 665),
        "Rank-space formulation",
        font=LABEL_FONT,
        fill=(22, 32, 50, 255),
    )

    # -----------------------------------------------------
    # Formula 1
    # -----------------------------------------------------

    draw.text(
        (120, 720),
        "Dᵢ = Rᵢ − Aᵢ",
        font=STAT_FONT,
        fill=ACCENT_STYLES["report-heavy"]["bar"] + (255,),
    )

    draw.text(
        (120, 765),
        "cell-wise reporting–abundance rank residual",
        font=SMALL_FONT,
        fill=(95, 102, 116, 255),
    )


    # -----------------------------------------------------
    # Formula 2
    # -----------------------------------------------------

    draw.text(
        (525, 720),
        "MAE_D = (1/N) Σ |Dᵢ|",
        font=STAT_FONT,
        fill=ACCENT_STYLES["raw"]["bar"] + (255,),
    )

    draw.text(
        (525, 765),
        f"observed MAE = {stats['mae_d']:.3f}",
        font=SMALL_FONT,
        fill=(95, 102, 116, 255),
    )


    # -----------------------------------------------------
    # Formula 3
    # -----------------------------------------------------

    draw.text(
        (980, 720),
        "RMS_D = √[(1/N) Σ Dᵢ²]",
        font=STAT_FONT,
        fill=ACCENT_STYLES["model-high"]["bar"] + (255,),
    )

    draw.text(
        (980, 765),
        f"observed RMS = {stats['rmse_d']:.3f}",
        font=SMALL_FONT,
        fill=(95, 102, 116, 255),
    )
    return img.convert("RGB")

# =========================================================
# FINAL RESULT CARD
# =========================================================

def final_card():

    stats = compute_diagnostics()

    img = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (246, 248, 252, 255)
    )

    # =====================================================
    # TITLE
    # =====================================================

    draw_glow_text(
        img,
        (70, 40),
        "Quantitative divergence diagnostics",
        TITLE_FONT,
        fill_rgb=(21, 31, 49),
        glow_rgb=(128, 171, 255),
        blur_radius=7,
        glow_alpha=55,
    )

    draw = ImageDraw.Draw(img)

    draw.text(
        (72, 105),
        "Wood Thrush • observed-cell rank-space comparison",
        font=SUBTITLE_FONT,
        fill=(92, 100, 114, 255),
    )


    # =====================================================
    # TOP METRIC CARDS
    # =====================================================

    top_metrics = [

        (
            70, 160, 345, 285,
            "N",
            f"{stats['N']:,}",
            ACCENT_STYLES["raw"]
        ),

        (
            370, 160, 645, 285,
            "Spearman ρ",
            f"{stats['rho']:.3f}",
            ACCENT_STYLES["scatter"]
        ),

        (
            670, 160, 945, 285,
            "MAE_D",
            f"{stats['mae_d']:.3f}",
            ACCENT_STYLES["modeled"]
        ),

        (
            970, 160, 1245, 285,
            "RMS_D",
            f"{stats['rmse_d']:.3f}",
            ACCENT_STYLES["model-high"]
        ),

        (
            1270, 160, 1530, 285,
            "max |D|",
            f"{stats['peak_d']:.3f}",
            ACCENT_STYLES["report-heavy"]
        ),
    ]


    for (
        x1, y1, x2, y2,
        label,
        value,
        style
    ) in top_metrics:

        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=22,
            fill=(255, 255, 255, 255),
            outline=style["glow"] + (110,),
            width=2,
        )

        draw.rounded_rectangle(
            (
                x1 + 16,
                y1 + 18,
                x1 + 27,
                y1 + 70
            ),
            radius=6,
            fill=style["bar"] + (255,),
        )

        draw.text(
            (
                x1 + 43,
                y1 + 18
            ),
            label,
            font=SMALL_FONT,
            fill=(95, 103, 117, 255),
        )

        draw.text(
            (
                x1 + 43,
                y1 + 57
            ),
            value,
            font=STAT_FONT,
            fill=style["bar"] + (255,),
        )


    # =====================================================
    # FORMULA PANEL
    # =====================================================

    draw.rounded_rectangle(
        (
            70,
            325,
            825,
            655
        ),
        radius=24,
        fill=(255, 255, 255, 250),
        outline=(220, 225, 235, 255),
        width=2,
    )

    draw.text(
        (100, 350),
        "Residual formulation",
        font=LABEL_FONT,
        fill=(22, 32, 50, 255),
    )


    draw.text(
        (110, 410),
        "Dᵢ = Rᵢ − Aᵢ",
        font=STAT_FONT,
        fill=ACCENT_STYLES["report-heavy"]["bar"] + (255,),
    )

    draw.text(
        (390, 410),
        f"μᴅ = {stats['mean_d']:+.3f}",
        font=STAT_FONT,
        fill=ACCENT_STYLES["divergence"]["bar"] + (255,),
    )


    sigma_formula = "σᴅ = √[(1/(N−1)) Σ(Dᵢ−μᴅ)²]"

    draw.text(
        (110, 475),
        sigma_formula,
        font=SUBTITLE_FONT,
        fill=(42, 51, 68, 255),
    )

    # Automatically place the result just after the formula
    sigma_bbox = draw.textbbox(
        (110, 475),
        sigma_formula,
        font=SUBTITLE_FONT
    )

    sigma_value_x = sigma_bbox[2] + 18

    draw.text(
        (sigma_value_x, 471),
        f"= {stats['std_d']:.3f}",
        font=STAT_FONT,
        fill=ACCENT_STYLES["model-high"]["bar"] + (255,),
    )


    draw.text(
        (110, 535),
        "Eᴅ = (1/N) ΣDᵢ²",
        font=SUBTITLE_FONT,
        fill=(42, 51, 68, 255),
    )

    draw.text(
        (390, 535),
        f"= {stats['rmse_d'] ** 2:.3f}",
        font=STAT_FONT,
        fill=ACCENT_STYLES["raw"]["bar"] + (255,),
    )

    draw.text(
        (110, 580),
        "RMSᴅ = √Eᴅ",
        font=SUBTITLE_FONT,
        fill=(42, 51, 68, 255),
    )

    draw.text(
        (390, 580),
        f"= {stats['rmse_d']:.3f}",
        font=STAT_FONT,
        fill=ACCENT_STYLES["modeled"]["bar"] + (255,),
    )


    # =====================================================
    # SPATIAL / THRESHOLD DIAGNOSTICS
    # =====================================================

    draw.rounded_rectangle(
        (
            855,
            325,
            1530,
            655
        ),
        radius=24,
        fill=(255, 255, 255, 250),
        outline=(220, 225, 235, 255),
        width=2,
    )

    draw.text(
        (885, 350),
        "Spatial mismatch diagnostics",
        font=LABEL_FONT,
        fill=(22, 32, 50, 255),
    )


    diagnostics = [

        (
            "90th percentile |D|",
            f"{stats['q90_d']:.3f}",
            ACCENT_STYLES["model-high"]
        ),

        (
            "P(|D| ≥ 0.60)",
            f"{100 * stats['exceed_060']:.1f}%",
            ACCENT_STYLES["report-heavy"]
        ),

        (
            "Positive-D cells",
            f"{100 * stats['positive_share']:.1f}%",
            ACCENT_STYLES["divergence"]
        ),

        (
            "Negative-D cells",
            f"{100 * stats['negative_share']:.1f}%",
            ACCENT_STYLES["raw"]
        ),

        (
            "Top-decile Jaccard",
            f"{stats['jaccard_top10']:.3f}",
            ACCENT_STYLES["scatter"]
        ),

        (
            "Reporting CV",
            f"{stats['report_cv']:.2f}",
            ACCENT_STYLES["modeled"]
        ),
    ]


    y = 410

    for label, value, style in diagnostics:

        draw.rounded_rectangle(
            (
                892,
                y + 4,
                903,
                y + 38
            ),
            radius=5,
            fill=style["bar"] + (255,),
        )

        draw.text(
            (920, y),
            label,
            font=SMALL_FONT,
            fill=(79, 87, 101, 255),
        )

        draw.text(
            (1340, y - 4),
            value,
            font=SUBTITLE_FONT,
            fill=style["bar"] + (255,),
        )

        y += 39


    # =====================================================
    # BOTTOM ENGINEERING-STYLE DIAGNOSTIC STRIP
    # =====================================================

    draw.rounded_rectangle(
        (
            70,
            680,
            1530,
            850
        ),
        radius=24,
        fill=(255, 255, 255, 245),
        outline=(217, 223, 233, 255),
        width=2,
    )


    draw.text(
        (100, 707),
        "Normalized rank-space comparison",
        font=LABEL_FONT,
        fill=(22, 32, 50, 255),
    )


    # =====================================================
    # TOP-DECILE JACCARD
    # =====================================================

    jaccard_formula = "J₁₀ = |Tᴿ₁₀ ∩ Tᴬ₁₀| / |Tᴿ₁₀ ∪ Tᴬ₁₀|"

    jaccard_x = 100
    jaccard_y = 763

    draw.text(
        (jaccard_x, jaccard_y),
        jaccard_formula,
        font=SUBTITLE_FONT,
        fill=ACCENT_STYLES["scatter"]["bar"] + (255,),
    )

    jaccard_bbox = draw.textbbox(
        (jaccard_x, jaccard_y),
        jaccard_formula,
        font=SUBTITLE_FONT,
    )

    jaccard_value_x = jaccard_bbox[2] + 12

    draw.text(
        (jaccard_value_x, jaccard_y - 5),
        f"= {stats['jaccard_top10']:.3f}",
        font=STAT_FONT,
        fill=ACCENT_STYLES["scatter"]["bar"] + (255,),
    )


    # =====================================================
    # REPORTING COEFFICIENT OF VARIATION
    # =====================================================

    cv_formula = "CVreports = σreports / μreports"

    cv_x = 790
    cv_y = 763

    draw.text(
        (cv_x, cv_y),
        cv_formula,
        font=SUBTITLE_FONT,
        fill=ACCENT_STYLES["raw"]["bar"] + (255,),
    )

    cv_bbox = draw.textbbox(
        (cv_x, cv_y),
        cv_formula,
        font=SUBTITLE_FONT,
    )

    cv_value_x = cv_bbox[2] + 12

    draw.text(
        (cv_value_x, cv_y - 5),
        f"= {stats['report_cv']:.2f}",
        font=STAT_FONT,
        fill=ACCENT_STYLES["raw"]["bar"] + (255,),
    )

    # Tiny restraint footer only
    draw.text(
        (100, 827),
        "Diagnostics computed over observed grid cells; all rank quantities are dimensionless.",
        font=SMALL_FONT,
        fill=(118, 124, 137, 255),
    )


    return img.convert("RGB")


# =========================================================
# OPTIONAL SHOWCASE MANIFEST SUPPORT
# =========================================================

def load_showcase_manifest():
    if not SHOWCASE_MANIFEST.exists():
        return []
    with open(SHOWCASE_MANIFEST, "r", encoding="utf-8") as f:
        return json.load(f)


def format_abundance(value):
    return f"{float(value):.3f}"


def format_divergence(value):
    if value is None:
        return "n/a"
    return f"{float(value):+.3f}"


def showcase_title(entry):
    segment = entry["segment"]
    name = entry["name"]
    if segment == "Modeled abundance":
        return f"Modeled abundance — {name}"
    if segment == "Raw reporting":
        return f"Raw reporting — {name}"
    if float(entry.get("divergence", 0) or 0) >= 0:
        return f"Report-heavy divergence — {name}"
    return f"Model-high divergence — {name}"


def showcase_subtitle(entry):
    segment = entry["segment"]
    reports = int(entry["report_count"])
    abundance = format_abundance(entry["relative_abundance"])

    if segment == "Modeled abundance":
        return f"Modeled abundance {abundance}  •  eBird records {reports}"
    if segment == "Raw reporting":
        return f"{reports} Wood Thrush-positive records  •  modeled abundance {abundance}"

    divergence = format_divergence(entry.get("divergence"))
    return f"D = {divergence}  •  {reports} records  •  modeled abundance {abundance}"


def add_showcase_sequence(writer, entries, previous_image=None):
    last_image = previous_image
    for entry in entries:
        title = showcase_title(entry)
        subtitle = showcase_subtitle(entry)
        first_img = add_label(load_frame(entry["start_frame"]), title, subtitle)

        if last_image is not None:
            for img in crossfade(last_image, first_img, 14):
                append_image(writer, img)

        for i in range(entry["start_frame"], entry["hover_end"] + 1):
            img = add_label(load_frame(i), title, subtitle)
            append_image(writer, img)
            append_image(writer, img)

        last_image = add_label(load_frame(entry["hover_end"]), title, subtitle)
        hold(writer, last_image, 12)

    return last_image


# =========================================================
# VIDEO HELPERS
# =========================================================

def crossfade(image_a, image_b, frames=12):
    result = []
    for i in range(1, frames + 1):
        alpha = i / (frames + 1)
        result.append(Image.blend(image_a.convert("RGB"), image_b.convert("RGB"), alpha))
    return result


def append_image(writer, image):
    writer.append_data(np.asarray(image.convert("RGB")))


def hold(writer, image, frames):
    for _ in range(frames):
        append_image(writer, image)


def append_range(writer, start, end, title, subtitle=None, repeat=1):
    for i in range(start, end + 1):
        img = add_label(load_frame(i), title, subtitle)
        for _ in range(repeat):
            append_image(writer, img)


# =========================================================
# MAIN
# =========================================================

def main():
    print("Building polished Sightings ≠ Abundance animation...")

    showcase = load_showcase_manifest()
    modeled_showcase = [x for x in showcase if x.get("segment") == "Modeled abundance"]
    raw_showcase = [x for x in showcase if x.get("segment") == "Raw reporting"]
    divergence_showcase = [x for x in showcase if x.get("segment") == "Reporting–abundance divergence"]

    with imageio.get_writer(
        OUTPUT_VIDEO,
        fps=FPS,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=2,
    ) as writer:

        # OPENING
        print("Adding cinematic opening...")
        card = opening_card()
        hold(writer, card, 48)

        # 1 — MODELED ABUNDANCE
        print("Adding modeled abundance...")
        append_range(writer, 0, 47, "Modeled abundance", "Cornell eBird Status & Trends modeled relative abundance")
        append_range(writer, 48, 77, "Modeled abundance", "Zooming into regional variation across central New York")
        append_range(writer, 78, 103, "Modeled abundance", "Moving from the state-level surface to an individual ~3 km cell", repeat=2)
        append_range(writer, 104, 125, "Modeled abundance — example cell", "Hover reveals modeled abundance and raw reporting for this location", repeat=2)

        model_hover = add_label(
            load_frame(125),
            "Modeled abundance — example cell",
            "Hover reveals modeled abundance and raw reporting for this location",
        )
        hold(writer, model_hover, 18)

        if modeled_showcase:
            print("Adding modeled-abundance showcase stops...")
            model_last = add_showcase_sequence(writer, modeled_showcase, model_hover)
        else:
            model_last = model_hover

        # TRANSITION → RAW
        raw_first = add_label(load_frame(126), "Raw reporting", "Cells containing Wood Thrush-positive eBird reports")
        for img in crossfade(model_last, raw_first, 16):
            append_image(writer, img)

        # 2 — RAW REPORTING
        print("Adding raw reporting...")
        append_range(writer, 126, 173, "Raw reporting", "Cells containing Wood Thrush-positive eBird reports")
        append_range(writer, 174, 203, "Raw reporting", "Regional reporting intensity reveals a much sparser spatial pattern")
        append_range(writer, 204, 229, "Raw reporting", "Zooming toward a strongly reported cell", repeat=2)
        append_range(writer, 230, 253, "Raw reporting hotspot", "Hover: 117 observation records with nonzero modeled abundance", repeat=2)

        raw_hover = add_label(
            load_frame(253),
            "Raw reporting hotspot",
            "Hover shows observation records and modeled abundance for the same cell",
        )
        hold(writer, raw_hover, 16)

        if raw_showcase:
            print("Adding raw-reporting showcase stops...")
            raw_last = add_showcase_sequence(writer, raw_showcase, raw_hover)
        else:
            raw_last = raw_hover

        # TRANSITION → DIVERGENCE
        divergence_first = add_label(
            load_frame(254),
            "Reporting–abundance divergence",
            "Red: reporting rank higher  •  Blue: modeled abundance rank higher",
        )
        for img in crossfade(raw_last, divergence_first, 16):
            append_image(writer, img)

        # 3 — DIVERGENCE
        print("Adding divergence overview...")
        append_range(writer, 254, 305, "Reporting–abundance divergence", "Broader view shown at |D| ≥ 0.45")
        append_range(writer, 306, 335, "Reporting–abundance divergence", "Where do reporting and modeled abundance ranks disagree most?")
        append_range(writer, 336, 363, "Report-heavy divergence", "Moving toward cells where reporting rank exceeds modeled abundance rank")
        append_range(writer, 364, 387, "Report-heavy divergence", "Strong positive divergence among observed grid cells")
        append_range(writer, 388, 411, "Report-heavy example", "Hover: reporting rank is much higher than modeled abundance rank", repeat=2)

        red_hover = add_label(
            load_frame(411),
            "Report-heavy example",
            "Reporting rank is much higher than modeled abundance rank",
        )
        hold(writer, red_hover, 16)

        append_range(writer, 412, 435, "Reporting–abundance divergence", "Pulling back before moving across the state")
        append_range(writer, 436, 461, "Model-high divergence", "Moving toward cells where modeled abundance rank is higher")
        append_range(writer, 462, 485, "Model-high divergence", "Strong negative divergence among observed grid cells")
        append_range(writer, 486, 509, "Model-high example", "Hover: modeled abundance rank exceeds reporting rank", repeat=2)

        blue_hover = add_label(
            load_frame(509),
            "Model-high example",
            "Modeled abundance rank exceeds reporting rank",
        )
        hold(writer, blue_hover, 16)

        if divergence_showcase:
            print("Adding divergence showcase stops...")
            divergence_last = add_showcase_sequence(writer, divergence_showcase, blue_hover)
        else:
            divergence_last = blue_hover

        # SCATTER
        print("Adding spatial association plot...")
        scatter_img = scatter_card()
        for img in crossfade(divergence_last, scatter_img, 16):
            append_image(writer, img)
        hold(writer, scatter_img, 48)

        # VISUAL RECAP
        print("Adding three-view recap...")
        insight = insight_card()
        if insight is None:
            raise RuntimeError(
                "insight_card() did not return an image. "
                "Check for: return img.convert('RGB')"
            )
        for img in crossfade(scatter_img, insight, 16):
            append_image(writer, img)
        hold(writer, insight, 56)

        # FINAL RESULT
        print("Adding final result...")
        result_card = final_card()
        for img in crossfade(insight, result_card, 16):
            append_image(writer, img)
        hold(writer, result_card, 80)

    print()
    print("======================================")
    print("🎬 POLISHED VIDEO COMPLETE")
    print("======================================")
    print(OUTPUT_VIDEO.resolve())


if __name__ == "__main__":
    main()
