"""MEDE U11 CP2: matrice X, acoperire, distribuții și corelații Spearman."""
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
                          descriptive_statistics, make_dictionary, parse_dates,
                          source_coverage, spearman_pairwise)
from validate_outputs import validate as validate_corrected


def save_matrix(frame, destination):
    ingestion.save(frame.rename_axis("variable").reset_index(), destination)


def markdown_table(frame, columns):
    lines=["| "+" | ".join(columns)+" |", "|"+"|".join(["---"]*len(columns))+"|"]
    for _,row in frame[columns].iterrows():
        values=[f"{v:.6g}" if isinstance(v,(float,np.floating)) else str(v) for v in row]
        lines.append("| "+" | ".join(values)+" |")
    return lines


def methodology(root, tables, stats, coverage, cross, source_info, test_count, generated):
    matrix=tables["X_principal"]
    numeric=len(matrix.select_dtypes(include="number").columns)
    missing=int(matrix[list(FEATURES)].isna().sum().sum())
    rows=["# MEDE U11 · Metodologie CP2 și rezultate reale", "",
          "[Repository proiect](https://github.com/MonicaMirescu/mede-u11-tipare-inainte-de-incendiu). Artefacte locale pentru revizuire; nu au fost publicate prin această rulare.", "",
          "## Unitate și matrice", "",
          f"Unitatea este zi × regiune, Bejís–Villanueva de Viver: 01.01.2020–31.12.2024, {len(matrix)} zile consecutive. BBOX: lat 39,7…40,2; lon −1,0…−0,4.",
          f"X fizic are **{len(matrix)} × {len(FEATURES)}** predictori. `matrice_X.csv` are {len(matrix.columns)} coloane în total: data, 12 predictori, indicatori de lipsă/QA/acoperire și proveniență temporală. Sunt {numeric} coloane numerice în export; numai cele 12 cu rol predictor intră în corelația principală. Ordinea este ERA5, NDVI, LST. Dicționarul indică rolul, unitatea și alinierea fiecărei coloane pentru fiecare tabel/scenariu.",
          "Selecția descrie starea termică a aerului, umezeala atmosferică și a solului, precipitațiile, energia solară, vântul, vegetația și temperatura suprafeței. Mediile și maximele temperaturii/vântului păstrează atât nivelul zilnic, cât și episodul orar cel mai intens. Selecția este fizică, fără alegerea variabilelor după detecțiile VIIRS; variabilele corelate rămân vizibile în această etapă descriptivă.",
          "Tabelul aliniat complet păstrează datele ERA5 ale zilei D, toate coloanele MODIS, detecțiile VIIRS complete și varianta VIIRS nominal/high. VIIRS este separat de predictorii X. Zero detecții nu este dovadă de absență a incendiului.", "",
          "## Geografie și agregare regională", "",
          "ERA5: grilă regulată de 0,1°, 5×6=30 centre efectiv extrase: lat 39,7…40,1 și lon −1,0…−0,5. Coordonatele sunt validate între fișiere, după unități, unicitate, monotonie, pas și apartenență la BBOX. Se face media aritmetică pe cele 30 de puncte la fiecare oră; o celulă lipsă nu este ascunsă prin schimbarea suportului regional. Nu inventăm centre pe marginile nordică/estică și nu efectuăm o nouă interpolare spațială.",
          "MODIS: exportul AppEEARS este deja reproiectat în WGS84/EPSG:4326 prin nearest-neighbour, conform README-ului arhivei. Selectăm centrele din BBOX: 240×288=69.120 pixeli NDVI și 60×72=4.320 pixeli LST. Media este pe pixelii care trec QA. Rezoluțiile nominale ale produselor sunt 250 m/1 km; grila geografică exportată nu are aceeași arie fizică pentru fiecare pixel. Mediile sunt neponderate; nu reprezintă integrarea exactă pe aria BBOX și nu se pretinde un grid comun de pixeli între surse.", "",
          "## ERA5: ore, unități și D−1", "",
          "Temperatura și punctul de rouă se convertesc K→°C prin scăderea lui 273,15. Umiditatea relativă se calculează pe celulă/oră cu formula Magnus din pipeline-ul validat (coeficienți 17,625 și 243,04), se limitează la 0–100%, apoi se mediază regional și zilnic. Viteza vântului este sqrt(u²+v²) pe celulă/oră, apoi media regională; unitatea rămâne m/s. Umiditatea solului din stratul 0–7 cm rămâne m³/m³.",
          "Mediile zilnice folosesc orele 00:00–23:00 UTC pentru variabilele instantanee. Maximele temperaturii și vântului sunt maximele mediei regionale orare, nu maximele tuturor celulelor și nici rafale observate.",
          "Precipitația tp și radiația ssrd din produsul ERA5-Land time-series sunt deja dezacumulate. Valoarea la t acoperă ora încheiată la t: totalul zilei D folosește D 01:00…D+1 00:00. Conversii: m×1000→mm; J/m²÷10⁶→MJ/m². Nu diferențiem încă o dată. Un total este prezent numai cu 24 intervale valide; suma parțială, numărul de intervale și completitudinea sunt păstrate separat în tabelul complet/surse. Reziduurile negative minuscule sunt controlate și limitate la zero în toleranțele CP1 documentate, nu folosite pentru imputare.",
          "**În X datat D folosim exclusiv ERA5 din D−1**, prin join pe data calendaristică, inclusiv pentru indicatorii de completitudine. Aceasta este alegerea confirmată de utilizatoare: informațiile din orele ulterioare unei detecții din D nu intră în rândul D. Nu schimbăm data observațiilor din tabelul complet. Pentru prima zi X lipsește ERA5 din 31.12.2019: toți cei 9 predictori ERA5 sunt NaN. Pentru completare ar fi necesare variabilele instantanee ale acelei zile și tp/ssrd din 31.12.2019 01:00…01.01.2020 00:00, din aceeași sursă și pe aceeași grilă.",
          "[Documentație ECMWF pentru dezacumulare](https://confluence.ecmwf.int/pages/viewpage.action?pageId=627854124).", "",
          "## MODIS: QA și ferestre efective", "",
          "NDVI principal: reliability=0, MODLAND=0, usefulness utilizabil 0…12, teren, fără aerosol ridicat, nor adiacent/mixt, zăpadă sau umbră. Fill și valorile brute în afara intervalului −2000…10000 sunt respinse; factorul este 0,0001. Sensibilitatea adaugă numai reliability=1 cu MODLAND=0/1 și aceleași verificări detaliate. Codurile usefulness 13…15 sunt inutilizabile. Nu eliminăm arbitrar codurile intermediare prezente în export. [Ghid MOD13 C6.1](https://lpdaac.usgs.gov/documents/621/MOD13_User_Guide_V61.pdf).",
          "LST zi/noapte: temperatura brută validă, biții obligatorii QC=00 și interval fizic 200–360 K din pipeline-ul validat; QC=0 este valid, temperatura brută 0 este fill. Conversie: brut×0,02−273,15→°C. Numărul/procentul pixelilor acceptați are ca numitor toate centrele selectate în BBOX. Nu s-a aplicat un prag minim arbitrar de acoperire. Sensibilitatea la pragurile spațiale ipotetice rămâne în `surse_corectate/modis_coverage_sensitivity.csv`.",
          "Limitele temporale sunt citite din time bounds dacă există; pentru aceste fișiere, care nu au bounds, se utilizează extrasul NASA CMR versionat în metadata/modis_composite_periods.json, cu dovezi pentru fiecare dată pe două tile-uri de referință. LST are ferestre de 8 zile și ultima fereastră anuală de 5/6 zile; NDVI de sfârșit de an poate traversa anul. Nu deducem durata din distanța până la următorul compozit, fiindcă ar confunda o înregistrare lipsă cu o fereastră mai lungă. Unitățile/calendarul NetCDF sunt controlate explicit.", "",
          "## Propagare, vechime și goluri", "",
          "Pentru ziua D folosim ultimul compozit cu sfârșitul exclusiv al ferestrei ≤ D, prin căutare în trecut `merge_asof`. Valoarea este reportată ca o constantă între actualizări; aceasta este propagare temporală, nu interpolare liniară între două valori și nu observație zilnică nouă. Nu se folosesc compozite din viitor. Limitele CP1 rămân explicit 32 zile NDVI / 16 zile LST după închiderea ferestrei, fără a pretinde că sunt praguri optime.",
          "`*_age_days` este vârsta față de ultima zi a ferestrei (1 la prima alocare); `*_carry_days` este timpul de la prima alocare permisă (0 inițial); `*_is_carried` indică repetarea după acea primă alocare. Vârsta ferestrei nu este data exactă de achiziție a fiecărui pixel. `available_from` înseamnă închiderea ferestrei, nu data reală a publicării istorice; analiza nu simulează disponibilitatea operațională a produselor.",
          "Un compozit existent fără pixeli valizi produce NaN, fără a recupera pe ascuns un compozit mai vechi. Dacă lipsește înregistrarea, se poate reporta precedentul în limita documentată; de exemplu lipsește LST 16.10.2022. NDVI nu este disponibil în primele 3 zile, fiindcă prima fereastră extrasă se încheie pe 03.01.2020. Flag-urile de lipsă descriu NaN, fără să-l înlocuiască.",
          "În tabelul complet, 31.12.2024 are numai 23 intervale pentru tp/ssrd; totalurile sunt NaN, iar sumele parțiale sunt păstrate. Sunt necesare tp și ssrd la 01.01.2025 00:00 UTC pe aceeași grilă. În X, ultimul rând folosește ERA5 din 30.12.2024 și nu preia totalurile incomplete ale zilei 31.12.2024.", "",
          "## Acoperire măsurată în X", "",
          f"Sunt {missing} celule lipsă dintre {len(matrix)*len(FEATURES)} celule ale predictorilor fizici. Procentele de mai jos folosesc ca numitor zile×numărul predictorilor din sursă; nu includ indicatorii auxiliari. Nu confundăm procentul celulelor lipsă cu procentul zilelor având cel puțin o lipsă.", ""]
    rows+=markdown_table(coverage,["source","n_predictors","n_missing_cells","n_cells","missing_cells_pct","days_with_any_missing"])
    rows += ["", "## Statistici descriptive și grafice", "",
             f"`statistici_descriptive.csv` are {len(stats)} rânduri: fiecare coloană numerică din X principal, X de sensibilitate și tabelul complet. Include n valid/lipsă, medie, mediană, deviație standard de eșantion (ddof=1), minim, Q1/Q2/Q3 cu interpolare liniară a cuantilelor și maxim. Datele/șirurile nu sunt tratate ca numere. O variabilă fără valori valide are statistici NaN, fără valori inventate.",
             "Histogramele și boxploturile sunt paginate, cu axe/unități proprii fiecărei variabile; nu comparăm direct pe aceeași axă temperaturi, NDVI și număr de detecții. Boxploturile folosesc mustăți de 1,5×IQR; punctele exterioare sunt afișate și păstrate în calcule. Histogramele folosesc 35 de intervale sau bare discrete pentru ≤5 valori distincte. `index_grafice.csv` leagă fiecare variabilă/scenariu de ambele grafice. Distribuțiile MODIS sunt ale valorilor zilnice reportate, nu ale unor achiziții independente.", "",
             "## Spearman și perechi valide", "",
             "Corelațiile includ numai cei 12 predictori fizici. Pentru fiecare pereche se elimină numai zilele în care unul dintre cei doi lipsește, apoi se recalculează rangurile pe pereche, cu rang mediu la egalități. Spearman este corelația Pearson a acestor ranguri. Se raportează separat numărul zilelor comune în `numar_observatii_corelatii.csv`, inclusiv pe diagonală. Pentru mai puțin de două valori sau o variabilă constantă corelația este NaN. Nu se înlocuiește o corelație nedefinită cu zero.",
             "Spearman descrie asocieri monotone fără a presupune normalitatea variabilelor; este potrivit descriptiv inclusiv pentru precipitații asimetrice și multe egalități. Nu reprezintă ajustare pentru sezonalitate, tendințe sau dependență temporală. Compozitele reportate reduc numărul efectiv de observații independente: n este număr de zile, nu eșantion independent. Nu calculăm p-value și nu interpretăm corelația drept cauzalitate sau dovadă a unui semnal specific incendiilor. [Definiția Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html), [observații complete pe pereche](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.corr.html).", "",
             "Cele mai mari 5 corelații între ERA5 din D−1 și MODIS, ordonate după |ρ|; perechile din aceeași sursă sunt excluse din acest clasament:", ""]
    rows+=markdown_table(cross.head(5),["era5_variable","modis_variable","spearman_rho","n_valid_days"])
    rows += ["", "## Sensibilitate NDVI și VIIRS", "",
             "În `sensibilitate_NDVI/` se repetă X și corelațiile cu politica marginală justificată. Numai NDVI și indicatorii săi de suport/vechime se schimbă; ERA5 și LST păstrează exact aceeași aliniere. Comparația perechilor este în `sensibilitate_ndvi_corelatii.csv`. Nu selectăm retrospectiv politica care produce corelații mai mari.",
             f"VIIRS complet: {source_info['viirs_detections']} detecții în {source_info['viirs_days_with_detection']} zile. Low: {source_info['viirs']['confidence_counts'].get('l',0)}. Varianta n/h: {source_info['viirs']['filtered_detections']} detecții în {source_info['viirs']['filtered_days_with_detection']} zile. Acestea nu sunt numere de incendii distincte. Acoperirea observațională nu poate fi dedusă din acest CSV de detecții. Suma FRP peste achiziții nu este energie zilnică sau putere regională simultană.", "",
             "## Reproducere și validare", "", "```bash",
             "python -m pip install -r requirements.txt",
             "python -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2",
             "python -X utf8 -B validate_cp2.py --output-dir outputs/CP2", "```", "",
             f"Rularea curentă a executat {test_count} teste automate pe fixture-uri sintetice și calendarul NASA salvat, apoi pipeline-ul corectat pe arhivele originale. Hash-urile arhivelor, metadatelor și codului, versiunile bibliotecilor și inventarul artefactelor sunt în `manifest_CP2.json`. Rezultatul verificării fișierelor efectiv salvate este în `validare_CP2.json`.",
             "Nu s-au executat PCA, scree plot, clustering sau modele predictive. Pentru etapele ulterioare rămân de discutat validarea temporală, disponibilitatea operațională reală a produselor și calitatea reprezentării regionale la suport spațial redus.", "", "## Fișiere generate", ""]
    rows += [f"- `{name}`" for name in sorted(generated)]
    (root/"metodologie_CP2.md").write_text("\n".join(rows)+"\n",encoding="utf-8")


