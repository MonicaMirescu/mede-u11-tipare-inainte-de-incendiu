"""Reguli metodologice pure, testabile separat de arhivele reale."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


def attribute(obj, name):
    value = np.asarray(obj.attrs[name]).reshape(-1)[0]
    return value.decode() if isinstance(value, bytes) else value.item() if isinstance(value, np.generic) else value


def decode_time(variable):
    """Decodează unitățile efective; calendarul julian AppEEARS e echivalent aici."""
    units = attribute(variable, "units")
    match = re.fullmatch(r"(hours|seconds|days) since (.+)", units)
    if not match:
        raise ValueError(f"Unități temporale nesuportate: {units}")
    origin = pd.Timestamp(match[2])
    if origin.tzinfo:
        origin = origin.tz_convert("UTC").tz_localize(None)
    dates = pd.DatetimeIndex(origin + pd.to_timedelta(variable[:], unit={"hours": "h", "seconds": "s", "days": "D"}[match[1]]))
    calendar = attribute(variable, "calendar") if "calendar" in variable.attrs else "standard"
    if calendar == "julian":
        # În acest interval, aceleași zile bisecte după originea comună 2000.
        if origin != pd.Timestamp("2000-01-01") or not dates.to_series().between("2000-01-01", "2099-12-31").all():
            raise ValueError("Calendar julian în afara intervalului verificat 2000–2099")
    elif calendar not in {"standard", "gregorian", "proleptic_gregorian"}:
        raise ValueError(f"Calendar nesuportat: {calendar}")
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Timpi duplicați sau neordonați")
    return dates


def validate_grid(lat, lon, bbox, reference=None, spacing=None):
    for values, low, high, name in [(lat, bbox["south"], bbox["north"], "latitude"),
                                     (lon, bbox["west"], bbox["east"], "longitude")]:
        values = np.asarray(values)
        if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
            raise ValueError(f"Coordonate invalide: {name}")
        diff = np.diff(values)
        if not ((diff > 0).all() or (diff < 0).all()):
            raise ValueError(f"Coordonate neordonate/duplicate: {name}")
        if np.any(values < low - 1e-8) or np.any(values > high + 1e-8):
            raise ValueError(f"Coordonate în afara BBOX: {name}")
        if spacing is not None and not np.allclose(np.abs(diff), spacing, rtol=0, atol=1e-8):
            raise ValueError(f"Pas de grilă neașteptat: {name}")
    if reference is not None:
        for actual, expected in zip((lat, lon), reference):
            if np.shape(actual) != np.shape(expected) or not np.allclose(actual, expected, rtol=0, atol=1e-10):
                raise ValueError("Grile geografice diferite între fișiere")


def relative_humidity(temperature_k, dewpoint_k):
    t, d = temperature_k - 273.15, dewpoint_k - 273.15
    return np.clip(100 * np.exp(17.625*d/(243.04+d) - 17.625*t/(243.04+t)), 0, 100)


def interval_daily(series, days):
    """Valoarea la t acoperă (t-1h,t]; nu se dezacumulează din nou."""
    if series.index.has_duplicates or (series.index != series.index.floor("h")).any():
        raise ValueError("Intervale orare duplicate sau timestamp în afara orei exacte")
    shifted = series.set_axis(series.index - pd.Timedelta(hours=1))
    grouped = shifted.resample("D")
    count = grouped.count().reindex(days, fill_value=0).astype(int)
    partial = grouped.sum(min_count=1).reindex(days)
    complete = count.eq(24)
    return pd.DataFrame({"total": partial.where(complete), "partial": partial,
                         "interval_hours": count, "complete": complete.astype(int)}, index=days)


def ndvi_masks(raw, reliability, quality):
    """Două politici explicite. Nu se completează pixeli respinși."""
    physical = (raw >= -2000) & (raw <= 10000)
    # Exportul și textul ghidului descriu 13 niveluri utilizabile (0–12).
    # Nu eliminăm 3/5/6/7/11 doar fiindcă tabelul prescurtat nu le enumeră.
    # 13–15 înseamnă inutilizabil/defect/neprocesat; 12 nu este no-data.
    useful = ((quality >> 2) & 15) <= 12
    clean = ((quality >= 0) & (quality < 65535) & useful
             & (((quality >> 6) & 3) != 3)  # fără aerosol ridicat
             & ((quality & ((1 << 8) | (1 << 10) | (1 << 14) | (1 << 15))) == 0)
             & (((quality >> 11) & 7) == 1))  # teren, nu apă
    strict = physical & clean & (reliability == 0) & ((quality & 3) == 0)
    marginal = physical & clean & (reliability == 1) & np.isin(quality & 3, [0, 1])
    return {"strict": strict, "justified": strict | marginal,
            "legacy": physical & np.isin(reliability, [0, 1])}


def lst_mask(raw, qa):
    # QC=0 este valid chiar dacă exportul AppEEARS îl declară și _FillValue.
    return ((raw >= 7500) & (raw <= 65535) & ((qa & 3) == 0)
            & (raw * 0.02 >= 200) & (raw * 0.02 <= 360))


def composite_periods(ds, product, dates, metadata):
    """Preferă time bounds din fișier; altfel extrasul NASA CMR versionat."""
    time = ds["time"]
    if "bounds" in time.attrs:
        key = attribute(time, "bounds")
        bounds = ds[key][:]
        if bounds.shape != (len(dates), 2):
            raise ValueError("Formă invalidă time bounds")
        units = attribute(time, "units")
        match = re.fullmatch(r"(seconds|hours|days) since (.+)", units)
        if not match:
            raise ValueError("Unități time bounds nesuportate")
        origin = pd.Timestamp(match[2])
        origin = origin.tz_localize(None) if origin.tzinfo else origin
        decoded = origin + pd.to_timedelta(bounds.ravel(), unit={"seconds":"s", "hours":"h", "days":"D"}[match[1]])
        starts, ends = decoded[::2], decoded[1::2]
        provenance = "NetCDF time bounds"
    else:
        periods = metadata["products"][product]["periods"]
        rows = []
        for day in dates:
            key = day.strftime("%Y-%m-%d")
            if key not in periods:
                raise ValueError(f"Lipsesc metadata temporale NASA: {product} {key}; actualizați extrasul CMR")
            rows.append(periods[key])
        starts = pd.DatetimeIndex(pd.to_datetime([r["start"] for r in rows], utc=True)).tz_localize(None)
        ends = pd.DatetimeIndex(pd.to_datetime([r["end_exclusive"] for r in rows], utc=True)).tz_localize(None)
        provenance = "NASA CMR cached temporal bounds"
    nominal = 16 if product == "MOD13Q1.061" else 8
    if not np.array_equal(starts.values, dates.values):
        raise ValueError("Începutul ferestrei diferă de timestamp-ul compozitului")
    durations = (ends - starts) / pd.Timedelta(days=1)
    if not ((durations >= 1) & (durations <= nominal) & (durations == np.floor(durations))).all():
        raise ValueError("Durată de compozit invalidă")
    return ends, provenance


def align_composites(data, days, label, nominal_span, value_columns):
    data = data.copy().rename(columns={"composite_start": f"{label}_composite_start",
                                       "composite_end_exclusive": f"{label}_composite_end_exclusive"})
    data[f"{label}_available_from"] = data[f"{label}_composite_end_exclusive"]
    available = f"{label}_available_from"
    # Păstrăm plafonul CP1 (2 perioade după închiderea ferestrei), explicit.
    out = pd.merge_asof(days.sort_values("date"), data.sort_values(available),
                        left_on="date", right_on=available, direction="backward",
                        tolerance=pd.Timedelta(days=nominal_span * 2))
    carry = (out.date - out[available]).dt.total_seconds() / 86400
    for value, prefix in value_columns.items():
        present = out[value].notna()
        out[f"{prefix}_age_days"] = (carry + 1).where(present)
        out[f"{prefix}_carry_days"] = carry.where(present)
        out[f"{prefix}_is_carried"] = (present & carry.gt(0)).astype(int)
    return out


def load_metadata(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
