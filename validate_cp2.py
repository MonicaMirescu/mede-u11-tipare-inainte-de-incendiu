"""Verifică artefactele CP2 efectiv salvate, inclusiv concordanța cu sursele."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from cp2_analysis import (FEATURES, ERA_FEATURES, build_matrix, check_calendar, parse_dates,
                          descriptive_statistics, source_coverage, spearman_pairwise)
from validate_outputs import require, validate as validate_corrected
from run_pipeline import file_sha256


def validate(output_dir):
    root=Path(output_dir)
    original=parse_dates(validate_corrected(root/"surse_corectate"))
    complete=parse_dates(pd.read_csv(root/"tabel_aliniat_complet.csv"))
    main=parse_dates(pd.read_csv(root/"matrice_X.csv"))
    sensitivity=parse_dates(pd.read_csv(root/"sensibilitate_NDVI/matrice_X.csv"))
    tables={"X_principal":main,"X_sensibilitate":sensitivity,"aliniat_complet":complete}
    for frame in tables.values():check_calendar(frame)
    require(not any(n.startswith("viirs_") for n in main), "VIIRS a intrat în X")
    require(set(n for n in main if n in FEATURES)==set(FEATURES), "Predictori X lipsă")
    for name in original:
        if name=="date" or pd.api.types.is_datetime64_any_dtype(original[name]):
            require(original[name].equals(complete[name]),f"Sursa a fost modificată în tabelul complet: {name}")
        else:
            require(np.allclose(original[name],complete[name],equal_nan=True),f"Sursa modificată: {name}")
    filtered=pd.read_csv(root/"surse_corectate/viirs_daily_nominal_high.csv")
    for name in ["viirs_detection_count","viirs_frp_sum_mw","viirs_frp_max_mw","viirs_has_detection"]:
        target=name.replace("viirs_","viirs_nominal_high_",1)
        require(np.allclose(filtered[name],complete[target],equal_nan=True),f"VIIRS filtrat neconcordant: {target}")
    for table,policy in [(main,"strict"),(sensitivity,"justified")]:
        expected=build_matrix(complete,ndvi_policy=policy)
        require(table.columns.equals(expected.columns),"Ordine/coloane X diferite de contract")
        for name in table:
            if pd.api.types.is_numeric_dtype(table[name]):
                require(np.allclose(table[name],expected[name],equal_nan=True),f"X diferă de alinierea pe sursă: {name}")
            else:
                require(table[name].equals(expected[name]),f"Dată X diferită de sursă: {name}")
        for name in FEATURES:
            require(table[f"{name}_missing"].eq(table[name].isna().astype(int)).all(),"Flag lipsă inconsistent")
        require((table.era5_observation_date==table.date-pd.Timedelta(days=1)).all(),"ERA5 nu este D−1")
        for label in ["ndvi","lst"]:
            end=table[f"{label}_composite_end_exclusive"]
            present=end.notna()
            require((end[present]<=table.date[present]).all(),"Compozit cu date viitoare în X")
    # Verificare independentă, explicită a decalajului, inclusiv lipsa inițială.
    lookup=complete.set_index("date")
    for name in ERA_FEATURES:
        values=lookup[name].reindex(main.date-pd.Timedelta(days=1)).to_numpy()
        require(np.allclose(main[name],values,equal_nan=True),f"Decalaj ERA5 incorect: {name}")
    stats=pd.read_csv(root/"statistici_descriptive.csv")
    expected=descriptive_statistics(tables)
    require(list(zip(stats.table,stats.variable))==list(zip(expected.table,expected.variable)),"Statistici lipsă/duplicate")
    for column in ["n_total","n_valid","n_missing","missing_pct","mean","median","std","min","q25","q50","q75","max"]:
        require(np.allclose(stats[column],expected[column],equal_nan=True),f"Statistici neconcordante: {column}")
    require((stats.n_valid+stats.n_missing==stats.n_total).all(),"Bilanț observații greșit")
    dictionary=pd.read_csv(root/"dictionar_variabile.csv")
    expected_keys={(t,n) for t,f in tables.items() for n in f}
    require(set(zip(dictionary.table,dictionary.variable))==expected_keys and len(dictionary)==len(expected_keys),"Dicționar incomplet")
    for table_name,folder in [("X_principal",root),("X_sensibilitate",root/"sensibilitate_NDVI")]:
        frame=tables[table_name]
        rho=pd.read_csv(folder/"matrice_corelatii.csv",index_col=0)
        counts=pd.read_csv(folder/"numar_observatii_corelatii.csv",index_col=0)
        require(list(rho.index)==list(FEATURES) and list(rho.columns)==list(FEATURES),"Corelațiile includ indicatori sau exclud predictori")
        expected_rho,expected_counts=spearman_pairwise(frame[list(FEATURES)])
        require(np.array_equal(counts,expected_counts),"Număr perechi greșit")
        require(np.allclose(rho,expected_rho,equal_nan=True),"Corelații Spearman neconcordante")
        require(np.allclose(rho,rho.T,equal_nan=True),"Corelații asimetrice")
        require((np.abs(rho.to_numpy()[np.isfinite(rho)])<=1+1e-12).all(),"Corelație în afara intervalului")
        cross=pd.read_csv(folder/"corelatii_ERA5_MODIS.csv")
        require(len(cross)==27,"Perechi între surse lipsă")
        for row in cross.itertuples(index=False):
            require(np.isclose(row.spearman_rho,rho.loc[row.era5_variable,row.modis_variable],equal_nan=True),"Top corelații incorect")
            require(row.n_valid_days==counts.loc[row.era5_variable,row.modis_variable],"n incorect în top")
    coverage=pd.read_csv(root/"acoperire_surse.csv")
    expected_coverage=source_coverage(main)
    require(np.allclose(coverage.missing_cells_pct,expected_coverage.missing_cells_pct),"Acoperire pe surse greșită")
    plot_index=pd.read_csv(root/"index_grafice.csv")
    expected_plots={(table,name,kind) for table,frame in tables.items()
                    for name in frame.select_dtypes(include="number") for kind in ["histograme","boxploturi"]}
    actual_plots=set(zip(plot_index.table,plot_index.variable,plot_index.kind))
    require(actual_plots==expected_plots and len(plot_index)==len(expected_plots),"Nu toate variabilele numerice au ambele distribuții")
    require(all((root/"grafice"/name).is_file() for name in plot_index.file.unique()),"Lipsește un PNG referit de index")
    from PIL import Image
    images=list((root/"grafice").glob("*.png"))
    require(len(images)>0,"Lipsesc grafice PNG")
    for path in images:
        with Image.open(path) as image:
            require(min(image.size)>500,f"Grafic prea mic: {path.name}")
            image.verify()
    manifest=json.loads((root/"manifest_CP2.json").read_text(encoding="utf-8"))
    project=Path(__file__).resolve().parent
    for name,digest in manifest["source_sha256"].items():
        require(file_sha256(project/name)==digest,f"Cod schimbat de la generarea CP2: {name}")
    for name,digest in manifest["output_sha256"].items():
        require((root/name).is_file() and file_sha256(root/name)==digest,f"Artefact schimbat/lipsă: {name}")
    expected_png={name for name in manifest["generated_files"] if name.endswith(".png")}
    require({p.relative_to(root).as_posix() for p in images}==expected_png,"PNG suplimentar/lipsă față de inventarul rulării")
    return {"status":"passed","days":len(main),"physical_predictors":len(FEATURES),
            "matrix_csv_columns":len(main.columns),"numeric_statistics_rows":len(stats),
            "png_files_verified":len(images),"distribution_variable_scenarios":len(expected_plots)//2}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("outputs/CP2"))
    print(validate(parser.parse_args().output_dir))


if __name__=="__main__":main()
