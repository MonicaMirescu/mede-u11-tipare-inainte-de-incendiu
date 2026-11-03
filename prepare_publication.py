"""Selectează și verifică pachetul GitHub fără a modifica rezultatele CP2.

--write necesită rularea integrală existentă și o validează înainte de selecție.
Verificarea implicită funcționează și într-o clonă fără arhivele brute/24 PNG.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

from PIL import Image
import pandas as pd

ESSENTIAL_FIGURES = {
    "grafice/X_principal_predictori_histograme_01.png",
    "grafice/X_principal_predictori_boxploturi_01.png",
    "grafice/corelatii_spearman.png",
    "grafice/numar_observatii_corelatii.png",
    "grafice/corelatii_sensibilitate_ndvi.png",
    "grafice/aliniere_surse.png",
    "grafice/preview_matrice_X.png",
}
MANIFEST = "publicatie_CP2.json"


def safe_path(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError(f"Cale nepermisă în inventar: {name}")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Cale în afara pachetului: {name}")
    return path


def content_hash(path):
    data = path.read_bytes()
    if path.suffix.lower() != ".png":
        # Git poate converti CRLF/LF. Nicio altă normalizare sau rotunjire.
        data = data.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def write_manifest(root, project):
    from validate_cp2 import validate
    validation = validate(root)
    original = json.loads((root/"manifest_CP2.json").read_text(encoding="utf-8"))
    published = sorted(n for n in original["generated_files"] if not n.endswith(".png") or n in ESSENTIAL_FIGURES)
    omitted = sorted(set(original["generated_files"])-set(published))
    sources = sorted(set(original["source_sha256"]) | {
        "prepare_publication.py", "README.md", ".gitignore", "AGENTS.md", "compare_pipeline.py",
        "docs/CP2_CERINTE.md", "docs/METODOLOGIE_CORECTII.md", "docs/PREDARE_GITHUB.md",
        "metadata/README.md", "metadata/modis_composite_periods.json"})
    manifest = {
        "purpose": "Selecție GitHub a rezultatelor validate; fără schimbări metodologice sau numerice",
        "hash_convention": "SHA-256; PNG exact bytes; text UTF-8 cu CRLF normalizat la LF pentru portabilitate Git",
        "full_run_validation": validation,
        "original_validation_report": json.loads((root/"validare_CP2.json").read_text(encoding="utf-8")),
        "published_artifacts": published,
        "omitted_artifacts": omitted,
        "omission_reason": "24 distribuții auxiliare/aliniate/de sensibilitate rămân locale și sunt regenerabile; 7 figuri esențiale publicate",
        "artifact_sha256": {n:content_hash(safe_path(root,n)) for n in published},
        "source_sha256": {n:content_hash(safe_path(project,n)) for n in sources},
        "raw_data_policy": "Nicio arhivă ZIP/NetCDF sau observație brută din data/raw nu este inclusă; numai INSTRUCTIUNI.txt",
        "full_reproduction": "python -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2",
        "published_verification": "python -X utf8 -B prepare_publication.py",
    }
    (root/MANIFEST).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def verify(root, project, check_index=False):
    manifest = json.loads((root/MANIFEST).read_text(encoding="utf-8"))
    original = json.loads((root/"manifest_CP2.json").read_text(encoding="utf-8"))
    published, omitted = set(manifest["published_artifacts"]), set(manifest["omitted_artifacts"])
    if published & omitted or published | omitted != set(original["generated_files"]):
        raise ValueError("Inventarul publicat nu corespunde rulării integrale")
    if {n for n in published if n.endswith(".png")} != ESSENTIAL_FIGURES:
        raise ValueError("Selecția celor 7 grafice este inconsistentă")
    if len(omitted)!=24 or any(not n.endswith(".png") for n in omitted):
        raise ValueError("S-au exclus și alte rezultate decât cele 24 PNG redundante")
    for base, mapping in [(root,manifest["artifact_sha256"]),(project,manifest["source_sha256"])]:
        for name, digest in mapping.items():
            path=safe_path(base,name)
            if not path.is_file() or content_hash(path)!=digest:
                raise ValueError(f"Fișier lipsă sau modificat față de selecția validată: {name}")
    if set(manifest["artifact_sha256"])!=published:
        raise ValueError("Lipsesc hash-uri de artefacte publicate")
    for name in ESSENTIAL_FIGURES:
        with Image.open(root/name) as picture:
            if min(picture.size)<500:raise ValueError(f"PNG prea mic: {name}")
            picture.verify()
    x=pd.read_csv(root/"matrice_X.csv",parse_dates=["date"])
    if x.shape!=(1827,54) or not x.date.equals(pd.Series(pd.date_range("2020-01-01","2024-12-31"),name="date")):
        raise ValueError("Dimensiuni sau calendar X incorecte")
    if any(n.startswith("viirs_") for n in x):raise ValueError("VIIRS în predictorii X")
    if check_index:
        tracked=set(subprocess.check_output(["git","ls-files","-z"],cwd=project).decode("utf-8").split("\0"))-{ "" }
        forbidden=[]
        for name in tracked:
            path=PurePosixPath(name)
            if ((name.startswith("data/raw/") and name!="data/raw/INSTRUCTIUNI.txt")
                or path.suffix.lower() in {".zip",".nc",".tmp",".temp",".bak",".pyc"}
                or any(part in {"__pycache__",".venv","venv",".pytest_cache"} for part in path.parts)):
                forbidden.append(name)
        if forbidden:raise ValueError(f"Fișiere nepermise în index: {forbidden}")
        prefix=root.relative_to(project).as_posix()+"/"
        required={prefix+n for n in published|{MANIFEST}} | set(manifest["source_sha256"])
        if required-tracked:raise ValueError(f"Fișiere publicate care lipsesc din index: {sorted(required-tracked)}")
        if any(prefix+n in tracked for n in omitted):raise ValueError("Un PNG exclus este în index")
    return {"status":"passed","published_cp2_artifacts":len(published)+1,
            "published_png":len(ESSENTIAL_FIGURES),"local_only_png":len(omitted),
            "x_shape":list(x.shape),"git_index_checked":check_index,
            "note":"Rezultate identice selecției validate, cu tolerarea exclusivă a conversiei CRLF/LF în text"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("outputs/CP2"))
    parser.add_argument("--write",action="store_true",help="Validează rularea integrală și scrie inventarul publicării")
    parser.add_argument("--check-index",action="store_true",help="Verifică și selecția din indexul Git")
    args=parser.parse_args()
    project=Path(__file__).resolve().parent;root=args.output_dir.resolve()
    if args.write:write_manifest(root,project)
    print(json.dumps(verify(root,project,args.check_index),ensure_ascii=False))


if __name__=="__main__":
    import sys
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    main()
