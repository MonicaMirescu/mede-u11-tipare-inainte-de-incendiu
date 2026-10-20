# MEDE U11 – Tipare înainte de incendiu (CP1)

**Proiect:** Tipare înainte de incendiu  
**Regiune:** Bejís – Villanueva de Viver, Castellón, Spania  
**Perioadă:** 2020-01-01 – 2024-12-31 (1.827 zile)  
**Unitatea de analiză:** zi × regiune

Pipeline Python pentru **încărcarea, verificarea și alinierea** a trei surse:
- **ERA5-Land** (Copernicus/ECMWF): temperatură, punct de rouă, precipitații, vânt, radiație, umiditatea solului; date orare.
- **VIIRS S-NPP Active Fire C2** (NASA FIRMS): detecții, FRP și date de achiziție.
- **MODIS MOD13Q1.061 NDVI / MOD11A2.061 LST** (NASA AppEEARS): compozite la 16, respectiv 8 zile.

## Cum se rulează

Ai nevoie de Python 3.10+ și de cele trei arhive ZIP originale (neincluse în repo).

```bash
python -m pip install -r requirements.txt
```

Copiază arhivele ZIP nedespachetate în `data/raw/` și asigură-te că numele lor includ **ERA5**, **VIIRS** sau **FIRE**, respectiv **MODIS**. Apoi:

```bash
python run_pipeline.py
python validate_outputs.py
```

Sau rulează cu directoare explicite:

```bash
python run_pipeline.py --input-dir /cale/date/brute --output-dir data/processed
python validate_outputs.py --processed-dir data/processed
```

Scriptul produce `era5_daily.csv`, `viirs_daily.csv`, `modis_daily.csv`, `dataset_aliniat_zilnic.csv`, `raport_acoperire.csv`, `raport_acoperire.md` și `manifest.json`.

## Rezultatele rulării pe datele proiectului

| Verificare | Rezultat |
| --- | ---: |
| Zile în interval | **1.827** |
| Ore ERA5 | **43.848** |
| Puncte ERA5 | **30** |
| Detecții VIIRS | **1.249**, în **24** de zile |
| Compozite MODIS NDVI/LST | **116 / 230** |
| Acoperire ERA5 | **100%** |
| NDVI zilnic disponibil | **1.824/1.827** (99,84%) |
| LST zi / noapte | **1.816 / 1.800** zile |

Vezi raportul din `data/processed/raport_acoperire.md` și `data/processed/manifest.json`. Fișierele CSV complete sunt generate prin rularea scriptului din arhivele originale.

## Reguli și limitări

- ERA5 este agregat zilnic și spațial în cele 30 de puncte; acumulările de precipitații/radiație sunt însumate.
- VIIRS este o **etichetă observațională**, nu predictorul meteorologic; 0 detecții nu înseamnă absența sigură a incendiilor.
- MODIS utilizează indicatorii QA; codul QC=0 la LST este **valid**, nu lipsă.
- Compozitele MODIS sunt folosite conservator numai după sfârșitul ferestrei lor de observație (8/16 zile), pentru a evita folosirea datelor viitoare.
- Rezultatele sunt medii pe întreaga casetă geografică; nu există încă model predictiv, testare temporală, AUC sau baseline. Acestea sunt pentru etapele ulterioare.

## Surse originale

- [Copernicus ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries)
- [NASA FIRMS VIIRS](https://firms.modaps.eosdis.nasa.gov/download/)
- [NASA Earthdata AppEEARS](https://appeears.earthdatacloud.nasa.gov/)

**Notă:** Pipeline-ul este adaptat extragerilor efective pentru regiunea Bejís–Villanueva de Viver (2020–2024), nu reprezintă un model generalizat pentru orice NetCDF.