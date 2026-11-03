#!/usr/bin/env python3
"""MEDE CP1: load and align ERA5-Land, VIIRS and MODIS to day × region."""
from __future__ import annotations
import argparse
import json
import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from pipeline_methods import (attribute, decode_time, validate_grid, relative_humidity,
                              interval_daily, ndvi_masks, lst_mask, composite_periods,
                              align_composites, load_metadata)

START = pd.Timestamp("2020-01-01")
END = pd.Timestamp("2024-12-31")
BBOX = dict(north=40.2, south=39.7, west=-1.0, east=-0.4)
DAYS = pd.date_range(START, END, freq="D")
METADATA = Path(__file__).parent / "metadata/modis_composite_periods.json"


def archives(input_dir):
    zips = sorted(Path(input_dir).glob("*.zip"))
    def one(keys):
        found = [p for p in zips if any(k in p.name.upper() for k in keys)]
        if len(found) != 1:
            raise ValueError(f"Se așteaptă exact o arhivă {keys} în {input_dir}, găsite: {len(found)}")
        return found[0]
    return one(["ERA5"]), one(["VIIRS", "DL_FIRE"]), one(["MODIS"])


def unpack_member(zf, member, tmp):
    path = Path(tmp) / Path(member).name
    with zf.open(member) as src, path.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return path


