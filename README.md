# MEDE U11 – Matrice zilnică și analiză descriptivă (CP2)

**Proiect:** Tipare înainte de incendiu  
**Regiune:** Bejís – Villanueva de Viver, Castellón, Spania  
**Perioadă:** 2020-01-01 – 2024-12-31 (1.827 zile)  
**Unitatea de analiză:** zi × regiune

Pipeline Python pentru **încărcarea, verificarea și alinierea** a trei surse:
- **ERA5-Land** (Copernicus/ECMWF): temperatură, punct de rouă, precipitații, vânt, radiație, umiditatea solului; date orare.
- **VIIRS S-NPP Active Fire C2** (NASA FIRMS): detecții, FRP și date de achiziție.
- **MODIS MOD13Q1.061 NDVI / MOD11A2.061 LST** (NASA AppEEARS): compozite la 16, respectiv 8 zile.

## Predare GitHub: verificare fără date brute

Repository-ul include implementarea CP1 corectată, implementarea CP2, tabelele validate și **7 grafice esențiale** din cele 31 generate local. Pentru verificarea pachetului descărcat de pe GitHub, fără arhivele brute:

```bash
python -m pip install -r requirements.txt
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B prepare_publication.py
```

Inventarul exact și hash-urile sunt în [publicatie_CP2.json](outputs/CP2/publicatie_CP2.json). [Ghidul de predare](docs/PREDARE_GITHUB.md) explică selecția, diferența dintre verificarea pachetului și reproducerea integrală, precum și fișierele păstrate exclusiv local. ZIP-urile și NetCDF-urile originale nu sunt publicate.

Rezultatul principal este **X = 1.827 zile × 12 predictori fizici**; exportul are 54 coloane cu tot cu date/indicatori. Lipsurile predictorilor sunt 0,055% ERA5, 0,164% NDVI și 0,876% LST. Sunt păstrate explicit, fără imputare. [Heatmap principal](outputs/CP2/grafice/corelatii_spearman.png), [distribuții](outputs/CP2/grafice/X_principal_predictori_histograme_01.png), [aliniere](outputs/CP2/grafice/aliniere_surse.png), [preview X](outputs/CP2/grafice/preview_matrice_X.png).

## Reproducerea CP2 pe arhivele originale

Ai nevoie de Python 3.10+, dependențele din `requirements.txt` și cele trei arhive originale în `data/raw/`. Nu sunt necesare credențiale sau acces la internet la rulare; metadatele temporale NASA sunt salvate în proiect.

```bash
python -m pip install -r requirements.txt
python -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2
python -X utf8 -B validate_cp2.py --output-dir outputs/CP2
python -X utf8 -B prepare_publication.py --write
```

Comanda CP2 execută testele automate, recitește arhivele prin pipeline-ul corectat, validează sursele și generează toate cele 31 de grafice, apoi verifică fișierele efectiv salvate. `validate_cp2.py` verifică rularea integrală și se folosește după reproducere; pentru subsetul publicat folosește `prepare_publication.py`. Verificările nu se bazează numai pe cifre fixate în README.

În rândul X datat **D**, predictorii ERA5 provin din **D−1**, conform deciziei metodologice pentru analiza informațiilor anterioare zilei investigate. NDVI/LST provin din ultimul compozit cu fereastra încheiată până la D. Prima zi X nu are ERA5 anterior în arhivă și rămâne lipsă; tabelul complet păstrează observațiile originale ale zilei D, inclusiv totalurile incomplete de la 31.12.2024. Nu se impută valori.

X are **12 predictori fizici**: 9 ERA5, NDVI strict și LST zi/noapte. Exportul CSV include și data, proveniența temporală, suportul spațial/vechimea MODIS, completitudinea ERA5 și flag-uri de lipsă. Aceste coloane auxiliare sunt identificate în dicționar și excluse din corelații. VIIRS este păstrat numai în tabelul complet, inclusiv varianta nominal/high; zero detecții nu demonstrează absența incendiului.

Artefactele sunt în [outputs/CP2](outputs/CP2/):

- `matrice_X.csv`, `tabel_aliniat_complet.csv`, `dictionar_variabile.csv`.
- `statistici_descriptive.csv`: toate coloanele numerice din X principal, X de sensibilitate și tabelul complet; n valid/lipsă, medie, mediană, deviație standard de eșantion, minim, cuartile și maxim.
- `acoperire_surse.csv` și `acoperire_variabile.csv`: lipsuri, număr de zile reportate și zero imputări. Procentul pe sursă se calculează numai peste celulele predictorilor fizici: zile × numărul predictorilor acelei surse.
- `matrice_corelatii.csv`, `numar_observatii_corelatii.csv`, `corelatii_ERA5_MODIS.csv`: Spearman și numărul zilelor valide pe fiecare pereche; clasamentul dintre surse folosește |ρ|.
- `grafice/`: pe GitHub sunt publicate histogramele/boxploturile predictorilor principali, heatmap Spearman cu n, heatmap al numărului de zile, heatmap de sensibilitate NDVI, tabel de aliniere și preview X. Rularea integrală generează suplimentar distribuțiile tuturor indicatorilor/scenariilor. `index_grafice.csv` indică paginile rulării integrale; cele 24 de PNG-uri suplimentare sunt locale/regenerabile.
- `sensibilitate_NDVI/`: aceeași analiză cu NDVI marginal justificat; comparația corelațiilor este în `sensibilitate_ndvi_corelatii.csv`. Analiza principală rămâne strictă.
- [metodologie_CP2.md](outputs/CP2/metodologie_CP2.md), `manifest_CP2.json`, `validare_CP2.json` și jurnalul testelor. `surse_corectate/` păstrează rezultatele ingestiei reale folosite în această rulare.

Spearman se calculează pe observațiile complete ale fiecărei perechi, cu ranguri medii pentru egalități, recalculate după eliminarea lipsurilor. Indicatorii de QA/vechime și VIIRS nu intră în matricea principală de corelații. Distribuțiile și n sunt zilnice; valorile MODIS reportate nu sunt achiziții independente. Corelațiile nu sunt ajustate pentru sezonalitate și nu demonstrează cauzalitate sau un semnal specific incendiilor. Nu s-au implementat PCA, scree plot, clustering sau modele predictive.

## Reproducerea corecțiilor CP1 (istoric validat)

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

Tabelul `dataset_aliniat_zilnic.csv` rămâne tabelul de aliniere CP1, cu coloane VIIRS observaționale. Matricea X și analiza CP2 se generează separat, prin comenzile de mai sus. Rapoartele din `data/processed/` rămân istorice CP1 și nu descriu rularea corectată.

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

Deciziile corecțiilor sunt descrise în [metodologia CP1](docs/METODOLOGIE_CORECTII.md). Corecțiile validate sunt salvate în commit-ul `5671125`, pe `cp2-corectii-pipeline`; implementarea CP2 pornește de aici pe `cp2-matrice-statistici`. Predarea se propune prin Pull Request către `main`, fără îmbinare automată. Datele brute rămân excluse din git.
