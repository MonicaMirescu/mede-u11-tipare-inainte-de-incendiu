"""Verificări rapide pentru tabelul zilnic CP1."""
import argparse
from pathlib import Path
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    path = parser.parse_args().processed_dir / "dataset_aliniat_zilnic.csv"
    df = pd.read_csv(path, parse_dates=["date", "ndvi_available_from", "lst_available_from"])
    days = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    assert len(df) == len(days) == 1827
    assert not df.date.duplicated().any()
    assert df.date.reset_index(drop=True).equals(pd.Series(days))
    assert (df.era5_hourly_observations == 24).all()
    for col in ["temperature_mean_c", "precipitation_total_mm", "soil_moisture_mean_m3m3"]:
        assert df[col].notna().all(), f"ERA5 missing: {col}"
    assert (df.precipitation_total_mm >= 0).all()
    assert (df.viirs_detection_count >= 0).all()
    assert int(df.viirs_detection_count.sum()) == 1249
    assert int(df.viirs_has_detection.sum()) == 24
    assert (df.viirs_has_detection == (df.viirs_detection_count > 0).astype(int)).all()
    assert df.ndvi_mean.dropna().between(-0.2, 1.0).all()
    assert df.lst_day_mean_c.dropna().between(-73.15, 86.85).all()
    assert df.lst_night_mean_c.dropna().between(-73.15, 86.85).all()
    for col in ["ndvi_available_from", "lst_available_from"]:
        valid = df.loc[df[col].notna()]
        assert (valid[col] <= valid.date).all(), f"Compozit din viitor: {col}"
    print("TESTE TRECUTE: 1827 zile, ERA5 complet, 1249 VIIRS în 24 zile; MODIS QC/aliniere verificate")


if __name__ == "__main__":
    main()