def read_era5(path):
    units = {"t2m": "K", "d2m": "K", "tp": "m", "u10": "m s**-1",
             "v10": "m s**-1", "ssrd": "J m**-2", "swvl1": "m**3 m**-3"}
    data, cells, negative_info = {}, {}, {}
    times = None
    reference = None
    with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
        for member in zf.namelist():
            if not member.endswith(".nc"):
                continue
            nc = unpack_member(zf, member, tmp)
            with h5py.File(nc) as ds:
                t = decode_time(ds["valid_time"])
                core = (t >= START) & (t < END + pd.Timedelta(days=1))
                kept = (t >= START) & (t <= END + pd.Timedelta(days=1))
                study_times = t[core]
                if times is None:
                    times = study_times
                elif not np.array_equal(times, study_times):
                    raise ValueError("ERA5: timpi diferiți între fișiere")
                lat, lon = ds["latitude"][:], ds["longitude"][:]
                if attribute(ds["latitude"], "units") != "degrees_north" or attribute(ds["longitude"], "units") != "degrees_east":
                    raise ValueError("ERA5: unități geografice neașteptate")
                validate_grid(lat, lon, BBOX, reference, spacing=0.1)
                if reference is None:
                    reference = (lat, lon)
                for key in sorted(set(units).intersection(ds.keys())):
                    if key in data:
                        raise ValueError(f"ERA5: variabilă duplicată {key}")
                    if attribute(ds[key], "units") != units[key]:
                        raise ValueError(f"ERA5: unități neașteptate pentru {key}")
                    if "scale_factor" in ds[key].attrs or "add_offset" in ds[key].attrs:
                        raise ValueError("ERA5: export împachetat; este necesară decodarea explicită")
                    vals = ds[key][:].astype(float)
                    if "_FillValue" in ds[key].attrs:
                        fill = attribute(ds[key], "_FillValue")
                        vals[vals == fill] = np.nan
                    if np.isinf(vals).any():
                        raise ValueError(f"ERA5: valori infinite {key}")
                    if vals.shape != (len(t), len(lat), len(lon)):
                        raise ValueError(f"ERA5: formă invalidă pentru {key}")
                    if key in ("tp", "ssrd"):
                        tolerance = 1e-7 if key == "tp" else 5.0
                        if np.any(vals < -tolerance):
                            raise ValueError(f"ERA5: {key} negativ peste toleranța de rotunjire {tolerance}")
                        negative_info[key] = {"clipped_cell_hours": int((vals < 0).sum()),
                                              "minimum_raw": float(np.nanmin(vals)), "tolerance_native_units": tolerance}
                        vals = np.maximum(vals, 0)
                    # Media nu ascunde celule lipsă prin schimbarea suportului spațial.
                    data[key] = pd.Series(np.mean(vals[kept], axis=(1, 2)), index=t[kept])
                    if key in ("t2m", "d2m", "u10", "v10"):
                        cells[key] = vals[core]
            nc.unlink()
    if set(data) != set(units):
        raise ValueError(f"ERA5: lipsesc {set(units) - set(data)}")
    hours = pd.DataFrame(data)
    if not (hours.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("ERA5: seria orară nu este continuă")
    temp = hours.t2m - 273.15
    hours["t_c"] = temp
    hours["rh"] = pd.Series(relative_humidity(cells["t2m"], cells["d2m"]).mean(axis=(1, 2)), index=times)
    hours["wind"] = pd.Series(np.hypot(cells["u10"], cells["v10"]).mean(axis=(1, 2)), index=times)
    grouped = hours.resample("D")
    daily = pd.DataFrame(index=pd.date_range(START, END, freq="D", name="date"))
    daily["temperature_mean_c"] = grouped.t_c.mean()
    daily["temperature_max_c"] = grouped.t_c.max()
    daily["dewpoint_mean_c"] = grouped.d2m.mean() - 273.15
    daily["relative_humidity_mean_pct"] = grouped.rh.mean()
    daily["wind_speed_mean_mps"] = grouped.wind.mean()
    daily["wind_speed_max_mps"] = grouped.wind.max()
    for source, prefix, factor, unit in [("tp", "precipitation", 1000, "mm"),
                                          ("ssrd", "solar_radiation", 1e-6, "mjm2")]:
        interval = interval_daily(hours[source] * factor, daily.index)
        daily[f"{prefix}_total_{unit}"] = interval.total
        daily[f"{prefix}_partial_{unit}"] = interval.partial
        daily[f"{prefix}_interval_hours"] = interval.interval_hours
        daily[f"{prefix}_complete"] = interval.complete
    daily["soil_moisture_mean_m3m3"] = grouped.swvl1.mean()
    daily["era5_hourly_observations"] = grouped.t2m.count()
    for key in ["t2m", "d2m", "u10", "v10", "swvl1", "rh", "wind"]:
        daily[f"era5_{key}_valid_hours"] = grouped[key].count()
    if not (daily.era5_hourly_observations == 24).all():
        raise ValueError("ERA5: zi fără 24 valori orare")
    result = daily.reset_index()
    result.attrs["audit"] = {"grid_points": len(reference[0]) * len(reference[1]),
                             "latitude_centers": reference[0].tolist(), "longitude_centers": reference[1].tolist(),
                             "raw_hourly_timestamps": len(hours), "negative_rounding": negative_info,
                             "incomplete_days": result.loc[result.precipitation_complete.eq(0) | result.solar_radiation_complete.eq(0), "date"].dt.strftime("%Y-%m-%d").tolist()}
    return result


def viirs_daily(df):
    """Numără înregistrări observate; zero nu este eticheta «fără incendiu»."""
    counts = df.groupby("date").agg(
        viirs_detection_count=("frp", "size"),
        viirs_frp_sum_mw=("frp", "sum"),
        viirs_frp_max_mw=("frp", "max"))
    daily = pd.DataFrame({"date": DAYS}).merge(counts, left_on="date", right_index=True, how="left")
    daily["viirs_detection_count"] = daily.viirs_detection_count.fillna(0).astype(int)
    daily["viirs_has_detection"] = (daily.viirs_detection_count > 0).astype(int)
    daily["viirs_frp_sum_mw"] = daily.viirs_frp_sum_mw.fillna(0)
    return daily


def read_viirs(path, return_variants=False):
    with zipfile.ZipFile(path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError("VIIRS: se așteaptă un singur CSV")
        with zf.open(members[0]) as fh:
            df = pd.read_csv(fh)
    df["date"] = pd.to_datetime(df.acq_date).dt.normalize()
    df = df[df.date.between(START, END)
            & df.latitude.between(BBOX["south"], BBOX["north"])
            & df.longitude.between(BBOX["west"], BBOX["east"])].copy()
    if not df.confidence.isin(["l", "n", "h"]).all():
        raise ValueError("VIIRS: categorie confidence necunoscută")
    if df.frp.isna().any() or not np.isfinite(df.frp).all() or (df.frp < 0).any():
        raise ValueError("VIIRS: FRP invalid")
    if df.duplicated(["latitude", "longitude", "acq_date", "acq_time", "satellite"]).any():
        raise ValueError("VIIRS: detecții duplicate")
    hhmm = pd.to_numeric(df.acq_time, errors="raise")
    if not ((hhmm >= 0) & (hhmm // 100 < 24) & (hhmm % 100 < 60) & (hhmm == np.floor(hhmm))).all():
        raise ValueError("VIIRS: oră de achiziție invalidă")
    if not df.satellite.eq("SNPP").all() or not pd.to_numeric(df.version).eq(2).all():
        raise ValueError("VIIRS: se așteaptă S-NPP Collection 2")
    daily = viirs_daily(df)
    low = df.loc[df.confidence.eq("l")].groupby("date").size()
    daily["viirs_low_confidence_count"] = daily.date.map(low).fillna(0).astype(int)
    filtered = viirs_daily(df.loc[df.confidence.isin(["n", "h"])])
    info = {"confidence_counts": {str(k): int(v) for k, v in df.confidence.value_counts().items()},
            "filtered_detections": int(filtered.viirs_detection_count.sum()),
            "filtered_days_with_detection": int(filtered.viirs_has_detection.sum()),
            "observation_coverage": "unknown; detection-only archive",
            "frp_sum_meaning": "Sum of observed pixel FRP across acquisitions, not daily energy or simultaneous regional power"}
    return (daily, filtered, info) if return_variants else daily


def pixel_mean(raw, valid, factor, offset=0):
    count = int(valid.sum())
    return ((float(raw[valid].mean()) * factor + offset) if count else np.nan,
            100 * count / valid.size)


def read_modis(path, metadata_path=METADATA, return_details=False):
    ndvi, lst = None, None
    metadata = load_metadata(metadata_path)
    qa_rows, source_info = [], {}
    with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
        for member in zf.namelist():
            if not member.endswith(".nc"):
                continue
            nc = unpack_member(zf, member, tmp)
            with h5py.File(nc) as ds:
                dates = decode_time(ds["time"])
                if not (dates == dates.normalize()).all():
                    raise ValueError("MODIS: compozite cu timestamp în afara începutului zilei")
                lat, lon = ds["lat"][:], ds["lon"][:]
                yy = np.flatnonzero((lat >= BBOX["south"]) & (lat <= BBOX["north"]))
                xx = np.flatnonzero((lon >= BBOX["west"]) & (lon <= BBOX["east"]))
                if not len(xx) or not len(yy):
                    raise ValueError("MODIS: fără pixeli în regiune")
                product = "MOD13Q1.061" if "MOD13Q1" in member else "MOD11A2.061" if "MOD11A2" in member else None
                if product is None:
                    raise ValueError(f"Produs MODIS necunoscut: {member}")
                if product in source_info:
                    raise ValueError(f"Produs MODIS duplicat: {product}")
                ends, provenance = composite_periods(ds, product, dates, metadata)
                source_info[product] = {"time_bounds_source": provenance, "pixel_count": int(len(yy)*len(xx)),
                                        "grid_shape_selected": [len(yy), len(xx)],
                                        "time_units": str(attribute(ds["time"], "units")),
                                        "calendar": str(attribute(ds["time"], "calendar"))}
                rows = []
                if "MOD13Q1" in member:
                    variable = ds["_250m_16_days_NDVI"]
                    if not np.isclose(attribute(variable, "scale_factor"), .0001) or attribute(variable, "_FillValue") != -3000:
                        raise ValueError("NDVI: scală/fill neașteptat")
                    raw_cube = variable[:][:, yy][:, :, xx]
                    qa_cube = ds["_250m_16_days_pixel_reliability"][:][:, yy][:, :, xx]
                    quality_cube = ds["_250m_16_days_VI_Quality"][:][:, yy][:, :, xx]
                    for i, day in enumerate(dates):
                        raw, qa, quality = raw_cube[i], qa_cube[i], quality_cube[i]
                        masks = ndvi_masks(raw, qa, quality)
                        row = dict(composite_start=day, composite_end_exclusive=ends[i], ndvi_total_pixels=raw.size)
                        for variant, prefix in [("strict", "ndvi"), ("justified", "ndvi_justified")]:
                            val, fraction = pixel_mean(raw, masks[variant], .0001)
                            row[f"{prefix}_mean"] = val
                            row[f"{prefix}_valid_pixels_pct"] = fraction
                            row[f"{prefix}_valid_pixel_count"] = int(masks[variant].sum())
                        for variant, mask in masks.items():
                            val, fraction = pixel_mean(raw, mask, .0001)
                            qa_rows.append(dict(composite_start=day, variant=variant, mean=val,
                                                valid_pixel_count=int(mask.sum()), total_pixels=raw.size,
                                                valid_pixels_pct=fraction))
                        row["ndvi_justified_marginal_pixel_count"] = int((masks["justified"] & ~masks["strict"]).sum())
                        rows.append(row)
                    ndvi = pd.DataFrame(rows)
                elif "MOD11A2" in member:
                    cubes = {}
                    for source in ("Day", "Night"):
                        variable = ds[f"LST_{source}_1km"]
                        if not np.isclose(attribute(variable, "scale_factor"), .02) or attribute(variable, "_FillValue") != 0:
                            raise ValueError("LST: scală/fill neașteptat")
                        cubes[source] = (variable[:][:, yy][:, :, xx], ds[f"QC_{source}"][:][:, yy][:, :, xx].astype(np.int64))
                    for i, day in enumerate(dates):
                        row = dict(composite_start=day, composite_end_exclusive=ends[i], lst_total_pixels=len(yy)*len(xx))
                        for source, label in (("Day", "day"), ("Night", "night")):
                            raw, qa = cubes[source][0][i], cubes[source][1][i]
                            # QA=0 is a VALID quality code, NOT missing data.
                            good = lst_mask(raw, qa)
                            val, fraction = pixel_mean(raw, good, 0.02, -273.15)
                            row[f"lst_{label}_mean_c"] = val
                            row[f"lst_{label}_valid_pixels_pct"] = fraction
                            row[f"lst_{label}_valid_pixel_count"] = int(good.sum())
                        rows.append(row)
                    lst = pd.DataFrame(rows)
            nc.unlink()
    if ndvi is None or lst is None:
        raise ValueError("MODIS: lipsesc produsele NDVI sau LST")
    days = pd.DataFrame({"date": DAYS})
    days = align_composites(ndvi, days, "ndvi", 16, {"ndvi_mean": "ndvi", "ndvi_justified_mean": "ndvi_justified"})
    days = align_composites(lst, days, "lst", 8, {"lst_day_mean_c": "lst_day", "lst_night_mean_c": "lst_night"})
    info = {
        "ndvi_composites_total": len(ndvi), "lst_composites_total": len(lst),
        "ndvi_composites_with_valid_pixels": int(ndvi.ndvi_mean.notna().sum()),
        "ndvi_justified_composites_with_valid_pixels": int(ndvi.ndvi_justified_mean.notna().sum()),
        "lst_day_composites_with_valid_pixels": int(lst.lst_day_mean_c.notna().sum()),
        "lst_night_composites_with_valid_pixels": int(lst.lst_night_mean_c.notna().sum()),
        "source_metadata": source_info,
        "default_ndvi_policy": "strict",
        "available_from_meaning": "Observation window end, not historical publication date",
        "max_carry_days_after_window_end": {"ndvi": 32, "lst": 16},
    }
    details = {"ndvi_composites.csv": ndvi, "lst_composites.csv": lst,
               "ndvi_qa_comparison.csv": pd.DataFrame(qa_rows)}
    return (days, info, details) if return_details else (days, info)


def save(frame, destination):
    frame = frame.copy()
    for col in frame.select_dtypes(include="datetime64[ns]").columns:
        frame[col] = frame[col].dt.strftime("%Y-%m-%d")
    frame.to_csv(destination, index=False, float_format="%.12g")


def file_sha256(path):
    with Path(path).open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(fh.read()).hexdigest()


def coverage_report(combined):
    groups = {
        "ERA5-Land": ["temperature_mean_c", "temperature_max_c", "dewpoint_mean_c",
                      "relative_humidity_mean_pct", "wind_speed_mean_mps", "wind_speed_max_mps",
                      "precipitation_total_mm", "solar_radiation_total_mjm2", "soil_moisture_mean_m3m3"],
        "VIIRS detection records": ["viirs_detection_count", "viirs_has_detection"],
        "MODIS NDVI strict": ["ndvi_mean"], "MODIS NDVI justified": ["ndvi_justified_mean"],
        "MODIS LST": ["lst_day_mean_c", "lst_night_mean_c"]}
    records = []
    for source, columns in groups.items():
        for col in columns:
            n = int(combined[col].notna().sum())
            prefix = {"ndvi_mean": "ndvi", "ndvi_justified_mean": "ndvi_justified",
                      "lst_day_mean_c": "lst_day", "lst_night_mean_c": "lst_night"}.get(col)
            records.append(dict(source=source, column=col, days_with_value=n, days_missing=len(DAYS)-n,
                                days_total=len(DAYS), coverage_pct=100*n/len(DAYS),
                                carried_days=int(combined[f"{prefix}_is_carried"].sum()) if prefix else 0,
                                interpretation="record count available; observation coverage unknown" if source.startswith("VIIRS") else "numeric availability"))
    return pd.DataFrame(records)


def coverage_sensitivity(modis):
    records = []
    for value, prefix in [("ndvi_mean", "ndvi"), ("ndvi_justified_mean", "ndvi_justified"),
                          ("lst_day_mean_c", "lst_day"), ("lst_night_mean_c", "lst_night")]:
        for cutoff in [0, 1, 5, 10, 25, 50, 75]:
            usable = modis[value].notna() & modis[f"{prefix}_valid_pixels_pct"].ge(cutoff)
            records.append(dict(variable=value, hypothetical_min_valid_pixels_pct=cutoff,
                                days_with_value=int(usable.sum()), days_removed=int(modis[value].notna().sum()-usable.sum()),
                                applied_to_output=False))
    return pd.DataFrame(records)


def run(input_dir, output_dir, metadata_path=METADATA):
    era_path, viirs_path, modis_path = archives(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print("[1/4] ERA5-Land")
    era = read_era5(era_path)
    print("[2/4] VIIRS Active Fire")
    viirs, viirs_filtered, viirs_info = read_viirs(viirs_path, return_variants=True)
    print("[3/4] MODIS NDVI/LST")
    modis, modis_info, details = read_modis(modis_path, metadata_path, return_details=True)
    print("[4/4] Aliniere zilnică și raport")
    combined = era.merge(viirs, on="date", validate="one_to_one")
    combined = combined.merge(modis, on="date", validate="one_to_one")
    if len(combined) != len(DAYS) or combined.date.duplicated().any():
        raise ValueError("Număr invalid de zile în tabelul aliniat")
    for name, frame in (
        ("era5_daily.csv", era), ("viirs_daily.csv", viirs),
        ("viirs_daily_nominal_high.csv", viirs_filtered),
        ("modis_daily.csv", modis), ("dataset_aliniat_zilnic.csv", combined)):
        save(frame, output_dir / name)
    for name, frame in details.items():
        save(frame, output_dir / name)
    save(coverage_sensitivity(modis), output_dir / "modis_coverage_sensitivity.csv")
    incomplete = era.loc[era.precipitation_complete.eq(0) | era.solar_radiation_complete.eq(0)]
    save(incomplete, output_dir / "era5_incomplete_days.csv")
    report = coverage_report(combined)
    save(report, output_dir / "raport_acoperire.csv")
    info = {
        "study_area": "Bejís–Villanueva de Viver, Castellón, Spain",
        "bbox": BBOX,
        "period": {"start": str(START.date()), "end": str(END.date()), "days": len(DAYS)},
        "era5_hours": int(era.era5_hourly_observations.sum()), "era5_grid_points": era.attrs["audit"]["grid_points"],
        "era5": era.attrs["audit"],
        "required_extra_data": ("tp and ssrd at 2025-01-01 00:00 UTC (interval 2024-12-31 23:00–2025-01-01 00:00), same grid, same de-accumulated source"
                                if END in set(incomplete.date) else None),
        "inputs": [{"file": p.name, "sha256": file_sha256(p)} for p in (era_path, viirs_path, modis_path)],
        "modis_metadata_sha256": file_sha256(metadata_path),
        "viirs_detections": int(viirs.viirs_detection_count.sum()),
        "viirs_days_with_detection": int(viirs.viirs_has_detection.sum()),
        "viirs": viirs_info,
        "modis": modis_info,
        "method": "UTC day; interval-ending ERA5 accumulations shifted by 1h; cell RH before mean; MODIS metadata window bounds; NDVI strict plus justified QA variant",
        "note": "No VIIRS detection is not proof that no fire occurred."
    }
    (output_dir / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Raport de acoperire – MEDE U11 CP1", "",
        f"- Unitate: zi × regiune, 2020–2024 ({len(DAYS)} zile).",
        f"- ERA5: {info['era5_hours']} ore în {info['era5_grid_points']} puncte.",
        f"- VIIRS: {info['viirs_detections']} detecții în {info['viirs_days_with_detection']} zile.",
        f"- MODIS: {modis_info['ndvi_composites_total']} NDVI, {modis_info['lst_composites_total']} LST.",
        f"- Totaluri ERA5 incomplete: {len(incomplete)} zile; totalul este NaN, suma parțială și orele sunt păstrate separat.",
        ("- Pentru ultima zi este necesar tp și ssrd la 2025-01-01 00:00 UTC, pe aceeași grilă și din aceeași sursă dezacumulată."
         if info["required_extra_data"] else "- Ultima zi are toate intervalele de totalizare."),
        f"- VIIRS încredere scăzută: {viirs_info['confidence_counts'].get('l', 0)} detecții; varianta nominal/high: {viirs_info['filtered_detections']} detecții în {viirs_info['filtered_days_with_detection']} zile.",
        "- Zero detecții VIIRS nu înseamnă absența sigură a incendiului.", "",
        "| Sursa | Variabila | Zile valide | Acoperire |",
        "|---|---|---:|---:|"
    ]
    for row in report.itertuples(index=False):
        lines.append(f"| {row.source} | {row.column} | {row.days_with_value}/{row.days_total} | {row.coverage_pct:.2f}% |")
    lines += ["", "## Limitări", "",
              "- Medii calculate în întreaga casetă, fără ponderare pe suprafața pixelilor.",
              "- NDVI strict implicit; varianta marginală justificată este păstrată separat. Fără prag minim de acoperire spațială aplicat.",
              "- Sensibilitatea la praguri ipotetice este în modis_coverage_sensitivity.csv; acestea nu modifică datele.",
              "- *_age_days = zile de la ultima zi a ferestrei (minim 1); *_carry_days = zile de la prima alocare permisă (minim 0). Nu este ziua achiziției fiecărui pixel.",
              "- available_from = sfârșitul exclusiv al ferestrei de observație, nu data istorică a publicării; nu simulează disponibilitatea operațională.",
              "- Reportăm ultimul compozit încheiat, găsit prin căutare în trecut (merge_asof), fără interpolare liniară; limita CP1 rămâne 32 zile NDVI / 16 zile LST după sfârșitul ferestrei.",
              "- Un compozit existent fără pixeli valizi rămâne lipsă; nu se înlocuiește cu un compozit mai vechi.",
              "- Acoperirea numerică VIIRS nu măsoară acoperirea observațională a satelitului.",
              "- Acest pipeline încarcă și aliniază datele; nu evaluează încă un model predictiv."]
    (output_dir / "raport_acoperire.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {len(DAYS)} zile, {info['viirs_detections']} detecții VIIRS")
    return info


def main():
    ap = argparse.ArgumentParser(description="MEDE U11: ingestia ERA5/VIIRS/MODIS")
    ap.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    ap.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    ap.add_argument("--modis-metadata", type=Path, default=METADATA)
    args = ap.parse_args()
    run(args.input_dir, args.output_dir, args.modis_metadata)


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
