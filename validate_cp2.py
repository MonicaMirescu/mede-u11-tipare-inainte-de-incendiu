"""Verificare științifică a livrabilului final CP2, cu sau fără arhive locale."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from cp2_analysis import (FEATURES, ERA_FEATURES, build_matrix, check_calendar, parse_dates,
                          cross_source_correlations, source_coverage, spearman_pairwise)
from cp2_delivery import (ARTIFACTS, CONTROL_FILES, CSV_FILES, PNG_FILES, SOURCE_FILES,
                          content_hash, predictor_statistics, variable_coverage, variable_dictionary)
from validate_outputs import require, validate_frame


def compare_frames(actual, expected, label):
    require(list(actual.columns) == list(expected.columns) and len(actual) == len(expected), f"Schema diferită: {label}")
    for name in expected:
        if pd.api.types.is_numeric_dtype(expected[name]):
            require(np.allclose(actual[name], expected[name], equal_nan=True, rtol=2e-11, atol=1e-10),
                    f"Valori neconcordante: {label}/{name}")
        else:
            require(actual[name].fillna("").equals(expected[name].fillna("")), f"Date/texte diferite: {label}/{name}")


def validate(output_dir):
    root = Path(output_dir).resolve()
    project = Path(__file__).resolve().parent
    require({p.relative_to(root).as_posix() for p in root.rglob("*.csv")} == set(CSV_FILES), "Se cer exact cele 7 CSV-uri")
    require({p.relative_to(root / "grafice").as_posix() for p in (root / "grafice").rglob("*.png")} == set(PNG_FILES),
            "Se cer exact cele 4 PNG-uri")
    found = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(set(ARTIFACTS) <= found and found <= set(ARTIFACTS) | set(CONTROL_FILES), "Fișiere lipsă/suplimentare în livrabil")
    full = parse_dates(pd.read_csv(root / "tabel_aliniat_complet.csv"))
    matrix = parse_dates(pd.read_csv(root / "matrice_X.csv"))
    check_calendar(full)
    check_calendar(matrix)
    require(matrix.shape == (1827, 54) and len(FEATURES) == 12, "Dimensiuni X incorecte")
    require(not any(n.startswith("viirs_") or n.startswith("ndvi_justified_") for n in matrix), "VIIRS/sensibilitate în X")
    require(not any(n.startswith("ndvi_justified_") for n in full), "Sensibilitate NDVI în tabelul final")
    require(not np.isinf(matrix.select_dtypes(include="number").to_numpy()).any(), "Valori infinite în X")

    # Aceleași controale ale fluxurilor, QA strict, ferestrelor, vârstei și VIIRS;
    # verificările comparative QA pe compozite se execută la ingestia reală.
    filtered = full[[n for n in full if n.startswith("viirs_nominal_high_")]].rename(
        columns=lambda n: n.replace("viirs_nominal_high_", "viirs_", 1))
    filtered.insert(0, "date", full.date.dt.strftime("%Y-%m-%d"))
    validate_frame(full, filtered)
    compare_frames(matrix, build_matrix(full), "X față de surse")
    for name in FEATURES:
        require(matrix[f"{name}_missing"].eq(matrix[name].isna().astype(int)).all(), f"Flag lipsă greșit: {name}")
    require((matrix.era5_observation_date == matrix.date - pd.Timedelta(days=1)).all(), "ERA5 nu este D−1")
    lookup = full.set_index("date")
    for name in ERA_FEATURES:
        expected = lookup[name].reindex(matrix.date - pd.Timedelta(days=1)).to_numpy()
        require(np.allclose(matrix[name], expected, equal_nan=True, rtol=2e-11, atol=1e-10), f"Decalaj ERA5 incorect: {name}")

    statistics = pd.read_csv(root / "statistici_predictori.csv")
    compare_frames(statistics, predictor_statistics(matrix), "statistici")
    require(len(statistics) == 12 and set(statistics.variable) == set(FEATURES), "Statistici fără cei 12 predictori exclusiv")
    require((statistics.n_valid + statistics.n_missing == 1827).all(), "Bilanț observații greșit")
    dictionary = pd.read_csv(root / "dictionar_variabile.csv")
    compare_frames(dictionary, variable_dictionary({"X_principal": matrix, "aliniat_complet": full}), "dicționar")
    predictor_rows = dictionary[dictionary.table.eq("X_principal") & dictionary.role.eq("predictor")]
    require(len(predictor_rows) == 12 and set(predictor_rows.variable) == set(FEATURES), "Roluri predictor incorecte")

    # Recalculare pe perechi din X pentru verificare, cu definiția Spearman validată.
    # Fișierul și figura publică numai 9×3 perechi între surse.
    rho, counts = spearman_pairwise(matrix[list(FEATURES)])
    cross = pd.read_csv(root / "corelatii_ERA5_MODIS.csv")
    compare_frames(cross, cross_source_correlations(rho, counts), "Spearman între surse")
    require(len(cross) == 27 and not cross.duplicated(["era5_variable", "modis_variable"]).any(), "Perechi între surse lipsă/duplicate")
    require(cross.spearman_rho.dropna().between(-1, 1).all(), "ρ în afara intervalului")
    compare_frames(pd.read_csv(root / "acoperire_surse.csv"), source_coverage(matrix), "acoperire surse")
    compare_frames(pd.read_csv(root / "acoperire_variabile.csv"), variable_coverage(matrix), "acoperire variabile")

    for name in PNG_FILES:
        with Image.open(root / "grafice" / name) as picture:
            require(picture.format == "PNG" and min(picture.size) > 500, f"PNG invalid/prea mic: {name}")
            picture.verify()

    reference = json.loads((project / "metadata/cp2_validated_reference.json").read_text(encoding="utf-8"))
    require(set(reference["csv_sha256"]) == set(CSV_FILES), "Referință numerică incompletă")
    for name, digest in reference["csv_sha256"].items():
        require(content_hash(root / name) == digest, f"CSV diferit de selecția referinței validate: {name}")
    manifest = json.loads((root / "manifest_CP2.json").read_text(encoding="utf-8"))
    require(manifest["era5_lag_days"] == 1 and manifest["ndvi_main_policy"] == "strict", "Politică metodologică schimbată")
    require(manifest["inputs"] == reference["inputs"], "Arhive diferite de referința validată")
    require(manifest["predictors"] == list(FEATURES), "Inventar predictori greșit")
    require(set(manifest["generated_files"]) == set(ARTIFACTS) | set(CONTROL_FILES), "Inventar de livrare incorect")
    require(set(manifest["source_sha256"]) == set(SOURCE_FILES), "Inventar cod incomplet")
    require(set(manifest["output_sha256"]) == set(ARTIFACTS), "Inventar rezultate incomplet")
    for base, mapping in [(project, manifest["source_sha256"]), (root, manifest["output_sha256"])]:
        for name, digest in mapping.items():
            require(content_hash(base / name) == digest, f"Fișier schimbat de la generare: {name}")
    require(manifest["tests"]["exit_code"] == 0 and manifest["tests"]["tests_run"] >= 31, "Testele nu au trecut")
    require(manifest["ingestion_validation"].startswith("passed;"), "Lipsește verificarea ingestiei")
    return {"status": "passed", "days": len(matrix), "physical_predictors": len(FEATURES),
            "matrix_csv_columns": len(matrix.columns), "csv_files_verified": len(CSV_FILES),
            "png_files_verified": len(PNG_FILES), "descriptive_predictors": len(statistics),
            "cross_source_pairs": len(cross), "validated_reference": reference["validated_commit"],
            "csv_identical_to_validated_selection": True,
            "scientific_checks": ["fluxuri/completitudine ERA5", "QA strict și suport MODIS", "ferestre/vechime fără viitor",
                                  "VIIRS low separat", "D−1", "NaN explicit", "statistici", "Spearman/n pe perechi", "dicționar/acoperire"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/CP2"))
    print(json.dumps(validate(parser.parse_args().output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
