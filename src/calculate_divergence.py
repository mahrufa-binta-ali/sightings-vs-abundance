import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

input_path = (
    ROOT
    / "data"
    / "processed"
    / "wood_thrush_grid_2023.csv"
)

output_path = (
    ROOT
    / "data"
    / "processed"
    / "wood_thrush_grid_divergence_2023.csv"
)

df = pd.read_csv(input_path)

# ---------------------------------------------------------
# Only cells containing >=1 Wood Thrush observation record
# ---------------------------------------------------------

df["divergence"] = np.nan
df["divergence_abs"] = np.nan

observed = df["report_count"] > 0

comparison = df.loc[observed].copy()


# ---------------------------------------------------------
# Reporting concentration
# log transform first because counts are highly skewed
# ---------------------------------------------------------

comparison["log_reports"] = np.log1p(
    comparison["report_count"]
)

comparison["report_score"] = (
    comparison["log_reports"]
    .rank(method="average", pct=True)
)


# ---------------------------------------------------------
# Modeled abundance rank
# ---------------------------------------------------------

comparison["abundance_score"] = (
    comparison["relative_abundance"]
    .rank(method="average", pct=True)
)


# ---------------------------------------------------------
# Divergence
# ---------------------------------------------------------

comparison["divergence"] = (
    comparison["report_score"]
    - comparison["abundance_score"]
)

comparison["divergence_abs"] = (
    comparison["divergence"].abs()
)


# Put results back into full NY grid
df.loc[comparison.index, "report_score"] = comparison["report_score"]
df.loc[comparison.index, "abundance_score"] = comparison["abundance_score"]
df.loc[comparison.index, "divergence"] = comparison["divergence"]
df.loc[comparison.index, "divergence_abs"] = comparison["divergence_abs"]


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

df.to_csv(output_path, index=False)


# ---------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------

print("\nTotal NY cells:", len(df))
print("Cells included in divergence analysis:", len(comparison))

print("\nDivergence statistics:")
print(comparison["divergence"].describe())


print("\nHighest report-heavy divergence:")

print(
    comparison[
        [
            "lat",
            "lon",
            "report_count",
            "relative_abundance",
            "report_score",
            "abundance_score",
            "divergence"
        ]
    ]
    .sort_values("divergence", ascending=False)
    .head(10)
)


print("\nHighest model-heavy divergence:")

print(
    comparison[
        [
            "lat",
            "lon",
            "report_count",
            "relative_abundance",
            "report_score",
            "abundance_score",
            "divergence"
        ]
    ]
    .sort_values("divergence")
    .head(10)
)


print("\nSaved:")
print(output_path)

from scipy.stats import spearmanr

rho, p = spearmanr(
    comparison["report_count"],
    comparison["relative_abundance"]
)

print("\nSpearman correlation:")
print("rho =", rho)
print("p =", p)