"""Matrici zilnice/7 zile și un calendar comun, fără imputare sau viitor."""
import numpy as np
import pandas as pd

from .config import (DAYS, CP2_FEATURES, ERA_FEATURES, MODIS_FEATURES, NOAA_FEATURES,
                     FEATURES, GROUPS, SPLITS, MAXIMA, SUMS, split_labels, K)
from .io import read_csv, require

MODIS_DATES = [f"{p}_composite_{s}" for p in ["ndvi", "lst"] for s in ["start", "end_exclusive"]]


def load_cp2(path):
    frame = read_csv(path, parse_dates=["date", "era5_observation_date", *MODIS_DATES])
    require(frame.shape == (1827, 54), "Matricea de plecare CP2 nu are 1827×54")
    require(frame.date.equals(pd.Series(DAYS, name="date")), "Calendar CP2 incorect")
    require(not frame.date.duplicated().any(), "Date CP2 duplicate")
    require((frame.era5_observation_date == frame.date - pd.Timedelta(days=1)).all(), "ERA5 CP2 nu este D−1")
    for p in ["ndvi", "lst"]:
        end = frame[f"{p}_composite_end_exclusive"]
        require((end.isna() | end.le(frame.date)).all(), "MODIS CP2 conține observații viitoare")
    require(not np.isinf(frame[list(CP2_FEATURES)].to_numpy()).any(), "Predictori CP2 infiniți")
    return frame


def rolling_min_date(series, shift=1):
    values = series.map(lambda t: t.value if pd.notna(t) else np.nan).astype(float)
    return pd.to_datetime(values.shift(shift).rolling(7, min_periods=7).min())


def build_matrices(cp2, noaa):
    x = cp2.set_index("date")
    daily = x[list(CP2_FEATURES)].copy()
    for name in NOAA_FEATURES:
        daily[name] = noaa[name].reindex(DAYS - pd.Timedelta(days=1)).to_numpy()
    daily["era5_observation_date"] = DAYS - pd.Timedelta(days=1)
    daily["noaa_observation_date"] = DAYS - pd.Timedelta(days=1)
    for name in MODIS_DATES:
        daily[name] = x[name]
    weekly = pd.DataFrame(index=DAYS)
    weekly.index.name = "date"
    for name in ERA_FEATURES:
        rolling = daily[name].rolling(7, min_periods=7)
        weekly[name] = rolling.max() if name in MAXIMA else rolling.sum() if name in SUMS else rolling.mean()
        weekly[f"{name}_n_valid"] = daily[name].rolling(7, min_periods=1).count().astype(int)
    for name in NOAA_FEATURES:
        # Datele sunt mutate o singură dată de la ziua observației la ziua investigată.
        history = noaa[name].copy()
        history.index = history.index + pd.Timedelta(days=1)
        weekly[name] = history.rolling(7, min_periods=7).mean().reindex(DAYS)
        weekly[f"{name}_n_valid"] = history.rolling(7, min_periods=1).count().reindex(DAYS).fillna(0).astype(int)
    for name in MODIS_FEATURES:
        # Pentru t∈[D−7,D−1], valoarea cunoscută la începutul zilei t este rândul CP2 t.
        # ERA5 este deja D−1 în CP2, dar MODIS este o stare disponibilă la data rândului.
        prior = daily[name].shift(1)
        weekly[name] = prior.rolling(7, min_periods=7).mean()
        weekly[f"{name}_n_valid"] = prior.rolling(7, min_periods=1).count().astype(int)
    weekly = weekly[FEATURES + [f"{n}_n_valid" for n in FEATURES]]
    weekly["observation_window_start"] = DAYS - pd.Timedelta(days=7)
    weekly["observation_window_end"] = DAYS - pd.Timedelta(days=1)
    weekly["modis_asof_window_start"] = DAYS - pd.Timedelta(days=7)
    weekly["modis_asof_window_end"] = DAYS - pd.Timedelta(days=1)
    for prefix in ["ndvi", "lst"]:
        weekly[f"{prefix}_earliest_composite_start"] = rolling_min_date(x[f"{prefix}_composite_start"])
    for frame in [daily, weekly]:
        for name in FEATURES:
            frame[f"{name}_missing"] = frame[name].isna().astype(int)
    daily = daily.reset_index()
    weekly = weekly.reset_index()
    complete = daily[FEATURES].notna().all(axis=1) & weekly[FEATURES].notna().all(axis=1)
    guard = boundary_guard(daily, weekly)
    eligible = complete & guard
    for frame in [daily, weekly]:
        frame["split"] = split_labels(frame.date)
        frame["used_in_experiments"] = eligible.astype(int)
        frame["exclusion_reason"] = np.where(~complete, "missing_in_common_input",
                                              np.where(~guard, "boundary_overlap", "used"))
    for split in SPLITS:
        require(int((eligible & daily.split.eq(split)).sum()) > 2*K,
                f"Prea puține zile comune complete pentru metricile k={K}: {split}")
    return {"1zi": daily, "7zile": weekly}


