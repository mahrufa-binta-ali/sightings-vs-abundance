import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
import matplotlib.pyplot as plt


st.set_page_config(
    page_title="Sightings ≠ Abundance",
    layout="wide"
)

# ---------------------------------------------------------
# Optional URL control for automated animation rendering
# ---------------------------------------------------------

params = st.query_params


def qp_str(name, default):
    value = params.get(name, default)
    if isinstance(value, list):
        value = value[0]
    return str(value)


def qp_float(name, default):
    try:
        value = params.get(name, default)
        if isinstance(value, list):
            value = value[0]
        return float(value)
    except Exception:
        return float(default)


capture_mode = qp_str("capture", "0") == "1"

url_mode = qp_str("mode", "Modeled abundance")
url_abundance_threshold = qp_float("abundance_threshold", 0.10)
url_divergence_threshold = qp_float("divergence_threshold", 0.60)

camera_lat = qp_float("lat", 42.9)
camera_lon = qp_float("lon", -75.4)
camera_zoom = qp_float("zoom", 6.2)
camera_pitch = qp_float("pitch", 55)
camera_bearing = qp_float("bearing", 12)


if capture_mode:
    st.markdown(
        """
        <style>

        /* Hide Streamlit chrome */
        [data-testid="stToolbar"] {
            display: none;
        }

        header {
            visibility: hidden;
        }

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        /* Hide sidebar for cinematic capture */
        [data-testid="stSidebar"] {
            display: none;
        }

        /* Let main content use the full width */
        [data-testid="stAppViewContainer"] > .main {
            margin-left: 0;
        }

        .block-container {
            max-width: 1450px;
            padding-top: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

st.title("Sightings ≠ Abundance")
st.caption(
    "Exploring raw eBird reporting and modeled Wood Thrush abundance in New York"
)


# ---------------------------------------------------------
# Load final dataset
# ---------------------------------------------------------

df = pd.read_csv(
    "data/processed/wood_thrush_grid_divergence_2023.csv"
)


# ---------------------------------------------------------
# Sidebar / mode selection
# ---------------------------------------------------------

mode_options = [
    "Modeled abundance",
    "Raw reporting",
    "Reporting–abundance divergence"
]

if capture_mode:
    view_mode = (
        url_mode
        if url_mode in mode_options
        else "Modeled abundance"
    )
else:
    st.sidebar.header("Explore")
    view_mode = st.sidebar.radio(
        "3D layer",
        mode_options
    )

# =========================================================
# MODE 1 — MODELED ABUNDANCE
# =========================================================

if view_mode == "Modeled abundance":

    if capture_mode:
        threshold = url_abundance_threshold
    else:
        threshold = st.sidebar.slider(
            "Minimum relative abundance",
            0.0,
            1.0,
            0.10,
            0.01
        )

    plot_df = df[
        df["relative_abundance"] >= threshold
    ].copy()

    plot_df["height"] = plot_df["relative_abundance"]

    layer = pdk.Layer(
        "ColumnLayer",
        data=plot_df,
        get_position=["lon", "lat"],
        get_elevation="height",
        elevation_scale=5000,
        radius=1150,
        get_fill_color=[60, 150, 100, 210],
        pickable=True,
        auto_highlight=True,
    )

    layers = [layer]

    tooltip = {
        "html": """
        <b>Modeled relative abundance</b><br/>
        {relative_abundance}<br/><br/>

        <b>Raw eBird records:</b> {report_count}
        """
    }


# =========================================================
# MODE 2 — RAW REPORTING
# =========================================================

elif view_mode == "Raw reporting":

    plot_df = df[
        df["report_count"] > 0
    ].copy()

    plot_df["height"] = np.log1p(
        plot_df["report_count"]
    )

    layer = pdk.Layer(
        "ColumnLayer",
        data=plot_df,
        get_position=["lon", "lat"],
        get_elevation="height",
        elevation_scale=1800,
        radius=1150,
        get_fill_color=[55, 125, 220, 210],
        pickable=True,
        auto_highlight=True,
    )

    layers = [layer]

    tooltip = {
        "html": """
        <b>Raw Wood Thrush reporting</b><br/>
        {report_count} eBird records<br/><br/>

        <b>Modeled relative abundance:</b>
        {relative_abundance}
        """
    }


# =========================================================
# MODE 3 — DIVERGENCE
# =========================================================

else:

    if capture_mode:
        threshold = url_divergence_threshold
    else:
        threshold = st.sidebar.slider(
            "Minimum absolute divergence",
            0.0,
            1.0,
            0.60,
            0.05
        )

    plot_df = df[
        df["divergence_abs"] >= threshold
    ].copy()

    positive = plot_df[
        plot_df["divergence"] > 0
    ].copy()

    negative = plot_df[
        plot_df["divergence"] < 0
    ].copy()

    positive["height"] = positive["divergence_abs"]
    negative["height"] = negative["divergence_abs"]

    positive_layer = pdk.Layer(
        "ColumnLayer",
        data=positive,
        get_position=["lon", "lat"],
        get_elevation="height",
        elevation_scale=8500,
        radius=1300,
        get_fill_color=[225, 75, 70, 225],
        pickable=True,
        auto_highlight=True,
    )

    negative_layer = pdk.Layer(
        "ColumnLayer",
        data=negative,
        get_position=["lon", "lat"],
        get_elevation="height",
        elevation_scale=8500,
        radius=1300,
        get_fill_color=[55, 125, 220, 225],
        pickable=True,
        auto_highlight=True,
    )

    layers = [
        positive_layer,
        negative_layer
    ]

    tooltip = {
        "html": """
        <b>Reporting–abundance divergence</b><br/>
        Divergence: {divergence}<br/><br/>

        <b>eBird records:</b> {report_count}<br/>
        <b>Modeled abundance:</b> {relative_abundance}<br/>
        <b>Reporting percentile:</b> {report_score}<br/>
        <b>Abundance percentile:</b> {abundance_score}
        """
    }

# ---------------------------------------------------------
# Sidebar information
# ---------------------------------------------------------

st.sidebar.metric(
    "Cells displayed",
    f"{len(plot_df):,}"
)



if view_mode == "Reporting–abundance divergence":

    st.sidebar.markdown(
        """
        🔴 **Reporting rank higher**

        🔵 **Modeled abundance rank higher**

        Taller columns = stronger divergence
        """
    )


# ---------------------------------------------------------
# Camera
# ---------------------------------------------------------

view = pdk.ViewState(
    latitude=camera_lat,
    longitude=camera_lon,
    zoom=camera_zoom,
    pitch=camera_pitch,
    bearing=camera_bearing
)


deck = pdk.Deck(
    layers=layers,
    initial_view_state=view,
    map_provider="carto",
    map_style="light",
    tooltip=tooltip
)


map_height = 780 if capture_mode else 700

st.pydeck_chart(
    deck,
    width="stretch",
    height=map_height,
    key=f"map_{view_mode}"
)

# ---------------------------------------------------------
# Quantitative result for divergence view
# ---------------------------------------------------------

if view_mode == "Reporting–abundance divergence":

    st.markdown("### Spatial association")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Observed grid cells",
        "2,590"
    )

    col2.metric(
        "Spearman ρ",
        "0.119"
    )

    col3.metric(
        "p-value",
        "1.09 × 10⁻⁹"
    )

    st.caption(
        "The association is statistically detectable but weak; "
        "the p-value should not be interpreted as evidence of a strong relationship."
    )

    st.info(
        "Takeaway: Raw reporting concentration shows only a weak spatial "
        "rank association with modeled relative abundance across observed cells."
    )

    observed_df = df[df["report_count"] > 0].copy()

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.scatter(
        observed_df["abundance_score"],
        observed_df["report_score"],
        alpha=0.25,
        s=15
    )

    ax.set_xlabel("Modeled abundance percentile")
    ax.set_ylabel("Reporting percentile")
    ax.set_title("Reporting vs. modeled abundance rank")

    ax.text(
        0.03,
        0.95,
        "Spearman ρ = 0.119",
        transform=ax.transAxes,
        verticalalignment="top"
    )

    st.pyplot(fig)

    plt.close(fig)


# =========================================================
# Explanatory text
# =========================================================

if view_mode == "Modeled abundance":

    st.markdown(
        """
        ### Modeled abundance

        Column height represents Cornell eBird Status & Trends
        **modeled relative abundance** for Wood Thrush.

        This is not a raw count of birds or observations.
        """
    )


elif view_mode == "Raw reporting":

    st.markdown(
        """
        ### Raw reporting

        Column height represents Wood Thrush **eBird observation
        records** within each Cornell ~3 km raster cell during the
        selected 2023 breeding-season window.

        Heights are log-scaled because reporting is strongly
        concentrated across locations.
        """
    )


else:

    st.markdown(
        """
        ### Reporting–abundance divergence

        Among raster cells containing at least one Wood Thrush
        observation record, this view compares the spatial percentile
        rank of reporting concentration with the percentile rank of
        modeled relative abundance.

        **Red:** reporting ranks higher than modeled abundance.

        **Blue:** modeled abundance ranks higher than reporting.

        Taller columns indicate stronger divergence.

        This is an exploratory comparison. It does **not** estimate
        observer effort, sampling bias, detection probability, or
        population error.
        """
    )