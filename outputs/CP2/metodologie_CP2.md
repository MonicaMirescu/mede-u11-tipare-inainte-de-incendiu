# MEDE U11 · Metodologie CP2 și rezultate reale

[Repository proiect](https://github.com/MonicaMirescu/mede-u11-tipare-inainte-de-incendiu). Artefacte locale pentru revizuire; nu au fost publicate prin această rulare.

## Unitate și matrice

Unitatea este zi × regiune, Bejís–Villanueva de Viver: 01.01.2020–31.12.2024, 1827 zile consecutive. BBOX: lat 39,7…40,2; lon −1,0…−0,4.
X fizic are **1827 × 12** predictori. `matrice_X.csv` are 54 coloane în total: data, 12 predictori, indicatori de lipsă/QA/acoperire și proveniență temporală. Sunt 46 coloane numerice în export; numai cele 12 cu rol predictor intră în corelația principală. Ordinea este ERA5, NDVI, LST. Dicționarul indică rolul, unitatea și alinierea fiecărei coloane pentru fiecare tabel/scenariu.
Selecția descrie starea termică a aerului, umezeala atmosferică și a solului, precipitațiile, energia solară, vântul, vegetația și temperatura suprafeței. Mediile și maximele temperaturii/vântului păstrează atât nivelul zilnic, cât și episodul orar cel mai intens. Selecția este fizică, fără alegerea variabilelor după detecțiile VIIRS; variabilele corelate rămân vizibile în această etapă descriptivă.
Tabelul aliniat complet păstrează datele ERA5 ale zilei D, toate coloanele MODIS, detecțiile VIIRS complete și varianta VIIRS nominal/high. VIIRS este separat de predictorii X. Zero detecții nu este dovadă de absență a incendiului.

## Geografie și agregare regională

ERA5: grilă regulată de 0,1°, 5×6=30 centre efectiv extrase: lat 39,7…40,1 și lon −1,0…−0,5. Coordonatele sunt validate între fișiere, după unități, unicitate, monotonie, pas și apartenență la BBOX. Se face media aritmetică pe cele 30 de puncte la fiecare oră; o celulă lipsă nu este ascunsă prin schimbarea suportului regional. Nu inventăm centre pe marginile nordică/estică și nu efectuăm o nouă interpolare spațială.
MODIS: exportul AppEEARS este deja reproiectat în WGS84/EPSG:4326 prin nearest-neighbour, conform README-ului arhivei. Selectăm centrele din BBOX: 240×288=69.120 pixeli NDVI și 60×72=4.320 pixeli LST. Media este pe pixelii care trec QA. Rezoluțiile nominale ale produselor sunt 250 m/1 km; grila geografică exportată nu are aceeași arie fizică pentru fiecare pixel. Mediile sunt neponderate; nu reprezintă integrarea exactă pe aria BBOX și nu se pretinde un grid comun de pixeli între surse.

## ERA5: ore, unități și D−1

Temperatura și punctul de rouă se convertesc K→°C prin scăderea lui 273,15. Umiditatea relativă se calculează pe celulă/oră cu formula Magnus din pipeline-ul validat (coeficienți 17,625 și 243,04), se limitează la 0–100%, apoi se mediază regional și zilnic. Viteza vântului este sqrt(u²+v²) pe celulă/oră, apoi media regională; unitatea rămâne m/s. Umiditatea solului din stratul 0–7 cm rămâne m³/m³.
Mediile zilnice folosesc orele 00:00–23:00 UTC pentru variabilele instantanee. Maximele temperaturii și vântului sunt maximele mediei regionale orare, nu maximele tuturor celulelor și nici rafale observate.
Precipitația tp și radiația ssrd din produsul ERA5-Land time-series sunt deja dezacumulate. Valoarea la t acoperă ora încheiată la t: totalul zilei D folosește D 01:00…D+1 00:00. Conversii: m×1000→mm; J/m²÷10⁶→MJ/m². Nu diferențiem încă o dată. Un total este prezent numai cu 24 intervale valide; suma parțială, numărul de intervale și completitudinea sunt păstrate separat în tabelul complet/surse. Reziduurile negative minuscule sunt controlate și limitate la zero în toleranțele CP1 documentate, nu folosite pentru imputare.
**În X datat D folosim exclusiv ERA5 din D−1**, prin join pe data calendaristică, inclusiv pentru indicatorii de completitudine. Aceasta este alegerea confirmată de utilizatoare: informațiile din orele ulterioare unei detecții din D nu intră în rândul D. Nu schimbăm data observațiilor din tabelul complet. Pentru prima zi X lipsește ERA5 din 31.12.2019: toți cei 9 predictori ERA5 sunt NaN. Pentru completare ar fi necesare variabilele instantanee ale acelei zile și tp/ssrd din 31.12.2019 01:00…01.01.2020 00:00, din aceeași sursă și pe aceeași grilă.
[Documentație ECMWF pentru dezacumulare](https://confluence.ecmwf.int/pages/viewpage.action?pageId=627854124).

## MODIS: QA și ferestre efective

NDVI principal: reliability=0, MODLAND=0, usefulness utilizabil 0…12, teren, fără aerosol ridicat, nor adiacent/mixt, zăpadă sau umbră. Fill și valorile brute în afara intervalului −2000…10000 sunt respinse; factorul este 0,0001. Sensibilitatea adaugă numai reliability=1 cu MODLAND=0/1 și aceleași verificări detaliate. Codurile usefulness 13…15 sunt inutilizabile. Nu eliminăm arbitrar codurile intermediare prezente în export. [Ghid MOD13 C6.1](https://lpdaac.usgs.gov/documents/621/MOD13_User_Guide_V61.pdf).
LST zi/noapte: temperatura brută validă, biții obligatorii QC=00 și interval fizic 200–360 K din pipeline-ul validat; QC=0 este valid, temperatura brută 0 este fill. Conversie: brut×0,02−273,15→°C. Numărul/procentul pixelilor acceptați are ca numitor toate centrele selectate în BBOX. Nu s-a aplicat un prag minim arbitrar de acoperire. Sensibilitatea la pragurile spațiale ipotetice rămâne în `surse_corectate/modis_coverage_sensitivity.csv`.
Limitele temporale sunt citite din time bounds dacă există; pentru aceste fișiere, care nu au bounds, se utilizează extrasul NASA CMR versionat în metadata/modis_composite_periods.json, cu dovezi pentru fiecare dată pe două tile-uri de referință. LST are ferestre de 8 zile și ultima fereastră anuală de 5/6 zile; NDVI de sfârșit de an poate traversa anul. Nu deducem durata din distanța până la următorul compozit, fiindcă ar confunda o înregistrare lipsă cu o fereastră mai lungă. Unitățile/calendarul NetCDF sunt controlate explicit.

## Propagare, vechime și goluri

Pentru ziua D folosim ultimul compozit cu sfârșitul exclusiv al ferestrei ≤ D, prin căutare în trecut `merge_asof`. Valoarea este reportată ca o constantă între actualizări; aceasta este propagare temporală, nu interpolare liniară între două valori și nu observație zilnică nouă. Nu se folosesc compozite din viitor. Limitele CP1 rămân explicit 32 zile NDVI / 16 zile LST după închiderea ferestrei, fără a pretinde că sunt praguri optime.
`*_age_days` este vârsta față de ultima zi a ferestrei (1 la prima alocare); `*_carry_days` este timpul de la prima alocare permisă (0 inițial); `*_is_carried` indică repetarea după acea primă alocare. Vârsta ferestrei nu este data exactă de achiziție a fiecărui pixel. `available_from` înseamnă închiderea ferestrei, nu data reală a publicării istorice; analiza nu simulează disponibilitatea operațională a produselor.
Un compozit existent fără pixeli valizi produce NaN, fără a recupera pe ascuns un compozit mai vechi. Dacă lipsește înregistrarea, se poate reporta precedentul în limita documentată; de exemplu lipsește LST 16.10.2022. NDVI nu este disponibil în primele 3 zile, fiindcă prima fereastră extrasă se încheie pe 03.01.2020. Flag-urile de lipsă descriu NaN, fără să-l înlocuiască.
În tabelul complet, 31.12.2024 are numai 23 intervale pentru tp/ssrd; totalurile sunt NaN, iar sumele parțiale sunt păstrate. Sunt necesare tp și ssrd la 01.01.2025 00:00 UTC pe aceeași grilă. În X, ultimul rând folosește ERA5 din 30.12.2024 și nu preia totalurile incomplete ale zilei 31.12.2024.

## Acoperire măsurată în X

Sunt 44 celule lipsă dintre 21924 celule ale predictorilor fizici. Procentele de mai jos folosesc ca numitor zile×numărul predictorilor din sursă; nu includ indicatorii auxiliari. Nu confundăm procentul celulelor lipsă cu procentul zilelor având cel puțin o lipsă.

| source | n_predictors | n_missing_cells | n_cells | missing_cells_pct | days_with_any_missing |
|---|---|---|---|---|---|
| ERA5-Land | 9 | 9 | 16443 | 0.0547345 | 1 |
| MODIS NDVI | 1 | 3 | 1827 | 0.164204 | 3 |
| MODIS LST | 2 | 32 | 3654 | 0.875753 | 24 |

## Statistici descriptive și grafice

`statistici_descriptive.csv` are 151 rânduri: fiecare coloană numerică din X principal, X de sensibilitate și tabelul complet. Include n valid/lipsă, medie, mediană, deviație standard de eșantion (ddof=1), minim, Q1/Q2/Q3 cu interpolare liniară a cuantilelor și maxim. Datele/șirurile nu sunt tratate ca numere. O variabilă fără valori valide are statistici NaN, fără valori inventate.
Histogramele și boxploturile sunt paginate, cu axe/unități proprii fiecărei variabile; nu comparăm direct pe aceeași axă temperaturi, NDVI și număr de detecții. Boxploturile folosesc mustăți de 1,5×IQR; punctele exterioare sunt afișate și păstrate în calcule. Histogramele folosesc 35 de intervale sau bare discrete pentru ≤5 valori distincte. `index_grafice.csv` leagă fiecare variabilă/scenariu de ambele grafice. Distribuțiile MODIS sunt ale valorilor zilnice reportate, nu ale unor achiziții independente.

## Spearman și perechi valide

Corelațiile includ numai cei 12 predictori fizici. Pentru fiecare pereche se elimină numai zilele în care unul dintre cei doi lipsește, apoi se recalculează rangurile pe pereche, cu rang mediu la egalități. Spearman este corelația Pearson a acestor ranguri. Se raportează separat numărul zilelor comune în `numar_observatii_corelatii.csv`, inclusiv pe diagonală. Pentru mai puțin de două valori sau o variabilă constantă corelația este NaN. Nu se înlocuiește o corelație nedefinită cu zero.
Spearman descrie asocieri monotone fără a presupune normalitatea variabilelor; este potrivit descriptiv inclusiv pentru precipitații asimetrice și multe egalități. Nu reprezintă ajustare pentru sezonalitate, tendințe sau dependență temporală. Compozitele reportate reduc numărul efectiv de observații independente: n este număr de zile, nu eșantion independent. Nu calculăm p-value și nu interpretăm corelația drept cauzalitate sau dovadă a unui semnal specific incendiilor. [Definiția Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html), [observații complete pe pereche](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.corr.html).

Cele mai mari 5 corelații între ERA5 din D−1 și MODIS, ordonate după |ρ|; perechile din aceeași sursă sunt excluse din acest clasament:

| era5_variable | modis_variable | spearman_rho | n_valid_days |
|---|---|---|---|
| temperature_mean_c | lst_day_mean_c | 0.90343 | 1818 |
| temperature_mean_c | lst_night_mean_c | 0.889801 | 1802 |
| temperature_max_c | lst_day_mean_c | 0.868775 | 1818 |
| temperature_max_c | lst_night_mean_c | 0.843421 | 1802 |
| dewpoint_mean_c | lst_night_mean_c | 0.792801 | 1802 |

## Sensibilitate NDVI și VIIRS

În `sensibilitate_NDVI/` se repetă X și corelațiile cu politica marginală justificată. Numai NDVI și indicatorii săi de suport/vechime se schimbă; ERA5 și LST păstrează exact aceeași aliniere. Comparația perechilor este în `sensibilitate_ndvi_corelatii.csv`. Nu selectăm retrospectiv politica care produce corelații mai mari.
VIIRS complet: 1249 detecții în 24 zile. Low: 64. Varianta n/h: 1185 detecții în 23 zile. Acestea nu sunt numere de incendii distincte. Acoperirea observațională nu poate fi dedusă din acest CSV de detecții. Suma FRP peste achiziții nu este energie zilnică sau putere regională simultană.

## Reproducere și validare

```bash
python -m pip install -r requirements.txt
python -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2
python -X utf8 -B validate_cp2.py --output-dir outputs/CP2
```

Rularea curentă a executat 31 teste automate pe fixture-uri sintetice și calendarul NASA salvat, apoi pipeline-ul corectat pe arhivele originale. Hash-urile arhivelor, metadatelor și codului, versiunile bibliotecilor și inventarul artefactelor sunt în `manifest_CP2.json`. Rezultatul verificării fișierelor efectiv salvate este în `validare_CP2.json`.
Nu s-au executat PCA, scree plot, clustering sau modele predictive. Pentru etapele ulterioare rămân de discutat validarea temporală, disponibilitatea operațională reală a produselor și calitatea reprezentării regionale la suport spațial redus.

## Fișiere generate

- `acoperire_surse.csv`
- `acoperire_variabile.csv`
- `corelatii_ERA5_MODIS.csv`
- `dictionar_variabile.csv`
- `grafice/X_principal_indicatori_boxploturi_01.png`
- `grafice/X_principal_indicatori_boxploturi_02.png`
- `grafice/X_principal_indicatori_boxploturi_03.png`
- `grafice/X_principal_indicatori_histograme_01.png`
- `grafice/X_principal_indicatori_histograme_02.png`
- `grafice/X_principal_indicatori_histograme_03.png`
- `grafice/X_principal_predictori_boxploturi_01.png`
- `grafice/X_principal_predictori_histograme_01.png`
- `grafice/X_sensibilitate_indicatori_boxploturi_01.png`
- `grafice/X_sensibilitate_indicatori_boxploturi_02.png`
- `grafice/X_sensibilitate_indicatori_boxploturi_03.png`
- `grafice/X_sensibilitate_indicatori_histograme_01.png`
- `grafice/X_sensibilitate_indicatori_histograme_02.png`
- `grafice/X_sensibilitate_indicatori_histograme_03.png`
- `grafice/X_sensibilitate_predictori_boxploturi_01.png`
- `grafice/X_sensibilitate_predictori_histograme_01.png`
- `grafice/aliniat_complet_toate_numerice_boxploturi_01.png`
- `grafice/aliniat_complet_toate_numerice_boxploturi_02.png`
- `grafice/aliniat_complet_toate_numerice_boxploturi_03.png`
- `grafice/aliniat_complet_toate_numerice_boxploturi_04.png`
- `grafice/aliniat_complet_toate_numerice_boxploturi_05.png`
- `grafice/aliniat_complet_toate_numerice_histograme_01.png`
- `grafice/aliniat_complet_toate_numerice_histograme_02.png`
- `grafice/aliniat_complet_toate_numerice_histograme_03.png`
- `grafice/aliniat_complet_toate_numerice_histograme_04.png`
- `grafice/aliniat_complet_toate_numerice_histograme_05.png`
- `grafice/aliniere_surse.png`
- `grafice/corelatii_sensibilitate_ndvi.png`
- `grafice/corelatii_spearman.png`
- `grafice/numar_observatii_corelatii.png`
- `grafice/preview_matrice_X.png`
- `index_grafice.csv`
- `manifest_CP2.json`
- `matrice_X.csv`
- `matrice_corelatii.csv`
- `metodologie_CP2.md`
- `numar_observatii_corelatii.csv`
- `sensibilitate_NDVI/corelatii_ERA5_MODIS.csv`
- `sensibilitate_NDVI/matrice_X.csv`
- `sensibilitate_NDVI/matrice_corelatii.csv`
- `sensibilitate_NDVI/numar_observatii_corelatii.csv`
- `sensibilitate_ndvi_corelatii.csv`
- `statistici_descriptive.csv`
- `surse_corectate/dataset_aliniat_zilnic.csv`
- `surse_corectate/era5_daily.csv`
- `surse_corectate/era5_incomplete_days.csv`
- `surse_corectate/lst_composites.csv`
- `surse_corectate/manifest.json`
- `surse_corectate/modis_coverage_sensitivity.csv`
- `surse_corectate/modis_daily.csv`
- `surse_corectate/ndvi_composites.csv`
- `surse_corectate/ndvi_qa_comparison.csv`
- `surse_corectate/raport_acoperire.csv`
- `surse_corectate/raport_acoperire.md`
- `surse_corectate/viirs_daily.csv`
- `surse_corectate/viirs_daily_nominal_high.csv`
- `tabel_aliniat_complet.csv`
- `teste_automate.log`
- `validare_CP2.json`
