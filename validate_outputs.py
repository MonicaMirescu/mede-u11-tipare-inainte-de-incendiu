"""Validări ale rezultatelor corectate; testele pe surse sunt separate."""
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from run_pipeline import DAYS


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(path):
    path = Path(path)
    df = pd.read_csv(path / "dataset_aliniat_zilnic.csv", parse_dates=["date"])
    require(df.date.equals(pd.Series(DAYS, name="date")), "Calendar zilnic incorect")
    require((df.era5_hourly_observations == 24).all(), "Ore ERA5 instantanee incomplete")
    for prefix, unit in [("precipitation", "mm"), ("solar_radiation", "mjm2")]:
        complete = df[f"{prefix}_complete"].eq(1)
        count, total, partial = (df[f"{prefix}_{name}"] for name in ["interval_hours", f"total_{unit}", f"partial_{unit}"])
        require(count.between(0, 24).all(), f"Număr intervale invalid {prefix}")
        require(complete.equals(count.eq(24)), f"Flag completitudine incorect {prefix}")
        require(total.notna().equals(complete), f"Total incomplet prezentat drept complet {prefix}")
        require(np.allclose(total[complete], partial[complete]), f"Total/sumă parțială diferite {prefix}")
        require((partial.dropna() >= 0).all(), f"Valori negative {prefix}")
    require(df.relative_humidity_mean_pct.dropna().between(0, 100).all(), "RH în afara intervalului")
    for label, span, values in [("ndvi", 16, {"ndvi_mean":"ndvi", "ndvi_justified_mean":"ndvi_justified"}),
                                 ("lst", 8, {"lst_day_mean_c":"lst_day", "lst_night_mean_c":"lst_night"})]:
        start = pd.to_datetime(df[f"{label}_composite_start"])
        end = pd.to_datetime(df[f"{label}_composite_end_exclusive"])
        available = pd.to_datetime(df[f"{label}_available_from"])
        present = end.notna()
        require((end-start).dt.days[present].between(1, span).all(), "Durată compozit invalidă")
        require(end.equals(available), "Data permisă nu coincide cu sfârșitul ferestrei")
        require((end[present] <= df.date[present]).all(), "Compozit cu observații viitoare")
        for value, prefix in values.items():
            valid = df[value].notna()
            age, carry = df[f"{prefix}_age_days"], df[f"{prefix}_carry_days"]
            count, pct = df[f"{prefix}_valid_pixel_count"], df[f"{prefix}_valid_pixels_pct"]
            require(age.notna().equals(valid), f"Vechime atribuită unei valori lipsă: {prefix}")
            require(np.allclose(age[valid], (df.date-end).dt.days[valid]+1), f"Vechime incorectă {prefix}")
            require(np.allclose(carry[valid], age[valid]-1), f"Propagare incorectă {prefix}")
            require(carry[valid].between(0, span*2).all(), "Propagare peste plafonul documentat")
            require(df[f"{prefix}_is_carried"].eq((valid & carry.gt(0)).astype(int)).all(), "Indicator propagare invalid")
            require(pct.dropna().between(0, 100).all(), "Procent pixeli invalid")
            require((count[valid] > 0).all(), "Medie fără pixeli valizi")
            require(np.allclose(pct[present], 100*count[present]/df[f"{label}_total_pixels"][present]), "Procent diferit de număr pixeli")
            low, high = (-.2, 1) if label == "ndvi" else (-73.15, 86.85)
            require(df[value].dropna().between(low, high).all(), "Valoare MODIS invalidă")
    present = df.ndvi_valid_pixel_count.notna()
    require(df.ndvi_valid_pixel_count[present].le(df.ndvi_justified_valid_pixel_count[present]).all(), "QA strict nu este submulțime")
    viirs = pd.read_csv(path / "viirs_daily_nominal_high.csv")
    require(viirs.date.equals(df.date.dt.strftime("%Y-%m-%d")), "Calendar VIIRS filtrat diferit")
    require(df.viirs_detection_count.eq(viirs.viirs_detection_count + df.viirs_low_confidence_count).all(), "Separare confidence incorectă")
    for frame in [df, viirs]:
        require(frame.viirs_detection_count.ge(0).all(), "Număr negativ de detecții")
        require(frame.viirs_has_detection.eq(frame.viirs_detection_count.gt(0).astype(int)).all(), "Flag VIIRS incorect")
        require(frame.loc[frame.viirs_detection_count.eq(0), "viirs_frp_max_mw"].isna().all(), "FRP maxim inventat fără detecții")
    qa = pd.read_csv(path / "ndvi_qa_comparison.csv")
    counts = qa.pivot(index="composite_start", columns="variant", values="valid_pixel_count")
    require((counts.strict <= counts.justified).all() and (counts.justified <= counts.legacy).all(), "Variante QA inconsistente")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    df = validate(parser.parse_args().processed_dir)
    print(f"VALIDARI TRECUTE: {len(df)} zile; intervale/completitudine ERA5, ferestre/vechime MODIS, variante QA si VIIRS. Testele pe surse sunt separate.")


if __name__ == "__main__":
    main()
