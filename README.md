# MEDE U11 – CP1 corectat metodologic, înainte de CP2

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

Copiază arhivele ZIP nedespachetate în `data/raw/`; numele trebuie să includă **ERA5**, **VIIRS** sau **DL_FIRE**, respectiv **MODIS**. Trebuie să existe exact o arhivă pentru fiecare sursă. Rularea corectată, fără a suprascrie rapoartele istorice CP1:

```bash
python -X utf8 -B run_pipeline.py --input-dir data/raw --output-dir outputs/corectii_pipeline/dupa
python -X utf8 -B validate_outputs.py --processed-dir outputs/corectii_pipeline/dupa
python -X utf8 -B -m unittest discover -s tests -v
```

Pentru comparația reproductibilă ÎNAINTE/DUPĂ pe aceleași arhive:

```bash
python -X utf8 -B compare_pipeline.py --input-dir data/raw --output-dir outputs/corectii_pipeline
```

Comparația execută testele automate, CP1 din commit-ul fix `e0c34bc071712bd77f96f94ee88f801d06fafc57` și codul curent, apoi validează rezultatele corectate. Nu schimbă ramura și nu necesită internet. Comparația folosește valorile în memorie, înaintea rotunjirii CSV; toleranța numerică este 1e-10. Se poate specifica alt commit cu `--baseline-ref`.

Artefacte în `outputs/corectii_pipeline/`:

- [Raport comparativ în română](outputs/corectii_pipeline/raport_comparativ.md), `comparatie_variabile.csv` și `diferente_zilnice.csv`.
- `inainte/`: rezultate CP1 reproduse din commit-ul de referință.
- `dupa/`: aceleași tabele zilnice CP1 corectate, acoperire per variabilă, `manifest.json`, compozite cu limite temporale, comparație QA NDVI, sensibilitatea acoperirii și zile ERA5 incomplete.
- `dupa/viirs_daily.csv`: toate detecțiile, cu număr low separat; `dupa/viirs_daily_nominal_high.csv`: varianta filtrată.
- `comparatie_manifest.json`: commit de referință, hash-uri SHA-256 ale arhivelor și metadatelor, reguli și rezultate măsurate.

Tabelul `dataset_aliniat_zilnic.csv` rămâne tabelul de aliniere CP1. Nu este matricea de predictori X; coloanele VIIRS sunt observaționale. Nu s-au implementat statisticile, figurile, PCA sau modelele CP2. Rapoartele din `data/processed/` rămân istorice CP1 și nu descriu rularea corectată.

## Rezultatele reale după corecții

| Verificare | Rezultat |
| --- | ---: |
| Zile în interval | **1.827** |
| Ore ERA5 | **43.848** |
| Puncte ERA5 | **30** |
| Detecții VIIRS | **1.249**, în **24** de zile |
| Compozite MODIS NDVI/LST | **116 / 230** |
| ERA5 instantaneu | **1.827/1.827** zile |
| Totaluri ERA5 complete, precipitații și radiație | **1.826/1.827** zile fiecare |
| NDVI strict / marginal justificat | **1.824 / 1.824** zile |
| LST zi / noapte | **1.819 / 1.803** zile |
| VIIRS nominal/high | **1.185** detecții în **23** zile; **64** low păstrate separat |

Valorile și zilele schimbate sunt cuantificate în raportul comparativ. Disponibilitatea zilnică MODIS include reutilizarea compozitelor; nu înseamnă achiziții zilnice independente.

## Reguli și limitări

- ERA5 time-series este deja dezacumulat: valoarea la ora t reprezintă intervalul încheiat la t. Pentru totalul unei zile UTC folosim 01:00–00:00 din ziua următoare. Nu diferențiem din nou. Totalurile incomplete sunt NaN; `*_partial_*`, `*_interval_hours` și `*_complete` păstrează informația disponibilă.
- La 31.12.2024 lipsesc intervalele finale de precipitație și radiație. Este necesar **tp și ssrd la 01.01.2025 00:00 UTC**, din aceeași sursă și pe aceeași grilă. Nu s-au imputat valori.
- Umiditatea relativă se calculează pe fiecare celulă și oră, apoi se mediază regional și zilnic. Grilele ERA5 se validează după coordonate, unități, BBOX și pas de 0,1°, între toate fișierele.
- VIIRS este o **etichetă observațională**, nu predictorul meteorologic; 0 detecții nu înseamnă absența sigură a incendiilor.
- MODIS utilizează indicatorii QA; codul QC=0 la LST este **valid**, nu lipsă.
- Ferestrele MODIS vin din time bounds, dacă există, altfel din [extrasul NASA CMR](metadata/modis_composite_periods.json). LST de sfârșit de an are 5/6 zile; NDVI poate traversa anul. `available_from` înseamnă închiderea ferestrei observațiilor, fără a presupune publicarea efectivă la acea dată.
- NDVI: politica strictă este implicită; marginalele sunt oferite separat și acceptate doar după QA detaliat. Nu aplicăm prag minim de pixeli. Efectul pragurilor ipotetice asupra acoperirii este publicat separat, fără filtrare suplimentară.
- MODIS păstrează numărul/procentul pixelilor și vechimea. `*_age_days` este vârsta față de ultima zi a ferestrei (minim 1), `*_carry_days` timpul de la prima alocare permisă (minim 0). Nu cunoaștem ziua exactă de achiziție a fiecărui pixel. Plafonul CP1 de propagare rămâne 32 zile NDVI / 16 zile LST după sfârșitul ferestrei; nu se face interpolare liniară.
- Rezultatele sunt medii pe întreaga casetă geografică; nu există încă model predictiv, testare temporală, AUC sau baseline. Acestea sunt pentru etapele ulterioare.

## Surse originale

- [Copernicus ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries)
- [NASA FIRMS VIIRS](https://firms.modaps.eosdis.nasa.gov/download/)
- [NASA Earthdata AppEEARS](https://appeears.earthdatacloud.nasa.gov/)

**Notă:** Pipeline-ul este adaptat extragerilor efective pentru regiunea Bejís–Villanueva de Viver (2020–2024), nu reprezintă un model generalizat pentru orice NetCDF.

Deciziile, indicatorii și limitele sunt descrise în [metodologia corecțiilor](docs/METODOLOGIE_CORECTII.md). Datele brute rămân excluse din git. Modificările sunt locale pe `cp2-corectii-pipeline`, pentru revizuire înaintea oricărui push.
