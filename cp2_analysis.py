"""Selecția X și statisticile CP2; fără imputare sau modelare."""
from __future__ import annotations

import numpy as np
import pandas as pd

from run_pipeline import DAYS


# Ordinea este parte a contractului CSV: ERA5, MODIS NDVI, MODIS LST.
FEATURES = {
    "temperature_mean_c": ("ERA5-Land", "Temperatură medie aer", "°C"),
    "temperature_max_c": ("ERA5-Land", "Maxim al temperaturii medii regionale", "°C"),
    "dewpoint_mean_c": ("ERA5-Land", "Punct de rouă mediu", "°C"),
    "relative_humidity_mean_pct": ("ERA5-Land", "Umiditate relativă medie", "%"),
    "wind_speed_mean_mps": ("ERA5-Land", "Viteză medie vânt", "m/s"),
    "wind_speed_max_mps": ("ERA5-Land", "Maxim al vitezei medii regionale", "m/s"),
    "precipitation_total_mm": ("ERA5-Land", "Precipitații totale", "mm/zi"),
    "solar_radiation_total_mjm2": ("ERA5-Land", "Radiație solară totală", "MJ/m²/zi"),
    "soil_moisture_mean_m3m3": ("ERA5-Land", "Umiditate sol, strat 0–7 cm", "m³/m³"),
    "ndvi_mean": ("MODIS NDVI", "NDVI regional", "adimensional"),
    "lst_day_mean_c": ("MODIS LST", "Temperatură suprafață, zi", "°C"),
    "lst_night_mean_c": ("MODIS LST", "Temperatură suprafață, noapte", "°C"),
}
ERA_FEATURES = [name for name, spec in FEATURES.items() if spec[0] == "ERA5-Land"]
MODIS_FEATURES = [name for name in FEATURES if name not in ERA_FEATURES]
ERA_QUALITY = ["era5_hourly_observations", "precipitation_interval_hours", "precipitation_complete",
               "solar_radiation_interval_hours", "solar_radiation_complete"]
NDVI_QUALITY = ["ndvi_total_pixels", "ndvi_valid_pixels_pct", "ndvi_valid_pixel_count",
                "ndvi_age_days", "ndvi_carry_days", "ndvi_is_carried",
                "ndvi_composite_start", "ndvi_composite_end_exclusive", "ndvi_available_from"]
LST_QUALITY = ["lst_total_pixels", "lst_composite_start", "lst_composite_end_exclusive", "lst_available_from"] + [
    f"lst_{period}_{suffix}" for period in ["day", "night"]
    for suffix in ["valid_pixels_pct", "valid_pixel_count", "age_days", "carry_days", "is_carried"]]
DATE_SUFFIXES = ("_composite_start", "_composite_end_exclusive", "_available_from", "_observation_date")


def parse_dates(frame):
    frame = frame.copy()
    for name in frame:
        if name == "date" or name.endswith(DATE_SUFFIXES):
            frame[name] = pd.to_datetime(frame[name], errors="raise")
    return frame


def check_calendar(frame, days=DAYS):
    if not frame.date.reset_index(drop=True).equals(pd.Series(days, name="date")):
        raise ValueError("CP2: calendarul nu coincide exact cu zilele studiului")


def build_matrix(aligned, era5_lag_days=1, ndvi_policy="strict"):
    if era5_lag_days != 1:
        raise ValueError("CP2 autorizat: ERA5 din D−1; alte decalaje necesită o decizie metodologică")
    if ndvi_policy not in {"strict", "justified"}:
        raise ValueError("Politică NDVI necunoscută")
    aligned = parse_dates(aligned)
    # Join explicit pe dată, nu shift pe poziție: o zi lipsă nu devine D−1.
    x = aligned[["date"]].copy()
    x["era5_observation_date"] = x.date - pd.Timedelta(days=era5_lag_days)
    era = aligned[["date"] + ERA_FEATURES + ERA_QUALITY].rename(columns={"date":"era5_observation_date"})
    x = x.merge(era, on="era5_observation_date", how="left", validate="one_to_one")
    # Data cerută D−1 este păstrată inclusiv când acea zi lipsește din arhivă.
    for name in ERA_FEATURES:
        x[f"{name}_missing"] = x[name].isna().astype(int)
    modis = aligned[["date"] + MODIS_FEATURES + NDVI_QUALITY + LST_QUALITY].copy()
    if ndvi_policy == "justified":
        for suffix in ["mean", "valid_pixels_pct", "valid_pixel_count", "age_days", "carry_days", "is_carried"]:
            modis[f"ndvi_{suffix}"] = aligned[f"ndvi_justified_{suffix}"]
    x = x.merge(modis, on="date", how="left", validate="one_to_one")
    for name in MODIS_FEATURES:
        x[f"{name}_missing"] = x[name].isna().astype(int)
    order = ["date"] + ERA_FEATURES + ["era5_observation_date"] + ERA_QUALITY + [f"{n}_missing" for n in ERA_FEATURES]
    order += ["ndvi_mean"] + NDVI_QUALITY + ["ndvi_mean_missing"]
    order += ["lst_day_mean_c", "lst_night_mean_c"] + LST_QUALITY + ["lst_day_mean_c_missing", "lst_night_mean_c_missing"]
    return x[order]


