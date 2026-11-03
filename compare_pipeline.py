"""Rulează CP1 dintr-un commit și codul curent pe aceleași arhive reale.

Comparația folosește valorile în memorie, înaintea rotunjirii CSV din CP1.
Nu generează matrice X, distribuții/corelații CP2 sau modele.
"""
import argparse
import json
import re
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

import run_pipeline as current
from validate_outputs import validate


def capture_run(module, input_dir, output_dir):
    frames = {}
    original_save = module.save
    def capture(frame, destination):
        frames[Path(destination).name] = frame.copy()
        original_save(frame, destination)
    module.save = capture
    try:
        info = module.run(input_dir, output_dir)
    finally:
        module.save = original_save
    return frames, info


def compare_frames(before, after):
    if not before.date.equals(after.date):
        raise ValueError("Calendare diferite înainte/după")
    summary, differences = [], []
    for col in before.select_dtypes(include="number").columns:
        if col not in after:
            continue
        a, b = before[col], after[col]
        common = a.notna() & b.notna()
        delta = b-a
        changed = common & ~np.isclose(a, b, atol=1e-10, rtol=0, equal_nan=True)
        lost, gained = a.notna() & b.isna(), a.isna() & b.notna()
        displayed = common & a.round(5).ne(b.round(5))
        summary.append(dict(variable=col, before_days=int(a.notna().sum()), after_days=int(b.notna().sum()),
                            changed_common_days=int(changed.sum()), changed_at_5_decimals=int(displayed.sum()),
                            lost_days=int(lost.sum()), gained_days=int(gained.sum()),
                            affected_days=int((changed|lost|gained).sum()),
                            max_abs_difference=float(delta[common].abs().max()) if common.any() else np.nan))
        for i in before.index[changed|lost|gained]:
            differences.append(dict(date=before.at[i,"date"], variable=col, before=a[i], after=b[i],
                                    change="lost" if lost[i] else "gained" if gained[i] else "numeric"))
    return pd.DataFrame(summary), pd.DataFrame(differences)