def run(input_dir, output_dir, metadata_path=ingestion.METADATA):
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    project=Path(__file__).resolve().parent
    print("[1/5] Teste automate",flush=True)
    command=[sys.executable,"-X","utf8","-B","-m","unittest","discover","-s",str(project/"tests"),"-v"]
    result=subprocess.run(command,cwd=project,capture_output=True,text=True,encoding="utf-8",timeout=120)
    log=result.stdout+result.stderr
    (root/"teste_automate.log").write_text(log,encoding="utf-8")
    if result.returncode:raise RuntimeError("Testele au eșuat; consultați teste_automate.log")
    test_count=int(re.search(r"Ran (\d+) tests?",log)[1])
    print("[2/5] Pipeline corectat pe arhivele reale",flush=True)
    source_info=ingestion.run(input_dir,root/"surse_corectate",metadata_path)
    full=parse_dates(validate_corrected(root/"surse_corectate"))
    filtered=pd.read_csv(root/"surse_corectate/viirs_daily_nominal_high.csv",parse_dates=["date"])
    filtered=filtered.rename(columns={name:name.replace("viirs_","viirs_nominal_high_",1) for name in filtered if name!="date"})
    full=full.merge(filtered,on="date",validate="one_to_one")
    check_calendar(full)
    print("[3/5] Matrice, statistici și corelații",flush=True)
    main=build_matrix(full)
    sensitivity=build_matrix(full,ndvi_policy="justified")
    tables={"X_principal":main,"X_sensibilitate":sensitivity,"aliniat_complet":full}
    sensitivity_dir=root/"sensibilitate_NDVI";sensitivity_dir.mkdir(exist_ok=True)
    for frame,path in [(main,root/"matrice_X.csv"),(full,root/"tabel_aliniat_complet.csv"),
                        (sensitivity,sensitivity_dir/"matrice_X.csv")]:ingestion.save(frame,path)
    dictionary=make_dictionary(tables);stats=descriptive_statistics(tables)
    ingestion.save(dictionary,root/"dictionar_variabile.csv")
    ingestion.save(stats,root/"statistici_descriptive.csv")
    coverage=source_coverage(main);ingestion.save(coverage,root/"acoperire_surse.csv")
    by_variable=stats[["table","variable","source","role","unit","n_total","n_valid","n_missing","missing_pct"]].copy()
    by_variable["imputed_days"]=0
    carried=[]
    for row in by_variable.itertuples(index=False):
        prefix={"ndvi_mean":"ndvi","ndvi_justified_mean":"ndvi_justified","lst_day_mean_c":"lst_day","lst_night_mean_c":"lst_night"}.get(row.variable)
        frame=tables[row.table]
        carried.append(int(frame[f"{prefix}_is_carried"].sum()) if prefix else 0)
    by_variable["carried_days_after_first_assignment"]=carried
    ingestion.save(by_variable,root/"acoperire_variabile.csv")
    correlations=[]
    for frame,folder in [(main,root),(sensitivity,sensitivity_dir)]:
        rho,n=spearman_pairwise(frame[list(FEATURES)])
        cross=cross_source_correlations(rho,n)
        save_matrix(rho,folder/"matrice_corelatii.csv");save_matrix(n,folder/"numar_observatii_corelatii.csv")
        ingestion.save(cross,folder/"corelatii_ERA5_MODIS.csv")
        correlations.append((rho,n,cross))
    main_rho,main_n,cross=correlations[0];sens_rho,sens_n,sens_cross=correlations[1]
    comparison=cross.merge(sens_cross,on=["era5_variable","modis_variable"],suffixes=("_strict","_justificat"),validate="one_to_one")
    comparison["rho_difference"]=comparison.spearman_rho_justificat-comparison.spearman_rho_strict
    ingestion.save(comparison,root/"sensibilitate_ndvi_corelatii.csv")
    print("[4/5] Grafice PNG pentru toate variabilele numerice",flush=True)
    with tempfile.TemporaryDirectory(prefix="mede_cp2_matplotlib_") as config:
        os.environ["MPLCONFIGDIR"]=config
        from cp2_figures import generate_figures
        figures,figure_index=generate_figures(tables,main_rho,main_n,sens_rho,sens_n,root/"grafice")
    ingestion.save(figure_index,root/"index_grafice.csv")
    source_files=[p.relative_to(root).as_posix() for p in (root/"surse_corectate").iterdir() if p.is_file()]
    generated=source_files+[p.relative_to(root).as_posix() for p in figures]+[
        "matrice_X.csv","tabel_aliniat_complet.csv","dictionar_variabile.csv","statistici_descriptive.csv",
        "acoperire_surse.csv","acoperire_variabile.csv","matrice_corelatii.csv","numar_observatii_corelatii.csv",
        "corelatii_ERA5_MODIS.csv","sensibilitate_ndvi_corelatii.csv","sensibilitate_NDVI/matrice_X.csv",
        "sensibilitate_NDVI/matrice_corelatii.csv","sensibilitate_NDVI/numar_observatii_corelatii.csv",
        "sensibilitate_NDVI/corelatii_ERA5_MODIS.csv","index_grafice.csv","metodologie_CP2.md",
        "manifest_CP2.json","validare_CP2.json","teste_automate.log"]
    methodology(root,tables,stats,coverage,cross,source_info,test_count,generated)
    manifest={"period":source_info["period"],"bbox":source_info["bbox"],"era5_lag_days":1,"ndvi_main_policy":"strict",
              "matrix_csv_shape":list(main.shape),"physical_predictor_shape":[len(main),len(FEATURES)],
              "predictors":list(FEATURES),"inputs":source_info["inputs"],"modis_metadata_sha256":source_info["modis_metadata_sha256"],
              "ingestion_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
              "source_sha256":{n:ingestion.file_sha256(project/n) for n in ["run_cp2.py","cp2_analysis.py","cp2_figures.py","validate_cp2.py","run_pipeline.py","pipeline_methods.py","validate_outputs.py","tests/test_cp2.py","tests/test_pipeline.py","requirements.txt"]},
              "versions":{"python":sys.version,"numpy":np.__version__,"pandas":pd.__version__,"matplotlib":matplotlib.__version__},
              "numeric_conventions":{"correlation":"Spearman; pairwise complete; average ranks","std_ddof":1,"quantile_interpolation":"linear","imputation":"none","csv_float_format":"%.12g"},
              "tests":{"command":command,"exit_code":result.returncode,"tests_run":test_count},
              "missing_by_source":coverage.to_dict("records"),"top5_cross_source_correlations":cross.head(5).to_dict("records"),
              "generated_files":sorted(generated),
              "output_sha256":{n:ingestion.file_sha256(root/n) for n in generated if n not in {"manifest_CP2.json","validare_CP2.json"}}}
    (root/"manifest_CP2.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("[5/5] Verificarea fișierelor efectiv generate",flush=True)
    from validate_cp2 import validate
    validation=validate(root)
    validation["source_tests_passed"]=test_count
    (root/"validare_CP2.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(validation,ensure_ascii=False))
    print(coverage.to_string(index=False))
    print(cross.head(5)[["era5_variable","modis_variable","spearman_rho","n_valid_days"]].to_string(index=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir",type=Path,default=Path("data/raw"))
    parser.add_argument("--output-dir",type=Path,default=Path("outputs/CP2"))
    parser.add_argument("--modis-metadata",type=Path,default=ingestion.METADATA)
    args=parser.parse_args();run(args.input_dir,args.output_dir,args.modis_metadata)


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    main()
