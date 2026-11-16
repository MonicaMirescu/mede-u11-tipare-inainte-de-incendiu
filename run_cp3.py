"""Reproduce CP3 din CP2 validat și snapshoturile NOAA, fără modificarea CP2."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent
for variable in ["NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ[variable] = "1"
runtime = PROJECT / ".local_cp2/cp3_runtime"
runtime.mkdir(parents=True, exist_ok=True)
os.environ["NUMBA_CACHE_DIR"] = str(runtime / "numba")
os.environ["MPLCONFIGDIR"] = str(runtime / "matplotlib")

from cp3.config import BASE_COMMIT, TABLES, FIGURES
from cp3.data import load_cp2, build_matrices, coverage_table, relation_table
from cp3.experiment import execute_or_reuse
from cp3.figures import generate_figures
from cp3.io import sha256, save_csv, save_json, require
from cp3.noaa import load_observations
from cp3.report import scientific_summary
from cp3.delivery import ARTIFACTS, CONTROL_FILES, source_files, protected_cp2_files
from cp3.validation import validate


def run_tests():
    counts = {}
    for label, directory in [("cp2", "tests"), ("cp3", "tests_cp3")]:
        command = [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", directory, "-v"]
        result = subprocess.run(command, cwd=PROJECT, capture_output=True, encoding="utf-8", timeout=300)
        log = result.stdout + result.stderr
        if result.returncode:
            print(log, flush=True)
            raise RuntimeError(f"Testele {label} au eșuat")
        count = int(re.search(r"Ran (\d+) tests?", log)[1])
        counts[label] = {"tests_run": count, "status": "passed", "command": f"python -X utf8 -B -m unittest discover -s {directory} -v"}
        print(f"{label}: {count} teste trecute", flush=True)
    return counts


def run(cp2_dir, noaa_dir, output_dir, reuse_experiments=False):
    cp2_dir, noaa_dir, root = [Path(p).resolve() for p in [cp2_dir, noaa_dir, output_dir]]
    require(root.is_relative_to(PROJECT), "Ieșirea CP3 trebuie să fie în proiect")
    for protected in [cp2_dir, noaa_dir, PROJECT/"data/raw"]:
        require(not root.is_relative_to(protected) and not protected.is_relative_to(root), "Ieșirea se suprapune peste date protejate")
    root.mkdir(parents=True, exist_ok=True)
    artifacts = ARTIFACTS
    expected = artifacts | CONTROL_FILES
    found = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(found <= expected, f"Fișiere suplimentare în directorul de ieșire: {sorted(found-expected)}")
    protected_files = protected_cp2_files(cp2_dir)
    before = {n: sha256(PROJECT/n) for n in sorted(protected_files)}
    print("[1/6] Teste și verificarea CP2", flush=True)
    tests = run_tests()
    from validate_cp2 import validate as validate_original_cp2
    validate_original_cp2(cp2_dir)
    print("[2/6] Snapshoturi NOAA și matrici 1/7 zile", flush=True)
    noaa, provenance = load_observations(noaa_dir)
    matrices = build_matrices(load_cp2(cp2_dir/"matrice_X.csv"), noaa)
    for window, name in [("1zi", TABLES[0]), ("7zile", TABLES[1])]:
        save_csv(matrices[window], root/name)
    save_csv(coverage_table(matrices), root/TABLES[2])
    relations = relation_table(matrices["1zi"])
    save_csv(relations, root/TABLES[5])
    print("[3/6] PCA/UMAP și stabilitate pe aceleași zile", flush=True)
    results, stability, records, arrays = execute_or_reuse(matrices, root, reuse=reuse_experiments)
    print("[4/6] Cele patru figuri sintetice", flush=True)
    generate_figures(root, results, stability, relations, records, arrays)
    print("[5/6] Sinteză numerică și proveniență", flush=True)
    summary = scientific_summary(stability, relations)
    after = {n: sha256(PROJECT/n) for n in sorted(protected_files)}
    require(before == after, "Fișierele CP2 au fost modificate în timpul rulării")
    sources = source_files(noaa_dir)
    prefix = root.relative_to(PROJECT).as_posix() + "/"
    versions = {n: importlib.metadata.version(n) for n in ["numpy", "pandas", "scipy", "scikit-learn", "umap-learn", "pynndescent", "numba", "llvmlite", "matplotlib", "h5py", "threadpoolctl", "joblib"]}
    manifest = {"study": "MEDE U11 — Tipare înainte de incendiu", "base_commit": BASE_COMMIT,
        "unit": "ziua, într-o singură regiune fixă; o singură serie temporală multivariată",
        "bbox": {"lat": [39.7, 40.2], "lon": [-1.0, -0.4]}, "tests": tests,
        "python": sys.version, "versions": versions, "experiment_reused_by_exact_signature": reuse_experiments,
        "cp2_exact_bytes_unchanged_during_run": True,
        "cp2_sha256_lf": {n: sha256(PROJECT/n, text=not n.endswith(".png")) for n in sorted(protected_files)},
        "source_sha256_lf": {n: sha256(PROJECT/n, text=True) for n in sources},
        "noaa_snapshot_sha256_lf": {n: v["snapshot_sha256_lf"] for n, v in provenance["indices"].items()},
        "hash_convention": "SHA-256; PNG/NPZ bytes exacte; fișiere text UTF-8 CRLF→LF; protejare CP2 runtime pe bytes exacte",
        "generated_files": sorted(expected), "summary": summary,
        "output_sha256": {n: sha256(root/n, text=Path(n).suffix not in {".png", ".npz"}) for n in sorted(artifacts)},
        "proposed_github_files": sorted([*sources, *(prefix+n for n in expected)]),
        "publication_status": "local review only; no push, PR or merge"}
    save_json(manifest, root/"manifest_CP3.json")
    print("[6/6] Validarea fișierelor și calculelor reale", flush=True)
    validation = validate(root, cp2_dir, noaa_dir)
    save_json(validation, root/"validare_CP3.json")
    print(json.dumps(validation, ensure_ascii=False), flush=True)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cp2-dir", type=Path, default=PROJECT/"outputs/CP2")
    parser.add_argument("--noaa-dir", type=Path, default=PROJECT/"data/CP3_NOAA")
    parser.add_argument("--output-dir", type=Path, default=PROJECT/"outputs/CP3")
    parser.add_argument("--reuse-experiments", action="store_true", help="Reutilizare numai dacă amprenta datelor, codului experimental și versiunilor este identică")
    args = parser.parse_args()
    run(args.cp2_dir, args.noaa_dir, args.output_dir, args.reuse_experiments)


if __name__ == "__main__":
    main()
