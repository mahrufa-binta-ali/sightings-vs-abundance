# Sightings ≠ Abundance

### A 3D spatial comparison of community-science reporting and modeled Wood Thrush relative abundance across New York

This project asks a simple question:

> **Do the places where Wood Thrush is reported most often also rank highest in modeled relative abundance?**

Raw community-science observations are not a direct measure of abundance. Reporting patterns can reflect both the ecological distribution of a species and the way people observe, including accessibility, search effort, timing, and where checklists are submitted.

To examine that difference spatially, this project compares raw Wood Thrush reporting with modeled relative abundance across New York during the 2023 breeding season.

---

## Research idea

The comparison follows two parallel spatial signals:

```text
Raw Wood Thrush reporting
        ↓
Reporting percentile rank Rᵢ

Modeled relative abundance
        ↓
Abundance percentile rank Aᵢ

        ↓
Dᵢ = Rᵢ − Aᵢ
        ↓
Spatial divergence analysis
        ↓
Interactive 3D visualization
```

### Where:

- **Rᵢ** = percentile rank of raw reporting in grid cell *i*
- **Aᵢ** = percentile rank of modeled relative abundance in grid cell *i*
- **Dᵢ** = reporting-abundance divergence

### Interpretation:

- **Dᵢ > 0** → reporting rank is higher
- **Dᵢ < 0** → modeled-abundance rank is higher
- **Dᵢ ≈ 0** → the two rankings roughly agree

---

## Why rank-space comparison?

Raw reporting and modeled relative abundance are different quantities and cannot be meaningfully compared using their original numerical scales.

The project therefore converts both variables to percentile ranks on a common 0–1 scale before calculating divergence.

Raw reporting is log-transformed first because the observation counts are strongly skewed:

$$
L_i = \log(1 + C_i)
$$

where **Cᵢ** is the number of Wood Thrush-positive records in grid cell *i*.

The percentile ranks are then calculated as:

```math
R_i = \mathrm{rank}(L_i)
```

```math
A_i = \mathrm{rank}(\mathrm{relative\ abundance}_i)
```

and the divergence is:

```math
D_i = R_i - A_i
```

---

## Quantitative results

The analysis included:

$$
N = 2{,}590
$$

observed grid cells.

The overall spatial rank association was:

$$
\rho = 0.119
$$

using Spearman rank correlation, indicating only a weak positive relationship between raw reporting and modeled abundance ranks.

Additional divergence diagnostics:

$$
MAE_D \approx 0.299
$$

$$
RMS_D \approx 0.373
$$

$$
\max |D_i| \approx 0.989
$$

$$
J_{10} \approx 0.127
$$

---

## Interpretation

### Mean Absolute Error in rank space

**MAE_D** measures the average absolute rank difference:

$$
MAE_D =
\frac{1}{N}
\sum_{i=1}^{N}
|D_i|
$$

An observed value of approximately **0.299** means that the reporting and modeled-abundance ranks differed by about **0.30 of the full 0–1 rank scale on average**.

### Root Mean Square divergence

**RMS_D** gives greater weight to large mismatches:

$$
RMS_D =
\sqrt{
\frac{1}{N}
\sum_{i=1}^{N}
D_i^2
}
$$

The observed value was approximately **0.373**.

### Maximum divergence

The largest observed divergence was:

$$
\max |D_i| \approx 0.989
$$

indicating that the most extreme grid cell had almost a full-scale separation between its two percentile ranks.

### Top-decile overlap

The top-decile overlap was evaluated with the Jaccard index:

```math
J_{10} = \frac{|T_R \cap T_A|}{|T_R \cup T_A|}
```

where:

- **T_R** contains the top 10% of reporting-ranked cells
- **T_A** contains the top 10% of modeled-abundance-ranked cells

The observed value was:

$$
J_{10} \approx 0.127
$$

indicating limited overlap between the two top-ranked spatial sets.

---

## 3D visualization

The Streamlit application provides three views:

### 1. Modeled abundance

- Continuous modeled spatial surface
- Column height represents relative abundance

### 2. Raw reporting

- Cells containing Wood Thrush-positive observation records
- Reporting height is log-scaled

### 3. Reporting-abundance divergence

- 🔴 **Red columns:** reporting rank higher than modeled abundance
- 🔵 **Blue columns:** modeled abundance rank higher than reporting
- Taller columns represent stronger rank divergence

The visualization is designed to answer a question that one correlation coefficient cannot:

> **Where does the disagreement occur geographically?**

```
## Project structure

```text
sightings-vs-abundance/
│
├── app.py
├── README.md
├── requirements.txt
├── .gitignore
│
├── data/
│   └── README.md
│
└── src/
    ├── calculate_divergence.py
    ├── fetch_gbif_wood_thrush.py
    ├── inspect_raster.py
    ├── join_observations_to_grid.py
    ├── raster_to_points.py
    ├── render_frames.py
    ├── render_showcase_frames.py
    └── make_video.py
```

## Workflow

### 1. Acquire occurrence records

Community-science Wood Thrush records are collected for New York during the selected 2023 breeding-season period.

### 2. Prepare modeled abundance raster

The modeled relative-abundance raster is converted into approximately 3 km grid-cell point representations.

### 3. Spatially join observations

Occurrence records are matched to modeled-abundance grid cells.

Each cell receives:

- geographic coordinates
- modeled relative abundance
- Wood Thrush report count

### 4. Calculate rank divergence

Run:

```bash
python src/calculate_divergence.py
```
This calculates:

- log-transformed reporting
- reporting percentile rank
- abundance percentile rank
- divergence
- absolute divergence
- Spearman rank association

### 5. Launch the interactive visualization

```bash
streamlit run app.py
```
### 6. Render cinematic frames

```bash
python src/render_frames.py
```
Optional showcase frames:

```bash
python src/render_showcase_frames.py
```
### 7. Build the final animation

```bash
python src/make_video.py
```
## Installation

Clone the repository:

```bash
git clone https://github.com/mahrufa-binta-ali/sightings-vs-abundance.git
cd sightings-vs-abundance|
```
Create a virtual environment:

```bash
python -m venv .venv
```
On Windows:

```bash
.venv\Scripts\activate
```
Install dependencies:

```bash
pip install -r requirements.txt
```
Install the Chromium browser used by Playwright:

```bash
playwright install chromium
```
## Data

Raw and processed datasets are intentionally not redistributed in this repository.

The analysis uses:

- Wood Thrush community-science occurrence records
- Modeled Wood Thrush relative-abundance data
- New York geographic boundary data

See [`data/README.md`](data/README.md) for the expected local directory structure.

---

## Interpretation

The result does **not** show that raw observations are wrong or that the modeled abundance surface is ground truth.

Instead, the two sources represent different views of the same ecological system.

Raw reporting contains information about both bird occurrence and human observation patterns, while modeled relative abundance attempts to standardize the observation process and estimate the underlying spatial pattern.

The weak rank association therefore motivates a more interesting spatial question:

> **What creates the mismatch?**

Potential next analyses include:

- Accessibility
- Observer effort
- Habitat
- Hotspot proximity
- Land cover
- Detection probability
- Spatial sampling bias

---

## Tools

- Python
- pandas
- NumPy
- SciPy
- Rasterio
- PyProj
- Streamlit
- PyDeck / deck.gl
- Matplotlib
- Playwright
- ImageIO / FFmpeg

---

## Author

**Mahrufa Binta Ali**

Project focus: computational ecology, spatial data analysis, biodiversity visualization, and community-science data.