def variable_spec(name, table):
    if name in FEATURES:
        source, label, unit = FEATURES[name]
        role = "predictor" if table.startswith("X_") else "observatie_contemporana"
        description = label
    else:
        source = "VIIRS" if name.startswith("viirs_") else "MODIS NDVI" if name.startswith("ndvi_") else "MODIS LST" if name.startswith("lst_") else "ERA5-Land"
        role, unit = "calitate_acoperire", "număr"
        label = name.replace("_", " ")
        description = label
        if name == "date":
            source, role, unit, description = "Calendar", "identificator", "zi UTC", "Ziua investigată D"
        elif name.endswith(DATE_SUFFIXES):
            role, unit = "provenienta_temporala", "dată UTC"
            if name.endswith("_age_days"):
                unit = "zile"
        elif name.endswith("_missing") and name.removesuffix("_missing") in FEATURES:
            source = FEATURES[name.removesuffix("_missing")][0]
            role, unit, description = "indicator_lipsa", "0/1", "1 = predictor lipsă; 0 = predictor prezent; nu este o imputare"
        elif name.startswith("viirs_"):
            role = "detectie_descriptiva"
            unit = "MW" if "frp" in name else "0/1" if "has_detection" in name else "detecții"
            description = "Înregistrări VIIRS observate; zero nu demonstrează absența incendiului"
            if "nominal_high" in name:
                description += "; numai confidence n/h"
            elif "low_confidence" in name:
                description += "; confidence l"
            if "frp_sum" in name:
                description += "; suma FRP peste achiziții, nu energie zilnică sau putere simultană"
        elif name == "ndvi_justified_mean":
            unit, role, description = "adimensional", "sensibilitate_QA", "NDVI cu marginale justificate prin QA detaliat"
        elif name.endswith("_pct"):
            unit, description = "%", "Procent pixeli valizi din toate centrele selectate în BBOX"
        elif name.endswith("_age_days"):
            unit, description = "zile", "Vechime față de ultima zi a ferestrei; minim 1; nu ziua exactă a achiziției pixelului"
        elif name.endswith("_carry_days"):
            unit, description = "zile", "Zile de la prima alocare permisă după închiderea ferestrei; minim 0"
        elif name.endswith("_is_carried"):
            unit, description = "0/1", "1 = valoare repetată după prima alocare permisă; 0 nu înlocuiește valoarea lipsă"
        elif name.endswith("_complete"):
            unit, description = "0/1", "1 = 24 intervale valide; totalul incomplet rămâne NaN"
        elif name.endswith("_hours") or name == "era5_hourly_observations":
            unit, description = "ore", "Număr de ore/intervale regionale valide"
        elif name.endswith("_partial_mm"):
            unit, role, description = "mm", "suma_partiala", "Sumă numai pe intervalele disponibile; nu se folosește în X"
        elif name.endswith("_partial_mjm2"):
            unit, role, description = "MJ/m²", "suma_partiala", "Sumă numai pe intervalele disponibile; nu se folosește în X"
        elif "pixel" in name:
            unit, description = "pixeli", "Suport spațial al compozitului în BBOX; numărul rămâne asociat valorii reportate"
    if table.startswith("X_"):
        temporal = "ziua UTC D−1" if source == "ERA5-Land" else "compozit cu sfârșit exclusiv ≤ D" if source.startswith("MODIS") else "D"
    else:
        temporal = "ziua UTC D" if source in {"ERA5-Land", "VIIRS"} else "compozit cu sfârșit exclusiv ≤ D" if source.startswith("MODIS") else "D"
    if name.endswith("_observation_date"):
        description = "Data ERA5 cerută D−1; păstrată chiar dacă lipsește din intervalul extras"
    elif name.endswith("_composite_start"):
        description = "Începutul ferestrei conform metadatelor produsului"
    elif name.endswith("_composite_end_exclusive"):
        description = "Prima clipă din afara ferestrei observațiilor"
    elif name.endswith("_available_from"):
        description = "Închiderea ferestrei observațiilor; nu data istorică de publicare"
    if table == "X_sensibilitate" and name.startswith("ndvi_"):
        description += "; politică marginală justificată în acest tabel"
    return dict(source=source, label=label, unit=unit, role=role, description=description,
                temporal_alignment=temporal, used_in_main_correlation=int(table == "X_principal" and name in FEATURES))


