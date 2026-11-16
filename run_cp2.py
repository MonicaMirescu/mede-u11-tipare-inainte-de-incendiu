"""MEDE U11: reproducere CP2 finală, 7 CSV și 4 PNG, fără schimbări metodologice."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import matplotlib
import numpy as np
import pandas as pd

import run_pipeline as ingestion
from cp2_analysis import (FEATURES, build_matrix, check_calendar, cross_source_correlations,
                          parse_dates, source_coverage, spearman_pairwise)
from cp2_delivery import (ARTIFACTS, CONTROL_FILES, SOURCE_FILES, content_hash,
                          predictor_statistics, variable_coverage, variable_dictionary)
from validate_outputs import validate as validate_corrected


def run(input_dir, output_dir, metadata_path=ingestion.METADATA):
    root = Path(output_dir).resolve()
    project = Path(__file__).resolve().parent
    input_dir = Path(input_dir).resolve()
    if root == input_dir or root.is_relative_to(input_dir) or input_dir.is_relative_to(root):
        raise ValueError("Directoarele de intrare/ieșire trebuie să fie separate")
    root.mkdir(parents=True, exist_ok=True)
    allowed = set(ARTIFACTS) | set(CONTROL_FILES)
    extra = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - allowed
    if extra:
        raise ValueError(f"Directorul conține rezultate din altă versiune; folosiți un director separat: {sorted(extra)}")
    print("[1/5] Teste automate", flush=True)
    command = [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", str(project / "tests"), "-v"]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, encoding="utf-8", timeout=180)
    log = result.stdout + result.stderr
    if result.returncode:
        print(log)
        raise RuntimeError("Testele au eșuat")
    test_count = int(re.search(r"Ran (\d+) tests?", log)[1])
    print(f"{test_count} teste: OK", flush=True)
    print("[2/5] Ingestie reală și verificări științifice; intermediari temporari", flush=True)
    with tempfile.TemporaryDirectory(prefix="mede_cp2_ingestion_") as temporary:
        source = Path(temporary)
        source_info = ingestion.run(input_dir, source, metadata_path)
        full = parse_dates(validate_corrected(source))
        filtered = pd.read_csv(source / "viirs_daily_nominal_high.csv", parse_dates=["date"])
        filtered = filtered.rename(columns={n: n.replace("viirs_", "viirs_nominal_high_", 1) for n in filtered if n != "date"})
        full = full.merge(filtered, on="date", validate="one_to_one")
    # QA alternativ este verificat în ingestie; livrabilul păstrează numai politica strictă.
    full = full.drop(columns=[n for n in full if n.startswith("ndvi_justified_")])
    check_calendar(full)
    print("[3/5] X principal și cele 7 CSV-uri", flush=True)
    matrix = build_matrix(full)
    rho, counts = spearman_pairwise(matrix[list(FEATURES)])
    cross = cross_source_correlations(rho, counts)
    tables = {
        "matrice_X.csv": matrix, "tabel_aliniat_complet.csv": full,
        "dictionar_variabile.csv": variable_dictionary({"X_principal": matrix, "aliniat_complet": full}),
        "statistici_predictori.csv": predictor_statistics(matrix),
        "corelatii_ERA5_MODIS.csv": cross, "acoperire_surse.csv": source_coverage(matrix),
        "acoperire_variabile.csv": variable_coverage(matrix),
    }
    for name, frame in tables.items():
        ingestion.save(frame, root / name)
    print("[4/5] Cele 4 figuri din CSV-urile validate", flush=True)
    with tempfile.TemporaryDirectory(prefix="mede_cp2_matplotlib_") as config:
        os.environ["MPLCONFIGDIR"] = config
        from cp2_figures import generate_figures
        generate_figures(parse_dates(pd.read_csv(root / "matrice_X.csv")),
                         pd.read_csv(root / "corelatii_ERA5_MODIS.csv"), root / "grafice")
    manifest = {
        "delivery": "CP2 final: 7 CSV, 4 PNG; fără analize auxiliare publicate",
        "period": source_info["period"], "bbox": source_info["bbox"], "era5_lag_days": 1,
        "ndvi_main_policy": "strict", "matrix_csv_shape": list(matrix.shape),
        "physical_predictor_shape": [len(matrix), len(FEATURES)], "predictors": list(FEATURES),
        "inputs": source_info["inputs"], "ingestion_audit": source_info,
        "ingestion_validation": "passed; inclusiv QA compozite strict/justified/legacy, înaintea eliminării intermediarilor",
        "source_sha256": {n: content_hash(project / n) for n in SOURCE_FILES},
        "hash_convention": "SHA-256; PNG exact; text UTF-8 CRLF→LF",
        "versions": {"python": sys.version, "numpy": np.__version__, "pandas": pd.__version__, "matplotlib": matplotlib.__version__},
        "numeric_conventions": {"correlation": "Spearman; pairwise complete; average ranks", "std_ddof": 1,
                                "quantile_interpolation": "linear", "imputation": "none", "csv_float_format": "%.12g"},
        "tests": {"tests_run": test_count, "exit_code": result.returncode},
        "generated_files": sorted((*ARTIFACTS, *CONTROL_FILES)),
        "output_sha256": {n: content_hash(root / n) for n in ARTIFACTS},
    }
    (root / "manifest_CP2.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[5/5] Validare, identitate cu referința și inventar final", flush=True)
    from validate_cp2 import validate
    validation = validate(root)
    validation["source_tests_passed"] = test_count
    (root / "validare_CP2.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from prepare_publication import write_manifest, verify
    write_manifest(root, project)
    print(json.dumps(verify(root, project), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/CP2"))
    parser.add_argument("--modis-metadata", type=Path, default=ingestion.METADATA)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir, args.modis_metadata)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
