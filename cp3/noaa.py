"""Snapshoturi NOAA CPC CDAS: o singură versiune observațională per indice."""
import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import urllib.request

import numpy as np
import pandas as pd

from .io import read_csv, require, save_json, sha256

URLS = {
    "nao": "https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv",
    "ao": "https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv",
}
DOCS = {
    "methodology": "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/history/method.shtml",
    "nao": "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.shtml",
    "ao": "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.shtml",
    "service_change": "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/teleconnections/scn/pdf/scn-changes-to-cpc-teleconnections-products.pdf",
}
START = pd.Timestamp("2019-12-25")
END = pd.Timestamp("2024-12-30")
SNAPSHOTS = {n: f"{n}_cdas_20191225_20241230.csv" for n in URLS}
# Coduri de lipsă recunoscute explicit; nu sunt observații sau imputări.
SENTINELS = [-999., -9999., 9999., -99999., 99999.]


def parse_noaa(path, index):
    frame = read_csv(path)
    column = f"{index}_index_cdas"
    require(list(frame) == ["year", "month", "day", column], "Antet NOAA incompatibil: se acceptă numai istoricul CDAS observațional")
    for name in ["year", "month", "day"]:
        require(pd.api.types.is_numeric_dtype(frame[name]) and frame[name].notna().all()
                and frame[name].eq(np.floor(frame[name])).all(), f"Dată NOAA invalidă: {name}")
    dates = pd.to_datetime(frame[["year", "month", "day"]], errors="raise")
    require(not dates.duplicated().any(), "Date NOAA duplicate")
    require(dates.is_monotonic_increasing, "Date NOAA neordonate")
    values = pd.to_numeric(frame[column], errors="raise")
    special = values.isin(SENTINELS) | values.abs().ge(1e10)
    require(not np.isinf(values).any(), "Indice NOAA infinit")
    values = values.mask(special)
    audit = {"rows": len(frame), "start": dates.min().strftime("%Y-%m-%d"),
             "end": dates.max().strftime("%Y-%m-%d"), "header": list(frame),
             "duplicate_dates": 0, "n_special_codes": int(special.sum()),
             "n_missing": int(values.isna().sum()), "min": float(values.min()), "max": float(values.max())}
    return pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name=f"{index}_index"), audit


def prepare_snapshots(destination, manual=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    provenance_path = destination / "provenienta_NOAA.json"
    if provenance_path.exists():
        return load_observations(destination)[1]
    import hashlib
    provenance = {"provider": "NOAA Climate Prediction Center", "product": "daily CDAS historical observed indices (legacy norm.daily; not CORE/GFS/GEFS)",
                  "requested_observation_period": [str(START.date()), str(END.date())], "documentation": DOCS,
                  "version_policy": "Ambele snapshoturi provin integral din produsele norm.daily.*.cdas, fără amestec cu noua familie CORE.",
                  "methods": {"nao": "RPCA, anomalii geopotențial 500 hPa 20–90N; climatologie 1950–2000 și tipare lunare interpolate; indice adimensional normalizat",
                              "ao": "Proiecție anomalii geopotențial 1000 hPa pe primul EOF; referință și normalizare 1979–2000; indice adimensional"},
                  "missing_codes_recognized": SENTINELS + ["abs(value)>=1e10", "empty/NaN"],
                  "operational_caution": "D−1 exprimă data observației, nu garantează disponibilitatea operațională istorică.", "indices": {}}
    # Validăm ambii indici înainte de scrierea unui inventar complet.
    for index, url in URLS.items():
        if manual and index in manual:
            data = Path(manual[index]).read_bytes()
            mode, headers = "manual_import", {}
        else:
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    require(response.geturl().startswith("https://ftp.cpc.ncep.noaa.gov/"), "Redirect NOAA neoficial")
                    data = response.read()
                    headers = {n: response.headers.get(n) for n in ["Last-Modified", "ETag", "Content-Type"]}
                mode = "download_https_official"
            except Exception as exc:
                raise RuntimeError(f"Acces NOAA blocat/eșuat pentru {index}: {exc}. Folosiți --nao-csv și --ao-csv cu CSV-urile CDAS oficiale; nu se generează date sintetice.") from exc
        # Textul snapshotului păstrează exact câmpurile originale, numai subsetul de date este selectat.
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
        header = next(reader)
        expected = ["year", "month", "day", f"{index}_index_cdas"]
        require(header == expected, f"Produs NOAA neașteptat la {url}: {header}")
        rows = list(reader)
        # Audităm și fișierul complet descărcat în memorie, fără a publica o copie redundantă.
        source_frame = pd.DataFrame(rows, columns=header)
        require(source_frame.shape[1] == 4, "Format NOAA invalid")
        full_buffer = io.StringIO(data.decode("utf-8-sig"))
        full_series, full_audit = parse_noaa(full_buffer, index)
        selected = [row for row in rows if START <= pd.Timestamp(year=int(row[0]), month=int(row[1]), day=int(row[2])) <= END]
        path = destination / SNAPSHOTS[index]
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(selected)
        series, audit = parse_noaa(path, index)
        require(series.index.equals(pd.date_range(START, END)), f"Lipsesc date calendaristice NOAA: {index}")
        provenance["indices"][index] = {"url": url, "resolved_url": url if mode == "download_https_official" else None, "mode": mode,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "source_sha256_bytes": hashlib.sha256(data).hexdigest(),
            "snapshot": path.name, "snapshot_sha256_lf": sha256(path, text=True),
            "source_audit": full_audit, "snapshot_audit": audit, "response_headers": headers}
    save_json(provenance, provenance_path)
    return provenance


def load_observations(directory):
    directory = Path(directory)
    provenance = json.loads((directory / "provenienta_NOAA.json").read_text(encoding="utf-8"))
    columns = []
    for index, url in URLS.items():
        info = provenance["indices"][index]
        require(info["url"] == url and info["snapshot"] == SNAPSHOTS[index], "Versiune NOAA amestecată sau sursă incompatibilă")
        path = directory / info["snapshot"]
        require(sha256(path, text=True) == info["snapshot_sha256_lf"], f"Snapshot NOAA modificat: {index}")
        values, audit = parse_noaa(path, index)
        require(audit == info["snapshot_audit"], "Audit NOAA diferit de proveniență")
        require(values.index.equals(pd.date_range(START, END)), "Calendarul NOAA nu acoperă intervalul necesar")
        columns.append(values)
    return pd.concat(columns, axis=1), provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/CP3_NOAA"))
    parser.add_argument("--nao-csv", type=Path)
    parser.add_argument("--ao-csv", type=Path)
    args = parser.parse_args()
    manual = {k: v for k, v in {"nao": args.nao_csv, "ao": args.ao_csv}.items() if v}
    prepare_snapshots(args.directory, manual=manual)
    observations, info = load_observations(args.directory)
    print(observations.describe().to_string())
    print(json.dumps({k: v["snapshot_audit"] for k, v in info["indices"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
