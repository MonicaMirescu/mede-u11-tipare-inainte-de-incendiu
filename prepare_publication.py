"""Inventariază și verifică exclusiv livrabilul final CP2 (7 CSV și 4 PNG)."""
import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess

from cp2_delivery import ARTIFACTS, CONTROL_FILES, SOURCE_FILES, content_hash
from validate_cp2 import validate

MANIFEST = "publicatie_CP2.json"


def write_manifest(root, project):
    validation = validate(root)
    names = sorted(set(ARTIFACTS) | set(CONTROL_FILES) - {MANIFEST})
    manifest = {
        "purpose": "Livrabil academic CP2 final, fără rezultate auxiliare",
        "hash_convention": "SHA-256; PNG exact; text UTF-8 CRLF→LF",
        "published_artifacts": sorted((*ARTIFACTS, *CONTROL_FILES)),
        "artifact_sha256": {n: content_hash(root / n) for n in names},
        "validation": validation,
        "raw_data_policy": "ZIP/NetCDF și date/raw originale excluse; numai data/raw/INSTRUCTIUNI.txt este versionat",
        "reproduction": "python -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2",
    }
    (root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify(root, project, check_index=False):
    validation = validate(root)
    inventory = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    expected = set(ARTIFACTS) | set(CONTROL_FILES)
    if set(inventory["published_artifacts"]) != expected or set(inventory["artifact_sha256"]) != expected - {MANIFEST}:
        raise ValueError("Inventar publicare inconsistent")
    for name, digest in inventory["artifact_sha256"].items():
        if content_hash(root / name) != digest:
            raise ValueError(f"Artefact modificat: {name}")
    report = json.loads((root / "validare_CP2.json").read_text(encoding="utf-8"))
    if report["status"] != "passed" or not report["csv_identical_to_validated_selection"]:
        raise ValueError("Validarea finală nu a trecut")
    if check_index:
        tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=project).decode("utf-8").split("\0")) - {""}
        prefix = root.relative_to(project).as_posix() + "/"
        required = set(SOURCE_FILES) | {"data/raw/INSTRUCTIUNI.txt"} | {prefix + n for n in expected}
        forbidden = [n for n in tracked if PurePosixPath(n).suffix.lower() in {".zip", ".nc", ".pyc", ".tmp", ".temp", ".bak"}]
        if forbidden or tracked != required:
            raise ValueError(f"Selecție Git incorectă; lipsesc={sorted(required-tracked)}; suplimentare={sorted(tracked-required)}; interzise={forbidden}")
    return {**validation, "published_artifacts": len(expected), "git_index_checked": check_index}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/CP2"))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check-index", action="store_true")
    args = parser.parse_args()
    root = args.output_dir.resolve()
    project = Path(__file__).resolve().parent
    if args.write:
        write_manifest(root, project)
    print(json.dumps(verify(root, project, args.check_index), ensure_ascii=False))


if __name__ == "__main__":
    main()
