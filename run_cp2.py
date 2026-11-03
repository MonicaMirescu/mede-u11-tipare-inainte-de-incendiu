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


def write_methodology(root):
    text = """# Metodologie CP2 · MEDE U11

[Repository](https://github.com/MonicaMirescu/mede-u11-tipare-inainte-de-incendiu/tree/cp2-final).
Unitate: **zi × regiune**, Bejís–Villanueva de Viver, Castellón; BBOX lat 39,7…40,2 / lon −1,0…−0,4.
Calendar: 01.01.2020–31.12.2024, **1.827 zile**. X are **12 predictori fizici** grupați ERA5 (9), NDVI (1), LST (2), plus indicatori auxiliari: 54 coloane în CSV.

## Grid și agregare spațială

ERA5-Land: 0,1°, 5×6=30 centre efectiv extrase, lat 39,7…40,1 / lon −1,0…−0,5. Cititorul verifică unitățile, unicitatea, monotonia, pasul, BBOX și concordanța coordonatelor între fișiere. Media regională este aritmetică la fiecare oră, cu suport fix; nu se adaugă centre la marginile BBOX.

MODIS AppEEARS: grile exportate WGS84/EPSG:4326, reproiectate nearest-neighbour conform arhivei; 240×288=69.120 centre NDVI și 60×72=4.320 centre LST în BBOX. Rezoluții nominale: 250 m / 1 km. Media folosește pixelii valizi QA, neponderați pe arie. Sursele devin comparabile la nivelul regiunii, fără o nouă interpolare spațială pe un grid comun de pixeli. Suportul efectiv diferă între surse și compozite.

VIIRS: puncte filtrate în BBOX și interval, agregate pe zi UTC: număr detecții și FRP. Numărul low este explicit; nominal/high este păstrat în tabelul complet. VIIRS nu intră în X. Zero detecții nu dovedește absența focului; detecțiile nu sunt incendii distincte, iar suma FRP peste achiziții nu este energie zilnică sau putere regională simultană.

## ERA5: zi UTC, conversii și D−1

Temperatura/punctul de rouă: K−273,15→°C. RH se calculează **pe celulă și oră**, cu Magnus (17,625; 243,04), limitată la 0–100%, apoi se mediază regional și zilnic. Vânt: sqrt(u²+v²) pe celulă/oră, apoi media regională, în m/s. Sol: strat 0–7 cm, m³/m³. Mediile zilnice folosesc 00:00–23:00 UTC; maximele sunt maximele mediei regionale orare, nu maximele celulelor sau rafale.

tp/ssrd sunt deja dezacumulate; timestamp-ul încheie intervalul orar. Totalul zilei D folosește D 01:00…D+1 00:00, fără o nouă diferențiere. Conversii: m×1000→mm; J/m²÷10⁶→MJ/m². Totalul necesită 24 intervale valide; altfel este NaN, cu sumă parțială și număr de intervale separate. Reziduurile negative minuscule sunt controlate cu toleranțele pipeline-ului validat.

În X datat **D**, ERA5 provine din **D−1**, prin join pe data calendaristică. Tabelul complet păstrează ziua originală D. Prima zi X are cei 9 predictori ERA5 lipsă: ar fi necesare observațiile din 31.12.2019 (fluxuri 31.12.2019 01:00…01.01.2020 00:00). La 31.12.2024, tabelul complet are 23 intervale tp/ssrd: sunt necesare valorile la **01.01.2025 00:00 UTC**, aceeași sursă și grilă. Nu se inventează totaluri. Ultimul X folosește 30.12.2024.

## MODIS: QA, ferestre și propagare

NDVI principal strict: reliability=0, MODLAND=0, usefulness utilizabil 0…12, teren, fără aerosol ridicat, nor adiacent/mixt, zăpadă sau umbră; fill și brut în afara −2000…10000 respinse. Conversie brut×0,0001. LST zi/noapte: QC obligatoriu=00 și 200–360 K, conform pipeline-ului validat; QC=0 este valid, temperatura brută 0 este fill. Conversie brut×0,02−273,15→°C. Fără prag minim arbitrar de pixeli: se păstrează numărul/procentul valid, cu numitor toate centrele din BBOX.

Ferestrele vin din time bounds; în arhivele date, fără bounds, din extrasul NASA CMR versionat în metadata/modis_composite_periods.json. LST nu are mereu 8 zile: ultima fereastră anuală are 5/6; NDVI poate traversa anul. Nu se deduce durata din următoarea înregistrare.

În ziua D se folosește ultimul compozit cu sfârșit exclusiv ≤ D, prin căutare în trecut. Este **propagare constantă**, nu interpolare liniară și nu achiziție zilnică nouă. Nu se folosesc observații din viitor. Limitele validate rămân 32 zile NDVI / 16 zile LST după închiderea ferestrei; nu sunt prezentate drept praguri optime. Un compozit fără pixeli QA valizi rămâne NaN, fără recuperarea ascunsă a unuia mai vechi. Dacă lipsește înregistrarea (LST 16.10.2022), precedentul poate fi reportat în limita documentată.

age_days = zile față de ultima zi a ferestrei (minim 1); carry_days = zile de la prima alocare permisă (minim 0); is_carried marchează reutilizarea ulterioară. Nu cunoaștem ziua achiziției fiecărui pixel. available_from este închiderea ferestrei, nu publicarea operațională istorică. Primele 3 zile NDVI rămân lipsă. NaN și indicatorii de lipsă nu sunt imputări.

## Statistici și corelații

statistici_predictori.csv conține exclusiv cei 12 predictori: n valid/lipsă, medie, mediană, deviație standard de eșantion (ddof=1), minim, Q1/Q2/Q3 cu interpolare liniară a cuantilelor și maxim. Histogramele reprezentative au 35 intervale și folosesc CSV-ul X validat; nu schimbă datele.

Spearman se calculează pe zilele complete ale **fiecărei perechi**, cu ranguri medii la egalități, recalculate după eliminarea lipsurilor. Pentru <2 valori sau variabilă constantă, ρ este NaN. Sunt publicate numai cele **9×3=27 perechi ERA5–MODIS**, cu n zile valide pentru fiecare. Heatmap-ul folosește direct acest CSV și scară −1…+1.

Corelația descrie asocierea monotonă, nu cauzalitate sau semnal specific incendiilor. Nu există ajustare pentru sezonalitate/autocorelație; n înseamnă zile aliniate, nu observații independente. Valorile MODIS repetate și suportul QA uneori redus limitează interpretarea.

Acoperirea pe surse folosește celulele predictorilor fizici: zile×număr predictori. Lipsuri: ERA5 9/16.443 (0,055%), NDVI 3/1.827 (0,164%), LST 32/3.654 (0,876%); total 44/21.924. Acoperirea per variabilă include numai X principal, cu zero imputări și reportări explicit numărate.

## Reproducere și verificare

Comenzile sunt în README. Rularea standard recitește cele trei arhive, execută testele și toate verificările ingestiei, apoi publică numai 7 CSV, 4 PNG și acest document. Intermediarii QA/ingestie sunt temporari. Manifestul păstrează hash-urile intrărilor, codului și rezultatelor; validare_CP2.json rezumă verificările, iar publicatie_CP2.json inventariază livrabilul.

Referința numerică este commit-ul validat 47782513a066921737ad93db5c5f30ee69ca6e9f; metadata/cp2_validated_reference.json păstrează hash-urile celor 7 CSV-uri selectate/extrase. Valorile sunt identice cu referința, inclusiv n și lipsurile; statisticile sunt extrase prin selecție, fără schimbarea definițiilor. Variantele extinse rămân în ramura cp2-matrice-statistici și PR #1, nu în livrabilul final.

Surse: [ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries), [MOD13 QA](https://lpdaac.usgs.gov/documents/621/MOD13_User_Guide_V61.pdf), [NASA CMR](https://cmr.earthdata.nasa.gov/search/), [VIIRS FIRMS](https://firms.modaps.eosdis.nasa.gov/download/).
Fără PCA, clustering sau modele predictive.
"""
    (root / "metodologie_CP2.md").write_text(text, encoding="utf-8")


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
    write_methodology(root)
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