def boundary_guard(daily, weekly):
    """Separăm ferestrele brute inclusiv compozitele, nu doar etichetele zilelor."""
    guard = pd.Series(True, index=daily.index)
    for split in ["validation", "test"]:
        start = pd.Timestamp(SPLITS[split][0])
        selected = daily.date.between(*SPLITS[split])
        safe = weekly.observation_window_start.ge(start)
        for prefix in ["ndvi", "lst"]:
            safe &= daily[f"{prefix}_composite_start"].ge(start)
            safe &= weekly[f"{prefix}_earliest_composite_start"].ge(start)
        guard.loc[selected] = safe.loc[selected]
    return guard


def coverage_table(matrices):
    rows = []
    for window, frame in matrices.items():
        for split in ["all", *SPLITS]:
            part = frame if split == "all" else frame[frame.split.eq(split)]
            used = part.used_in_experiments.eq(1)
            for group, names in GROUPS.items():
                complete = part[names].notna().all(axis=1)
                rows.append(dict(record_type="group", window=window, split=split, group=group, variable="",
                    n_predictors=len(names), n_days=len(part), n_valid_cells=int(part[names].notna().sum().sum()),
                    n_missing_cells=int(part[names].isna().sum().sum()), n_complete_group=int(complete.sum()),
                    n_used_common=int(used.sum()), n_excluded_common_missing=int(part.exclusion_reason.eq("missing_in_common_input").sum()),
                    n_excluded_boundary=int(part.exclusion_reason.eq("boundary_overlap").sum()),
                    first_used=part.loc[used, "date"].min().strftime("%Y-%m-%d"),
                    last_used=part.loc[used, "date"].max().strftime("%Y-%m-%d"), imputed_values=0))
            for name in FEATURES:
                source = "ERA5" if name in ERA_FEATURES else "MODIS" if name in MODIS_FEATURES else "NOAA"
                rows.append(dict(record_type="variable", window=window, split=split, group=source, variable=name,
                    n_predictors=1, n_days=len(part), n_valid_cells=int(part[name].notna().sum()),
                    n_missing_cells=int(part[name].isna().sum()), n_complete_group=int(part[name].notna().sum()),
                    n_used_common=int(used.sum()), n_excluded_common_missing=int(part.exclusion_reason.eq("missing_in_common_input").sum()),
                    n_excluded_boundary=int(part.exclusion_reason.eq("boundary_overlap").sum()),
                    first_used=part.loc[used, "date"].min().strftime("%Y-%m-%d"),
                    last_used=part.loc[used, "date"].max().strftime("%Y-%m-%d"), imputed_values=0))
    return pd.DataFrame(rows)


def relation_table(daily):
    """Toate perechile zilnice valide, fără selectarea după detecțiile VIIRS."""
    from scipy.stats import spearmanr
    rows = []
    for meteo in ERA_FEATURES:
        for index in NOAA_FEATURES:
            pair = daily[[meteo, index]].dropna()
            rho = spearmanr(pair[meteo], pair[index]).statistic if len(pair) >= 2 and pair.nunique().min() > 1 else np.nan
            rows.append(dict(era5_variable=meteo, noaa_variable=index, spearman_rho=rho,
                             n_valid_days=len(pair), era5_unit=CP2_FEATURES[meteo][2], noaa_unit="adimensional",
                             observation_alignment="D-1", period="2020-2024"))
    return pd.DataFrame(rows)
