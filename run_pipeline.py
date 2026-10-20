#!/usr/bin/env python3
"""MEDE CP1: load and align ERA5-Land, VIIRS and MODIS to day × region."""
from __future__ import annotations
import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

START = pd.Timestamp("2020-01-01")
END = pd.Timestamp("2024-12-31")
BBOX = dict(north=40.2, south=39.7, west=-1.0, east=-0.4)
DAYS = pd.date_range(START, END, freq="D")


def archives(input_dir):
    zips = sorted(Path(input_dir).glob("*.zip"))
    def one(keys):
        found = [p for p in zips if any(k in p.name.upper() for k in keys)]
        if not found:
            raise FileNotFoundError(f"Nu găsesc arhiva {keys} în {input_dir}")
        return found[0]
    return one(["ERA5"]), one(["VIIRS", "DL_FIRE"]), one(["MODIS"])


def unpack_member(zf, member, tmp):
    path = Path(tmp) / Path(member).name
    with zf.open(member) as src, path.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return path


def read_era5(path):
    names = {"t2m", "d2m", "tp", "u10", "v10", "ssrd", "swvl1"}
    data = {}
    times = None
    wind = {}
    with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
        for member in zf.namelist():
            if not member.endswith(".nc"):
                continue
            nc = unpack_member(zf, member, tmp)
            with h5py.File(nc) as ds:
                t = ds["valid_time"][:]
                if times is None:
                    times = t
                elif not np.array_equal(times, t):
                    raise ValueError("ERA5: timpi diferiți între fișiere")
                lat, lon = ds["latitude"][:], ds["longitude"][:]
                if len(lat) * len(lon) != 30:
                    raise ValueError("ERA5: grilă diferită de 30 puncte")
                for key in names.intersection(ds.keys()):
                    vals = ds[key][:].astype(float)
                    if vals.shape != (len(t), len(lat), len(lon)):
                        raise ValueError(f"ERA5: formă invalidă pentru {key}")
                    if key in ("tp", "ssrd"):
                        vals = np.maximum(vals, 0)
                    data[key] = np.nanmean(vals, axis=(1, 2))
                    if key in ("u10", "v10"):
                        wind[key] = vals
            nc.unlink()
    if set(data) != names:
        raise ValueError(f"ERA5: lipsesc {names - set(data)}")
    hours = pd.DataFrame(data, index=pd.to_datetime(times, unit="h", origin="1970-01-01"))
    if not (hours.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("ERA5: seria orară nu este continuă")
    temp = hours.t2m - 273.15
    dew = hours.d2m - 273.15
    hours["t_c"] = temp
    hours["rh"] = np.clip(100 * np.exp(17.625 * dew/(243.04+dew) - 17.625 * temp/(243.04+temp)), 0, 100)
    hours["wind"] = np.nanmean(np.hypot(wind["u10"], wind["v10"]), axis=(1, 2))
    hours["precip"] = hours.tp * 1000
    hours["rad"] = hours.ssrd / 1e6
    grouped = hours.resample("D")
    daily = pd.DataFrame(index=pd.date_range(START, END, freq="D", name="date"))
    daily["temperature_mean_c"] = grouped.t_c.mean()
    daily["temperature_max_c"] = grouped.t_c.max()
    daily["dewpoint_mean_c"] = grouped.d2m.mean() - 273.15
    daily["relative_humidity_mean_pct"] = grouped.rh.mean()
    daily["wind_speed_mean_mps"] = grouped.wind.mean()
    daily["wind_speed_max_mps"] = grouped.wind.max()
    daily["precipitation_total_mm"] = grouped.precip.sum(min_count=1)
    daily["solar_radiation_total_mjm2"] = grouped.rad.sum(min_count=1)
    daily["soil_moisture_mean_m3m3"] = grouped.swvl1.mean()
    daily["era5_hourly_observations"] = grouped.t2m.count()
    if not (daily.era5_hourly_observations == 24).all():
        raise ValueError("ERA5: zi fără 24 valori orare")
    if daily.isna().any().any():
        raise ValueError("ERA5: valori lipsă")
    return daily.reset_index()


def read_viirs(path):
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
    counts = df.groupby("date").agg(
        viirs_detection_count=("frp", "size"),
        viirs_frp_sum_mw=("frp", "sum"),
        viirs_frp_max_mw=("frp", "max"))
    daily = pd.DataFrame({"date": DAYS}).merge(counts, left_on="date", right_index=True, how="left")
    daily["viirs_detection_count"] = daily.viirs_detection_count.fillna(0).astype(int)
    daily["viirs_has_detection"] = (daily.viirs_detection_count > 0).astype(int)
    daily["viirs_frp_sum_mw"] = daily.viirs_frp_sum_mw.fillna(0)
    return daily


def pixel_mean(raw, valid, factor, offset=0):
    count = int(valid.sum())
    return ((float(raw[valid].mean()) * factor + offset) if count else np.nan,
            100 * count / valid.size)


def read_modis(path):
    ndvi, lst = None, None
    with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
        for member in zf.namelist():
            if not member.endswith(".nc"):
                continue
            nc = unpack_member(zf, member, tmp)
            with h5py.File(nc) as ds:
                dates = pd.to_datetime(ds["time"][:], unit="s", origin="2000-01-01").normalize()
                lat, lon = ds["lat"][:], ds["lon"][:]
                yy = np.flatnonzero((lat >= BBOX["south"]) & (lat <= BBOX["north"]))
                xx = np.flatnonzero((lon >= BBOX["west"]) & (lon <= BBOX["east"]))
                if not len(xx) or not len(yy):
                    raise ValueError("MODIS: fără pixeli în regiune")
                ix = np.ix_(yy, xx)
                rows = []
                if "MOD13Q1" in member:
                    for i, day in enumerate(dates):
                        raw = ds["_250m_16_days_NDVI"][i][ix]
                        qa = ds["_250m_16_days_pixel_reliability"][i][ix]
                        ok = (raw != -3000) & (raw >= -2000) & (raw <= 10000) & np.isin(qa, [0, 1])
                        val, fraction = pixel_mean(raw, ok, 0.0001)
                        rows.append(dict(composite_start=day, ndvi_mean=val, ndvi_valid_pixels_pct=fraction))
                    ndvi = pd.DataFrame(rows)
                elif "MOD11A2" in member:
                    for i, day in enumerate(dates):
                        row = dict(composite_start=day)
                        for source, label in (("Day", "day"), ("Night", "night")):
                            raw = ds[f"LST_{source}_1km"][i][ix]
                            qa = ds[f"QC_{source}"][i][ix].astype(np.int64)
                            # QA=0 is a VALID quality code, NOT missing data.
                            good = (raw >= 7500) & (raw <= 65535) & ((qa & 3) == 0)
                            good &= (raw * 0.02 >= 200) & (raw * 0.02 <= 360)
                            val, fraction = pixel_mean(raw, good, 0.02, -273.15)
                            row[f"lst_{label}_mean_c"] = val
                            row[f"lst_{label}_valid_pixels_pct"] = fraction
                        rows.append(row)
                    lst = pd.DataFrame(rows)
            nc.unlink()
    if ndvi is None or lst is None:
        raise ValueError("MODIS: lipsesc produsele NDVI sau LST")
    def available(data, span, label, daily):
        data = data.rename(columns={"composite_start": f"{label}_composite_start"}).copy()
        data[f"{label}_available_from"] = data[f"{label}_composite_start"] + pd.Timedelta(days=span)
        return pd.merge_asof(daily.sort_values("date"), data.sort_values(f"{label}_available_from"),
                             left_on="date", right_on=f"{label}_available_from",
                             direction="backward", tolerance=pd.Timedelta(days=span*2))
    days = pd.DataFrame({"date": DAYS})
    days = available(ndvi, 16, "ndvi", days)
    days = available(lst, 8, "lst", days)
    info = {
        "ndvi_composites_total": len(ndvi), "lst_composites_total": len(lst),
        "ndvi_composites_with_valid_pixels": int(ndvi.ndvi_mean.notna().sum()),
        "lst_day_composites_with_valid_pixels": int(lst.lst_day_mean_c.notna().sum()),
        "lst_night_composites_with_valid_pixels": int(lst.lst_night_mean_c.notna().sum()),
    }
    return days, info


def save(frame, destination):
    frame = frame.copy()
    for col in frame.select_dtypes(include="datetime64[ns]").columns:
        frame[col] = frame[col].dt.strftime("%Y-%m-%d")
    frame.to_csv(destination, index=False, float_format="%.5f")


def run(input_dir, output_dir):
    era_path, viirs_path, modis_path = archives(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print("[1/4] ERA5-Land")
    era = read_era5(era_path)
    print("[2/4] VIIRS Active Fire")
    viirs = read_viirs(viirs_path)
    print("[3/4] MODIS NDVI/LST")
    modis, modis_info = read_modis(modis_path)
    print("[4/4] Aliniere zilnică și raport")
    combined = era.merge(viirs, on="date", validate="one_to_one")
    combined = combined.merge(modis, on="date", validate="one_to_one")
    if len(combined) != len(DAYS) or combined.date.duplicated().any():
        raise ValueError("Număr invalid de zile în tabelul aliniat")
    for name, frame in (
        ("era5_daily.csv", era), ("viirs_daily.csv", viirs),
        ("modis_daily.csv", modis), ("dataset_aliniat_zilnic.csv", combined)):
        save(frame, output_dir / name)
    selected = {
        "ERA5-Land": ["temperature_mean_c", "precipitation_total_mm", "soil_moisture_mean_m3m3"],
        "VIIRS Active Fire": ["viirs_detection_count", "viirs_has_detection"],
        "MODIS NDVI": ["ndvi_mean"],
        "MODIS LST": ["lst_day_mean_c", "lst_night_mean_c"],
    }
    coverage = []
    for source, columns in selected.items():
        for col in columns:
            n = int(combined[col].notna().sum())
            coverage.append(dict(source=source, column=col, days_with_value=n,
                                 days_total=len(DAYS), coverage_pct=round(100*n/len(DAYS), 2)))
    report = pd.DataFrame(coverage)
    save(report, output_dir / "raport_acoperire.csv")
    info = {
        "study_area": "Bejís–Villanueva de Viver, Castellón, Spain",
        "bbox": BBOX,
        "period": {"start": str(START.date()), "end": str(END.date()), "days": len(DAYS)},
        "era5_hours": int(era.era5_hourly_observations.sum()), "era5_grid_points": 30,
        "viirs_detections": int(viirs.viirs_detection_count.sum()),
        "viirs_days_with_detection": int(viirs.viirs_has_detection.sum()),
        "modis": modis_info,
        "method": "Mean over region; daily VIIRS observations; 8/16-day composites only after end of window",
        "note": "No VIIRS detection is not proof that no fire occurred."
    }
    (output_dir / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Raport de acoperire – MEDE U11 CP1", "",
        f"- Unitate: zi × regiune, 2020–2024 ({len(DAYS)} zile).",
        f"- ERA5: {info['era5_hours']} ore în 30 puncte.",
        f"- VIIRS: {info['viirs_detections']} detecții în {info['viirs_days_with_detection']} zile.",
        f"- MODIS: {modis_info['ndvi_composites_total']} NDVI, {modis_info['lst_composites_total']} LST.",
        "- Zero detecții VIIRS nu înseamnă absența sigură a incendiului.", "",
        "| Sursa | Variabila | Zile valide | Acoperire |",
        "|---|---|---:|---:|"
    ]
    for row in report.itertuples(index=False):
        lines.append(f"| {row.source} | {row.column} | {row.days_with_value}/{row.days_total} | {row.coverage_pct}% |")
    lines += ["", "## Limitări", "",
              "- Medii calculate în întreaga casetă, fără ponderare pe suprafața pixelilor.",
              "- Filtrare MODIS după QA; valori propagate doar după sfârșitul ferestrei de observație.",
              "- Acest pipeline încarcă și aliniază datele; nu evaluează încă un model predictiv."]
    (output_dir / "raport_acoperire.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {len(DAYS)} zile, {info['viirs_detections']} detecții VIIRS")
    return info


def main():
    ap = argparse.ArgumentParser(description="MEDE U11: ingestia ERA5/VIIRS/MODIS")
    ap.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    ap.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = ap.parse_args()
    run(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
