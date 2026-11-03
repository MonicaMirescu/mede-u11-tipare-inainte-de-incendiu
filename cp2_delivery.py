"""Contractul livrabilului CP2: selecție, proveniență și inventar."""
import hashlib
from pathlib import Path

from cp2_analysis import FEATURES, descriptive_statistics, make_dictionary

CSV_FILES = (
    "matrice_X.csv", "tabel_aliniat_complet.csv", "dictionar_variabile.csv",
    "statistici_predictori.csv", "corelatii_ERA5_MODIS.csv",
    "acoperire_surse.csv", "acoperire_variabile.csv",
)
PNG_FILES = (
    "aliniere_surse.png", "preview_matrice_X.png",
    "distributii_selectate.png", "corelatii_intre_surse.png",
)
ARTIFACTS = (*CSV_FILES, *(f"grafice/{n}" for n in PNG_FILES), "metodologie_CP2.md")
CONTROL_FILES = ("manifest_CP2.json", "validare_CP2.json", "publicatie_CP2.json")
SOURCE_FILES = (
    ".gitignore", "README.md", "docs/CP2_CERINTE.md",
    "requirements.txt", "run_pipeline.py", "pipeline_methods.py", "validate_outputs.py",
    "cp2_analysis.py", "cp2_delivery.py", "cp2_figures.py", "run_cp2.py",
    "validate_cp2.py", "prepare_publication.py", "tests/test_cp2.py",
    "tests/test_pipeline.py", "tests/test_cp2_final.py", "metadata/README.md",
    "metadata/modis_composite_periods.json", "metadata/cp2_validated_reference.json",
)


def content_hash(path):
    """SHA-256 portabil Git: normalizează numai CRLF→LF în fișierele text."""
    path = Path(path)
    data = path.read_bytes()
    if path.suffix.lower() != ".png":
        data = data.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def predictor_statistics(matrix):
    return descriptive_statistics({"X_principal": matrix[list(FEATURES)]})


def variable_dictionary(tables):
    # CSV nu păstrează tipuri binare int32/int64; păstrăm definițiile științifice.
    return make_dictionary(tables).drop(columns="dtype")


def variable_coverage(matrix):
    stats = descriptive_statistics({"X_principal": matrix})
    out = stats[["table", "variable", "source", "role", "unit", "n_total",
                 "n_valid", "n_missing", "missing_pct"]].copy()
    out["imputed_days"] = 0
    prefixes = {"ndvi_mean": "ndvi", "lst_day_mean_c": "lst_day",
                "lst_night_mean_c": "lst_night"}
    out["carried_days_after_first_assignment"] = [
        int(matrix[f"{prefixes[n]}_is_carried"].sum()) if n in prefixes else 0
        for n in out.variable
    ]
    return out
