"""Protocol fixat înainte de examinarea rezultatelor CP3."""
from pathlib import Path

import pandas as pd
from cp2_analysis import FEATURES as CP2_FEATURES, ERA_FEATURES, MODIS_FEATURES

PROJECT = Path(__file__).resolve().parent.parent
BASE_COMMIT = "aa276aa836b1283319a80db11c30397853f8fb90"
DAYS = pd.date_range("2020-01-01", "2024-12-31", freq="D")
NOAA_FEATURES = ["nao_index", "ao_index"]
FEATURES = list(CP2_FEATURES) + NOAA_FEATURES
GROUPS = {
    "ERA5": ERA_FEATURES,
    "MODIS": MODIS_FEATURES,
    "NOAA": NOAA_FEATURES,
    "ERA5_MODIS": list(CP2_FEATURES),
    "ERA5_NOAA": ERA_FEATURES + NOAA_FEATURES,
    "TOATE": FEATURES,
}
SEEDS = [11, 22, 33, 44, 55]
MAIN_SEED = 11
K = 15
UMAP_PARAMETERS = dict(n_neighbors=15, min_dist=0.1, metric="euclidean",
                       n_epochs=300, n_jobs=1, init="random", low_memory=True)
SPLITS = {"train": ("2020-01-01", "2022-12-31"),
          "validation": ("2023-01-01", "2023-12-31"),
          "test": ("2024-01-01", "2024-12-31")}
MAXIMA = {"temperature_max_c", "wind_speed_max_mps"}
SUMS = {"precipitation_total_mm", "solar_radiation_total_mjm2"}
TABLES = ["matrice_CP3_zilnica.csv", "matrice_CP3_7zile.csv", "acoperire_CP3.csv",
          "rezultate_PCA_UMAP.csv", "stabilitate_CP3.csv", "relatii_ERA5_NOAA.csv"]
FIGURES = ["baseline_PCA.png", "comparatie_PCA_UMAP.png", "stabilitate.png", "relatii_surse.png"]


def dimensions(group):
    return 1 if group == "NOAA" else 2


def split_labels(dates):
    dates = pd.Series(pd.to_datetime(dates)).reset_index(drop=True)
    out = pd.Series("", index=dates.index, dtype="object")
    for name, (start, end) in SPLITS.items():
        out.loc[dates.between(start, end)] = name
    if out.eq("").any():
        raise ValueError("Date în afara perioadelor CP3")
    return out
