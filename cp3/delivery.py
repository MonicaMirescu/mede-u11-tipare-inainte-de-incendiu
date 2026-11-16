"""Inventare explicite pentru surse, rezultate și selecția comună CP2/CP3."""
from pathlib import Path

from cp2_delivery import SOURCE_FILES as CP2_SOURCE_FILES
from .config import PROJECT, TABLES, FIGURES
from .io import require

ARTIFACTS = set(TABLES) | {"experimente_CP3.json", "proiectii_CP3.npz"} | {"grafice/"+n for n in FIGURES}
CONTROL_FILES = {"manifest_CP3.json", "validare_CP3.json"}


def source_files(noaa_dir):
    files = [*PROJECT.glob("cp3/*.py"), *PROJECT.glob("tests_cp3/*.py"),
             *(PROJECT/n for n in ["run_cp3.py", "validate_cp3.py", "requirements_CP3.txt"]),
             *Path(noaa_dir).glob("*.csv"), Path(noaa_dir)/"provenienta_NOAA.json"]
    return sorted({p.relative_to(PROJECT).as_posix() for p in files})


def protected_cp2_files(cp2_dir):
    return set(CP2_SOURCE_FILES) | {"data/raw/INSTRUCTIUNI.txt"} | {
        p.relative_to(PROJECT).as_posix() for p in Path(cp2_dir).rglob("*") if p.is_file()}


def publication_files(root, noaa_dir):
    prefix = Path(root).relative_to(PROJECT).as_posix() + "/"
    return set(source_files(noaa_dir)) | {prefix+n for n in ARTIFACTS | CONTROL_FILES}


def verify_manifest_inventory(manifest, root, cp2_dir, noaa_dir):
    require(set(manifest["source_sha256_lf"]) == set(source_files(noaa_dir)), "Inventar surse CP3 incomplet")
    require(set(manifest["cp2_sha256_lf"]) == protected_cp2_files(cp2_dir), "Inventar protecție CP2 incomplet")
    require(set(manifest["output_sha256"]) == ARTIFACTS, "Inventar hash-uri rezultate CP3 incomplet")
    require(set(manifest["generated_files"]) == ARTIFACTS | CONTROL_FILES, "Inventar final inconsistent")
    expected = publication_files(root, noaa_dir)
    require(set(manifest["proposed_github_files"]) == expected, "Selecție CP3 inconsistentă")
    combined = expected | protected_cp2_files(cp2_dir)
    require({n for n in combined if Path(n).suffix.lower() == ".md"} == {"README.md"},
            "Documentația publicată trebuie centralizată în README.md")
    return combined