def run(input_dir, output_dir, baseline_ref):
    output_dir.mkdir(parents=True, exist_ok=True)
    project = Path(__file__).resolve().parent
    test_command = [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", str(project/"tests"), "-v"]
    tests = subprocess.run(test_command, cwd=project, capture_output=True, text=True, encoding="utf-8", timeout=120)
    test_log = tests.stdout + tests.stderr
    (output_dir/"teste_sintetice.log").write_text(test_log, encoding="utf-8")
    if tests.returncode:
        raise RuntimeError("Testele sintetice au eșuat; vezi teste_sintetice.log")
    test_count = int(re.search(r"Ran (\d+) tests?", test_log)[1])
    print(f"TESTE AUTOMATE: {test_count} trecute", flush=True)
    commit = subprocess.check_output(["git","rev-parse", "--verify", baseline_ref+"^{commit}"], text=True).strip()
    source = subprocess.check_output(["git","show",commit+":run_pipeline.py"], encoding="utf-8")
    baseline = types.ModuleType("cp1_baseline")
    exec(compile(source, f"git:{commit}:run_pipeline.py", "exec"), baseline.__dict__)
    print(f"INAINTE: CP1 din commit {commit}", flush=True)
    before, before_info = capture_run(baseline, input_dir, output_dir/"inainte")
    print("DUPA: codul curent", flush=True)
    after, after_info = capture_run(current, input_dir, output_dir/"dupa")
    validate(output_dir/"dupa")
    summary, differences = compare_frames(before["dataset_aliniat_zilnic.csv"], after["dataset_aliniat_zilnic.csv"])
    current.save(summary, output_dir/"comparatie_variabile.csv")
    current.save(differences, output_dir/"diferente_zilnice.csv")
    viirs_before, viirs_filtered = before["viirs_daily.csv"], after["viirs_daily_nominal_high.csv"]
    vs, vd = compare_frames(viirs_before, viirs_filtered)
    current.save(vs, output_dir/"comparatie_viirs_filtrat.csv")
    current.save(vd, output_dir/"diferente_viirs_filtrat.csv")
    qa = after["ndvi_qa_comparison.csv"]
    qa_summary = qa.groupby("variant").agg(accepted_pixel_composites=("valid_pixel_count","sum"),
                                           total_pixel_composites=("total_pixels","sum"),
                                           composites_with_pixels=("valid_pixel_count",lambda v:int(v.gt(0).sum())))
    current.save(qa_summary.reset_index(), output_dir/"comparatie_ndvi_qa.csv")
    qa_wide = qa.pivot(index="composite_start",columns="variant",values="mean")
    qa_value_changes = {variant:int((~np.isclose(qa_wide.legacy,qa_wide[variant],atol=1e-10,rtol=0,equal_nan=True)).sum())
                        for variant in ["strict","justified"]}
    old_modis, new_modis = before["modis_daily.csv"], after["modis_daily.csv"]
    justified_daily = new_modis[["date","ndvi_justified_mean","ndvi_justified_valid_pixels_pct"]].rename(
        columns={"ndvi_justified_mean":"ndvi_mean","ndvi_justified_valid_pixels_pct":"ndvi_valid_pixels_pct"})
    ndvi_variants, _ = compare_frames(new_modis[["date","ndvi_mean","ndvi_valid_pixels_pct"]], justified_daily)
    current.save(ndvi_variants, output_dir/"comparatie_ndvi_zilnic_strict_justificat.csv")
    ndvi_vs_legacy, _ = compare_frames(old_modis[["date","ndvi_mean","ndvi_valid_pixels_pct"]], justified_daily)
    current.save(ndvi_vs_legacy, output_dir/"comparatie_ndvi_justificat_vs_cp1.csv")
    timing_changed, availability_changed = {}, {}
    for label in ["ndvi", "lst"]:
        col=f"{label}_available_from"
        availability_changed[label] = int((old_modis[col].fillna(pd.Timestamp("1900-01-01")) != new_modis[col].fillna(pd.Timestamp("1900-01-01"))).sum())
        col=f"{label}_composite_start"
        timing_changed[label] = int((old_modis[col].fillna(pd.Timestamp("1900-01-01")) != new_modis[col].fillna(pd.Timestamp("1900-01-01"))).sum())
    evidence={"baseline_commit":commit,"numeric_change_tolerance":1e-10,
              "comparison_precision":"DataFrames in memory, before CSV rounding",
              "inputs":after_info["inputs"],"modis_metadata_sha256":after_info["modis_metadata_sha256"],
              "before":before_info,"after":after_info,"changed_modis_assignment_days":timing_changed,
              "changed_modis_available_from_days":availability_changed,
              "ndvi_composites_changed_vs_legacy":qa_value_changes,
              "synthetic_tests":{"exit_code":tests.returncode,"tests_run":test_count,"command":test_command},
              "current_source_sha256":{name:current.file_sha256(project/name) for name in
                                       ["run_pipeline.py","pipeline_methods.py","validate_outputs.py","compare_pipeline.py","tests/test_pipeline.py"]},
              "test_commands":["python -X utf8 -B -m unittest discover -s tests -v",
                               "python -X utf8 -B validate_outputs.py --processed-dir "+str(output_dir/"dupa")]}
    (output_dir/"comparatie_manifest.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Comparație reală CP1 înainte / după corecțiile metodologice", "",
           f"Referință CP1: `{commit}`. Aceleași trei arhive reale din `data/raw/`; SHA-256 în `comparatie_manifest.json`.",
           "Comparația numerică folosește valorile înainte de export, cu toleranță absolută 1e-10 și relativă zero. O diferență foarte mică poate să nu apară la cele 5 zecimale ale CSV-ului vechi.", "",
           "| Variabilă | Zile înainte | Zile după | Valori comune schimbate | Zile pierdute | Zile câștigate | Diferența absolută maximă |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for r in summary.itertuples(index=False):
        lines.append(f"| {r.variable} | {r.before_days} | {r.after_days} | {r.changed_common_days} | {r.lost_days} | {r.gained_days} | {r.max_abs_difference:.10g} |")
    lines += ["", "## Interpretare și date incomplete", "",
              "- Precipitația și radiația sunt deja dezacumulate. Mutăm intervalele cu o oră înainte de gruparea pe zi UTC; nu diferențiem valorile din nou.",
              "- 31.12.2024 are 23 intervale disponibile pentru fiecare total. Totalurile sunt NaN; sumele parțiale sunt distincte, cu flag complete=0. Este necesar tp și ssrd la 01.01.2025 00:00 UTC, pe aceeași grilă și din aceeași sursă.",
              "- RH se calculează pe celulă și oră, apoi se mediază spațial și zilnic. Coordonatele ERA5 sunt verificate între fișiere, în BBOX, cu pasul de 0,1°; punctele efective sunt în manifest.",
              f"- LST: {timing_changed['lst']} zile primesc altă înregistrare sau o înregistrare anterior lipsă după corectarea sfârșitului de an. NDVI: {timing_changed['ndvi']} zile cu alocare temporală schimbată. Limitele sunt din metadata NASA CMR salvate local.",
              f"- Coloana available_from LST diferă pe {availability_changed['lst']} rânduri; o parte indică același compozit, căruia i s-a corectat doar sfârșitul ferestrei. Acestea nu sunt toate schimbări ale valorii LST.",
              "- available_from este închiderea ferestrei observațiilor, nu data istorică de publicare. NDVI de sfârșit de an poate traversa anul; LST se încheie la 31 decembrie.",
              "- Lipsește compozitul LST cu începutul 16.10.2022. Se păstrează propagarea precedentului, cu vechime explicită; un compozit existent fără pixeli valizi rămâne lipsă.",
              "", "## NDVI: strict / marginal justificat", "",
              "Strict: reliability=0, MODLAND=0 și QA detaliat compatibil. Marginal justificat: adaugă reliability=1 cu MODLAND 0/1, usefulness documentat și utilizabil, teren, fără aerosol ridicat, nor adiacent/mixt, zăpadă sau umbră. Fără prag numeric impus pe usefulness între codurile utilizabile; varianta strictă rămâne implicită.", "",
              "| Variantă | Observații pixel × compozit acceptate | Compozite cu pixeli |",
              "|---|---:|---:|"]
    for variant,r in qa_summary.iterrows():
        lines.append(f"| {variant} | {int(r.accepted_pixel_composites)} / {int(r.total_pixel_composites)} | {int(r.composites_with_pixels)} |")
    lines += ["",f"Medii de compozit schimbate față de CP1: strict {qa_value_changes['strict']}, marginal justificat {qa_value_changes['justified']}.",
              f"Strict și marginal justificat: {int(new_modis.ndvi_mean.notna().sum())}, respectiv {int(new_modis.ndvi_justified_mean.notna().sum())} zile disponibile. Între variante diferă {int(ndvi_variants.loc[ndvi_variants.variable.eq('ndvi_mean'),'changed_common_days'].iloc[0])} medii zilnice; vezi comparatie_ndvi_zilnic_strict_justificat.csv.",
              "Acoperirea zilnică a ambelor variante este în `dupa/raport_acoperire.csv`. Comparația lor pe fiecare compozit este în `dupa/ndvi_qa_comparison.csv`.", "",
              "## Pixeli puțini și vechime", "",
              "Nu s-a aplicat un prag minim de acoperire. Numărul și procentul pixelilor valizi însoțesc fiecare valoare; `dupa/modis_coverage_sensitivity.csv` arată pierderea de zile la praguri ipotetice de 1, 5, 10, 25, 50 și 75%, fără a le aplica.",
              "`*_age_days` măsoară zilele de la ultima zi a ferestrei (prima valoare=1); `*_carry_days` măsoară zilele de la prima alocare permisă (prima valoare=0). Nu cunoaștem ziua exactă de achiziție a fiecărui pixel din aceste straturi. Limita de propagare CP1 rămâne explicit 32 zile NDVI / 16 zile LST după închiderea ferestrei.", "",
              "## VIIRS", "",
              f"Înainte și în varianta completă: {before_info['viirs_detections']} detecții în {before_info['viirs_days_with_detection']} zile. Sunt {after_info['viirs']['confidence_counts'].get('l',0)} detecții low. Varianta nominal/high: {after_info['viirs']['filtered_detections']} detecții în {after_info['viirs']['filtered_days_with_detection']} zile.",
              "`comparatie_viirs_filtrat.csv` cuantifică zilele și valorile afectate; numărătoarea completă este păstrată, cu low separat. Zero înseamnă zero detecții în arhivă; acoperirea observațională și absența incendiului nu pot fi stabilite. Suma FRP peste achiziții este descriptivă, nu energie zilnică sau putere regională simultană.", "",
              "## Validare și limite", "",
              f"Validatorul rezultatelor corectate și cele {test_count} teste automate au trecut în această rulare. Testele folosesc rastruri/CSV sintetice și verifică și calendarul NASA salvat. Jurnalul este în teste_sintetice.log; comenzile și hash-urile codului verificat sunt în manifest. Fixture-urile nu sunt confundate cu datele reale.",
              "Totalurile incomplete nu sunt imputate. Medii spațiale neponderate; maximele ERA5 sunt maximele mediei regionale orare. Datele din ziua incendiului nu devin automat predictori anteriori incendiului; nu s-a implementat matricea X sau analiza statistică CP2."]
    (output_dir/"raport_comparativ.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(summary.to_string(index=False))
    print("COMPARATIE FINALIZATA; validatorul corectat a trecut.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir",type=Path,default=Path("data/raw"))
    parser.add_argument("--output-dir",type=Path,default=Path("outputs/corectii_pipeline"))
    parser.add_argument("--baseline-ref",default="e0c34bc071712bd77f96f94ee88f801d06fafc57")
    args=parser.parse_args()
    run(args.input_dir,args.output_dir,args.baseline_ref)


if __name__ == "__main__":
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    main()