def make_dictionary(tables):
    return pd.DataFrame([dict(table=table, variable=name, dtype=str(frame[name].dtype),
                              **variable_spec(name, table)) for table, frame in tables.items() for name in frame])


def descriptive_statistics(tables):
    records = []
    for table, frame in tables.items():
        for name in frame.select_dtypes(include="number"):
            values = frame[name].dropna()
            if np.isinf(values).any():
                raise ValueError(f"CP2: valori infinite {table}/{name}")
            quartiles = values.quantile([.25,.5,.75], interpolation="linear")
            spec = variable_spec(name, table)
            records.append(dict(table=table, variable=name, source=spec["source"], role=spec["role"], unit=spec["unit"],
                                n_total=len(frame), n_valid=len(values), n_missing=int(frame[name].isna().sum()),
                                missing_pct=100*frame[name].isna().mean(), mean=values.mean(), median=values.median(),
                                std=values.std(ddof=1), min=values.min(), q25=quartiles.loc[.25],
                                q50=quartiles.loc[.5], q75=quartiles.loc[.75], max=values.max()))
    return pd.DataFrame(records)


def spearman_pairwise(frame):
    """Ranguri medii pentru egalități, recalculate pe zilele comune fiecărei perechi."""
    if np.isinf(frame.to_numpy(dtype=float)).any():
        raise ValueError("Valori infinite în predictori")
    valid = frame.notna().astype(np.int64)
    counts = valid.T @ valid
    correlation = pd.DataFrame(np.nan, index=frame.columns, columns=frame.columns)
    for i, left in enumerate(frame):
        for right in frame.columns[i:]:
            pair = frame[[left, right]].dropna() if left != right else frame[[left]].dropna()
            if len(pair) < 2 or pair.nunique().min() < 2:
                continue
            if left == right:
                rho = 1.
            else:
                ranks = pair.rank(method="average")
                rho = float(np.corrcoef(ranks[left], ranks[right])[0,1])
            correlation.loc[left,right] = correlation.loc[right,left] = rho
    return correlation, counts


def cross_source_correlations(correlation, counts):
    rows = []
    for era in ERA_FEATURES:
        for modis in MODIS_FEATURES:
            rows.append(dict(era5_variable=era, era5_label=FEATURES[era][1], era5_unit=FEATURES[era][2],
                             modis_variable=modis, modis_label=FEATURES[modis][1], modis_unit=FEATURES[modis][2],
                             spearman_rho=correlation.loc[era,modis], n_valid_days=int(counts.loc[era,modis])))
    result = pd.DataFrame(rows)
    result["absolute_rho"] = result.spearman_rho.abs()
    return result.sort_values(["absolute_rho","era5_variable","modis_variable"], ascending=[False,True,True], kind="stable").reset_index(drop=True)


def source_coverage(matrix):
    rows = []
    for source in dict.fromkeys(spec[0] for spec in FEATURES.values()):
        names = [name for name, spec in FEATURES.items() if spec[0] == source]
        subset = matrix[names]
        rows.append(dict(source=source, n_predictors=len(names), n_days=len(matrix), n_cells=subset.size,
                         n_valid_cells=int(subset.notna().sum().sum()), n_missing_cells=int(subset.isna().sum().sum()),
                         missing_cells_pct=100*subset.isna().sum().sum()/subset.size,
                         days_with_any_missing=int(subset.isna().any(axis=1).sum()),
                         days_all_predictors_valid=int(subset.notna().all(axis=1).sum())))
    return pd.DataFrame(rows)
