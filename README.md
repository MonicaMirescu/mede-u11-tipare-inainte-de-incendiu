# MEDE U11 — Tipare înainte de incendiu

[Repository public](https://github.com/MonicaMirescu/mede-u11-tipare-inainte-de-incendiu/tree/main)

Analiza combină meteorologia locală, observații satelitare și indici de circulație atmosferică pentru regiunea Bejís–Villanueva de Viver, Castellón, Spania, în perioada **01.01.2020–31.12.2024**. README centralizează documentația proiectului, de la definirea problemei și surselor până la alinierea datelor și compararea reprezentărilor PCA/UMAP.

## Cuprins

1. [Proiectul și întrebarea de cercetare](#proiect)
2. [Unitatea de analiză](#unitate)
3. [Surse, proveniență și versiuni](#surse)
4. [Metodologia CP1–CP2](#cp2)
5. [Metodologia CP3](#cp3)
6. [Protocolul experimental CP3](#protocol)
7. [Rezultate principale](#rezultate)
8. [Limitări metodologice](#limite)
9. [Structura repository-ului](#structura)
10. [Instalare, reproducere și validare](#reproducere)

<a id="proiect"></a>
## 1. Proiectul și întrebarea de cercetare

**Ce tipare meteorologice și satelitare apar în zilele care preced incendiile într-o regiune?** CP0 definește problema și sursele, CP1 pregătește și verifică datele, CP2 le aliniază și descrie statistic, iar CP3 compară o reprezentare liniară PCA cu alternativa neliniară UMAP.

Rezultatele CP3 descriu fidelitatea reprezentării datelor. Nu constituie încă o demonstrație a unor tipare specifice pre-incendiu: VIIRS este păstrat separat, fără selecția zilelor sau antrenarea modelelor după incendii. Nu sunt implementate clasificare, clustering sau modele predictive.

<a id="unitate"></a>
## 2. Unitatea de analiză

Unitatea este **zi × regiune**: o singură serie temporală multivariată, cu **1827 de zile** și regiune fixă. BBOX: latitudine **39,7–40,2° N**, longitudine **−1,0…−0,4°**. Nu analizăm un panel de regiuni sau pixeli independenți. Calendarul este zilnic, în UTC; zilele succesive sunt dependente temporal.

CP2 are 12 predictori fizici; CP3 adaugă NAO și AO, ajungând la 14. Data, QA, acoperirea, vechimea, indicatorii de lipsă și VIIRS sunt informații auxiliare sau observații separate, fără a intra în PCA/UMAP.

<a id="surse"></a>
## 3. Surse, proveniență și versiuni

| Sursă | Produs și suport | Proveniență păstrată |
|---|---|---|
| ERA5-Land | Reanaliză orară, grilă 0,1°; temperatură, punct de rouă, vânt, precipitații, radiație și umiditatea solului 0–7 cm | ZIP original; nume, hash și auditul ingestiei în `outputs/CP2/manifest_CP2.json` |
| MODIS NDVI | MOD13Q1.061, rezoluție nominală 250 m; compozite și QA detaliat | Export AppEEARS NetCDF în ZIP; ferestre verificate în metadatele NASA CMR versionate |
| MODIS LST | MOD11A2.061, rezoluție nominală 1 km; zi/noapte | Același mecanism; fereastra de la sfârșitul anului poate avea 5/6 zile |
| VIIRS | S-NPP Active Fire C2, detecții punctuale și FRP | ZIP original; verificarea BBOX, calendarului și încrederii în auditul CP2 |
| NOAA CPC NAO/AO | Indici zilnici observaționali istorici CDAS, familia `norm.daily.*.cdas`, adimensionali | Două snapshoturi CSV și `data/CP3_NOAA/provenienta_NOAA.json` |

Arhivele originale ERA5/MODIS/VIIRS nu sunt distribuite în Git. Identitatea exactă a intrărilor și hash-urile produselor sunt în manifestele JSON; nu se atribuie reanalizei o versiune de arhivă neînregistrată. Documentații de origine: [ERA5-Land time-series](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries), [MOD13 C6.1 QA](https://lpdaac.usgs.gov/documents/621/MOD13_User_Guide_V61.pdf), [VIIRS FIRMS](https://firms.modaps.eosdis.nasa.gov/download/).

### Metadate MODIS

`metadata/modis_composite_periods.json` este un extras real din [NASA CMR](https://cmr.earthdata.nasa.gov/search/), cu **116 date NDVI și 230 date LST** confirmate pe tile-urile de referință h17v04/h17v05. Fiecare intrare păstrează începutul, sfârșitul exclusiv, identificatorii granulelor/conceptelor, sfârșitul inclusiv original, interogarea și linkurile metadata. Sfârșitul exclusiv este `time_end` NASA + o secundă. Rularea nu consultă automat metadate noi și refuză să ghicească limite pentru date inexistente în extras.

Tile-urile de referință verifică calendarul produselor. Ele nu înlocuiesc fișierul AppEEARS granule-list, absent din ZIP-ul local, și nu certifică lista completă originală de granule ale extracției. Pentru alte perioade sunt necesare metadate NASA actualizate sau time bounds explicite în NetCDF.

### Snapshoturi NOAA

Sursele oficiale efectiv utilizate sunt [NAO CDAS, 500 hPa](https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv) și [AO CDAS, 1000 hPa](https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv). Descărcarea este înregistrată la **15.11.2026, 17:39 UTC**. Fiecare snapshot are **1833 rânduri**, din **25.12.2019 până la 30.12.2024**, fără lipsuri sau coduri speciale în intervalul utilizat.

Conform [metodologiei NOAA CPC](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/history/method.shtml), NAO folosește RPCA la 500 hPa, 20–90° N, referința 1950–2000 și tipare lunare interpolate zilnic; AO folosește proiecția anomaliilor la 1000 hPa pe primul EOF, cu referința și normalizarea 1979–2000. Indicii sunt normalizați de furnizor. Standardizarea experimentală ulterioară se învață separat, numai pe train.

| Indice | Fișier snapshot | SHA-256, text cu CRLF→LF |
|---|---|---|
| NAO | `nao_cdas_20191225_20241230.csv` | `1af6f7402e548a0773a2cd04fe83c5240c4559c415cc64c461f2f718156b2f6d` |
| AO | `ao_cdas_20191225_20241230.csv` | `5023c426d42912688d309c7a14c2846666b44db5fdca5c8ca89e9eddb8e01c0c` |

Proveniența JSON distinge hash-ul sursei complete descărcate de hash-ul snapshotului. NAO complet are două lipsuri în afara intervalului folosit; AO complet nu are lipsuri. Nu se amestecă CDAS cu CORE și nu se folosesc prognoze GFS/GEFS. Anunțul NOAA privind schimbarea produselor și documentațiile fiecărui indice sunt păstrate în proveniență. Snapshoturile nu sunt înlocuite automat la rulare.

Parserul verifică antetele `year,month,day,nao_index_cdas` / `ao_index_cdas`, calendarul, ordinea, duplicatele și valorile numerice. Respinge câmpurile necunoscute și infinitul. Golurile și codurile speciale −999, −9999, 9999, −99999, 99999 sau modul ≥10¹⁰ rămân NaN, fără completare.

<a id="cp2"></a>
## 4. Metodologia CP1–CP2

### Grid și agregare regională

| Sursă | Suport spațial efectiv | Agregare și aliniere |
|---|---|---|
| ERA5-Land | 5×6 = 30 centre; lat 39,7…40,1 / lon −1,0…−0,5; pas 0,1° | Media aritmetică regională orară, apoi zi UTC; în X datat D intră ziua D−1 |
| NDVI | AppEEARS WGS84/EPSG:4326, 240×288 = 69.120 centre în BBOX | Media pixelilor QA strict; ultimul compozit încheiat până la D |
| LST | AppEEARS WGS84/EPSG:4326, 60×72 = 4.320 centre în BBOX | Medii QA distincte zi/noapte; aceeași regulă de disponibilitate |
| VIIRS | Detecții punctuale în BBOX | Număr detecții și FRP zilnic UTC; numai în tabelul complet |

Exportul AppEEARS folosește reproiectare nearest-neighbour conform arhivei. Pipeline-ul nu introduce o nouă interpolare spațială pe o grilă comună. Sursele sunt reunite la nivelul regiunii; pixelii și suportul QA pot diferi. Mediile nu sunt ponderate pe aria pixelilor. Cititorul ERA5 verifică unitățile geografice, unicitatea, monotonia, pasul, BBOX și concordanța coordonatelor între fișiere; nu inventează centre la marginile BBOX.

### ERA5: zi UTC, conversii și D−1

Temperatura și punctul de rouă se convertesc prin K−273,15 în °C. Umiditatea relativă se calculează întâi **pe celulă și oră**, apoi se mediază regional și zilnic: `RH = 100 × exp(17,625 Td/(243,04+Td) − 17,625 T/(243,04+T))`, cu T/Td în °C și rezultat limitat la 0–100%. Vântul este `sqrt(u²+v²)` pe celulă/oră, apoi media regională, în m/s. Umiditatea solului este în m³/m³.

Mediile zilnice folosesc orele 00:00–23:00 UTC. Maximele temperaturii și vântului sunt maximele **mediei regionale orare**, fără a reprezenta extremele celulelor sau rafalele.

Precipitațiile și radiația sunt **deja dezacumulate**. Timestamp-ul încheie intervalul orar: totalul zilei D folosește **D 01:00…D+1 00:00**, fără o nouă diferențiere, conform convenției [ERA5-Land time-series](https://confluence.ecmwf.int/pages/viewpage.action?pageId=627854124). Conversii: m×1000→mm; J/m²÷10⁶→MJ/m². Sunt necesare 24 intervale valide; totalul incomplet rămâne NaN, iar suma parțială și numărul de intervale sunt separate. Reziduurile negative minuscule sunt controlate cu toleranțele pipeline-ului.

În X datat **D**, ERA5 provine din **D−1**, prin join calendaristic. Tabelul complet păstrează observațiile zilei D. În prima zi X lipsesc cei 9 predictori ERA5: ar fi necesare datele din 31.12.2019, inclusiv fluxurile 31.12.2019 01:00…01.01.2020 00:00. Pentru totalurile din **31.12.2024**, tabelul complet are numai 23 intervale: lipsesc tp/ssrd la **01.01.2025 00:00 UTC**, din aceeași sursă și grilă. Ultimul rând X folosește 30.12.2024 și nu moștenește acele totaluri incomplete.

### MODIS: QA, ferestre și propagare

NDVI principal folosește filtrarea strictă: reliability=0, MODLAND=0, usefulness utilizabil 0…12, teren, fără aerosol ridicat, nor adiacent/mixt, zăpadă sau umbră. Fill și valorile brute din afara −2000…10000 sunt respinse; conversia este brut×0,0001. Politica marginală justificată, verificată la ingestie, adaugă reliability=1 cu MODLAND=0/1, păstrând controalele detaliate. Nivelurile usefulness 13–15 sunt respinse. Varianta marginală nu intră în matricea principală sau în inventarul publicat.

LST zi/noapte cere biții obligatorii QC=00 și 200–360 K. QC numeric 0 este valid; temperatura brută 0 este fill. Conversia este brut×0,02−273,15 în °C. Nu se impune un prag minim arbitrar al procentului de pixeli: numărul și procentul valid sunt explicite, cu numitor toate centrele din BBOX.

Ferestrele folosesc time bounds, dacă există; în arhivele date, fără bounds, se utilizează extrasul NASA CMR. LST nu are automat 8 zile: ultima fereastră anuală are 5/6 zile; NDVI poate traversa anul. Durata nu este dedusă din următoarea înregistrare. Unitățile temporale sunt citite din fișier. Calendarul AppEEARS `julian` este acceptat numai pentru originea 2000-01-01 și perioada 2000–2099, unde diferențele de timp față de origine coincid cu calendarul gregorian folosit aici; calendarele nesuportate produc eroare.

În ziua D se selectează ultimul compozit cu **sfârșit exclusiv ≤ D**, prin căutare în trecut. Valoarea este propagată constant, fără interpolare liniară sau observații din viitor. Limitele rămân 32 zile NDVI / 16 zile LST după închiderea ferestrei; nu sunt prezentate drept praguri optime. Un compozit fără pixeli QA valizi rămâne NaN, fără recuperarea ascunsă a unuia mai vechi. Dacă lipsește înregistrarea, ca pentru LST 16.10.2022, precedentul poate fi reportat în limita documentată.

`age_days` măsoară zilele față de ultima zi a ferestrei, minimum 1; `carry_days`, zilele de la prima alocare permisă, minimum 0; `is_carried` marchează reutilizarea ulterioară. Nu cunoaștem ziua achiziției fiecărui pixel. `available_from` indică închiderea ferestrei, fără a garanta publicarea operațională istorică. Primele trei zile NDVI rămân lipsă.

### Matricea X, VIIRS și statistici

X are **1827 × 12 predictori fizici**, cu **54 coloane** în CSV incluzând data și auxiliarele:

| Sursă | Variabile | Unități |
|---|---|---|
| ERA5, temperatură | `temperature_mean_c`, `temperature_max_c`, `dewpoint_mean_c` | °C |
| ERA5, umiditate și vânt | `relative_humidity_mean_pct`; `wind_speed_mean_mps`, `wind_speed_max_mps` | %; m/s |
| ERA5, fluxuri și sol | `precipitation_total_mm`; `solar_radiation_total_mjm2`; `soil_moisture_mean_m3m3` | mm; MJ/m²; m³/m³ |
| MODIS | `ndvi_mean`; `lst_day_mean_c`, `lst_night_mean_c` | adimensional; °C |

Lipsurile rămân NaN, fără imputare. Dicționarul documentează fiecare coloană și rolul său. VIIRS este în `tabel_aliniat_complet.csv`, cu low separat și varianta nominal/high. Detecțiile nu sunt incendii distincte, iar suma FRP peste achiziții nu este energie zilnică sau putere regională simultană. **Zero detecții nu demonstrează absența incendiului.** Sunt 1249 detecții în 24 zile, dintre care 64 low; nominal/high păstrează 1185 detecții în 23 zile. CSV-ul nu include jurnalul observațiilor fără detecții, deci acoperirea observațională VIIRS nu este cunoscută.

Statisticile celor 12 predictori includ n valid/lipsă, medie, mediană, deviație standard de eșantion (`ddof=1`), minim, Q1/Q2/Q3 și maxim; cuantilele folosesc interpolare liniară. Cele trei histograme reprezentative au 35 intervale. Spearman folosește zilele complete ale fiecărei perechi și ranguri medii la egalități, recalculate după eliminarea lipsurilor. Pentru sub două valori sau o variabilă constantă, ρ este NaN. Sunt publicate **27 perechi ERA5–MODIS**, cu numărul zilelor valide comune; heatmap-ul folosește direct CSV-ul pe scala −1…+1.

<a id="cp3"></a>
## 5. Metodologia CP3

CP3 păstrează exact cei 12 predictori originali CP2 și aceleași NaN. NAO/AO din data observației **D−1** sunt adăugați pentru rândul D. Grupurile sunt ERA5 (9), MODIS (3), NOAA (2), ERA5+MODIS (12), ERA5+NOAA (11) și TOATE (14).

| Reprezentare | ERA5 | NOAA | MODIS |
|---|---|---|---|
| 1 zi | Ziua fizică D−1, deja aliniată în CP2 | Observația din D−1 | Starea CP2 disponibilă la începutul zilei D |
| 7 zile | D−7…D−1 fizic; rândurile CP2 D−6…D, fără al doilea shift | Istoricul observațional D−7…D−1 | Media stărilor CP2 din D−7…D−1, `shift(1).rolling(7)` |

Pe șapte zile se folosesc maxime pentru temperatura/vântul maxim regional, sume pentru precipitații și radiație, medii pentru ceilalți predictori și indici. Sunt necesare toate cele șapte valori valide (`min_periods=7`), fără ferestre parțiale sau completare. Istoricul NOAA începe în decembrie 2019; prima medie NOAA poate exista chiar dacă ERA5 anterior anului 2020 lipsește.

MODIS este o stare de disponibilitate la data rândului, în timp ce ERA5 din CP2 este deja decalat. De aceea ferestrele folosesc rânduri diferite ale CP2. Media MODIS pe șapte zile nu reprezintă șapte achiziții independente; pixelii unui compozit pot proveni dinaintea ferestrei. Valorile zilnice repetate sunt păstrate.

PCA folosește solver `full`, spectrul complet pe train și primele două componente pentru grupurile cu minimum trei predictori. NOAA se reduce **2→1**, prin ambele metode. Numărul componentelor este fixat înaintea comparației. `experimente_CP3.json` păstrează ordinea variabilelor, scaler-ele, coeficienții, eigenvalorile, EVR și loadings `components.T × sqrt(eigenvalue)`.

UMAP 0.5.7 folosește `n_neighbors=15`, `min_dist=0.1`, `metric=euclidean`, `n_epochs=300`, `init=random`, `n_jobs=1`, `low_memory=True`. Configurația este comună grupurilor; nu se caută hiperparametri pe test. Inițializarea și transformarea folosesc seed-uri explicite. Documentațiile [transformării UMAP](https://umap-learn.readthedocs.io/en/latest/transform.html) și [reproductibilității UMAP](https://umap-learn.readthedocs.io/en/latest/reproducibility.html) oferă context algoritmic; API-ul efectiv este cel fixat în dependențe, chiar dacă documentația online evoluează.

<a id="protocol"></a>
## 6. Protocolul experimental CP3

| Split | Interval planificat | Zile utilizate | Prima / ultima zi utilizată |
|---|---|---:|---|
| Train | 2020–2022 | 1041 | 11.01.2020 / 31.12.2022 |
| Validation | 2023 | 342 | 24.01.2023 / 31.12.2023 |
| Test | 2024 | 343 | 24.01.2024 / 31.12.2024 |

Aceeași intersecție de **1726 zile** este folosită în toate cele șase grupuri, ambele ferestre și ambele metode. Se elimină 55 zile incomplete în cel puțin o reprezentare și încă 46 zile complete cu suprapuneri ale ferestrelor brute la granițele perioadelor. Nu există împărțire aleatoare.

La validation/test, începutul ferestrei fizice ERA5/NOAA și începutul fiecărui compozit MODIS care contribuie la rând trebuie să fie în noua perioadă. Un simplu gap de șapte zile ar fi insuficient. Regula exclude partajarea acelorași intervale/compozite între train și holdout, fără a elimina dependența serială în interiorul split-urilor.

`StandardScaler` este ajustat numai pe train (`ddof=0`); aceiași parametri transformă validation/test. PCA și UMAP sunt ajustate numai pe train, apoi transformă separat validation și test, fără refit. Validation este o subperioadă de verificare descriptivă. VIIRS, calendarul, QA și auxiliarele nu sunt intrări ale modelelor.

Metricile se calculează separat în fiecare split:

- **Trustworthiness T**, k=15: penalizează vecinii introduși artificial în proiecție; `1 − 2Σmax(r−k,0) / [n·k·(2n−3k−1)]`, pe scala 0…1. Distanța este euclidiană în intrările standardizate și proiecție. Implementarea este verificată față de [scikit-learn trustworthiness](https://scikit-learn.org/stable/modules/generated/sklearn.manifold.trustworthiness.html).
- **kNN retention**: fracția celor 15 vecini originali regăsiți în proiecție. Punctul însuși este exclus; egalitățile exacte sunt departajate stabil după ordinea calendaristică, pentru ambele metode.
- **EVR PCA**: varianța explicată pe train. **MSE PCA**: eroarea medie pătratică de reconstrucție în spațiul standardizat, separat pe split. Pentru UMAP, EVR și reconstrucția sunt N/A.

Seed-uri UMAP: **11, 22, 33, 44, 55**, principal 11. Sunt 12 configurații grup×fereastră, 60 ajustări UMAP și 12 repetări la seed=11 pentru verificarea exactă a coordonatelor. Validatorul reface independent configurația TOATE, șapte zile, seed=11. Scripturile fixează un singur fir Numba/BLAS; identitatea exactă este verificată în mediul declarat, fără garanție pentru alte versiuni sau arhitecturi.

Stabilitatea raportează media, SD de eșantion, minimul, maximul și n între seed-uri. Stabilitatea structurii folosește suprapunerea vecinătăților kNN între cele zece perechi de seed-uri, invariantă la rotație/translație; nu compară coordonatele brute. SD este descriptivă, fără interpretare de interval de încredere. PCA are o singură rulare deterministă, cu SD=N/A.

<a id="rezultate"></a>
## 7. Rezultate principale

### CP2: acoperire și relații între surse

| Sursă | Celule predictori lipsă / total | Procent lipsă |
|---|---:|---:|
| ERA5-Land, 9 predictori | 9 / 16443 | 0,0547% |
| MODIS NDVI | 3 / 1827 | 0,1642% |
| MODIS LST, zi și noapte | 32 / 3654 | 0,8758% |

În total lipsesc **44 valori fizice**: 9 ERA5, 3 NDVI, 8 LST zi și 24 LST noapte. Cele mai mari corelații ERA5–MODIS în valoare absolută sunt:

| ERA5 | MODIS | Spearman ρ | Zile valide |
|---|---|---:|---:|
| Temperatură medie | LST zi | +0,9034 | 1818 |
| Temperatură medie | LST noapte | +0,8898 | 1802 |
| Temperatură maximă regională | LST zi | +0,8688 | 1818 |
| Temperatură maximă regională | LST noapte | +0,8434 | 1802 |
| Punct de rouă | LST noapte | +0,7928 | 1802 |

Asocierile sunt descriptive, neajustate pentru sezonalitate sau autocorelație; nu demonstrează cauzalitate.

### CP3: acoperire și comparația PCA–UMAP

| Reprezentare | Dimensiuni CSV, cu auxiliare | Celule predictori lipsă | Zile complete, 14 predictori | Zile comune utilizate |
|---|---|---:|---:|---:|
| 1 zi | 1827×38 | 44 | 1800 | 1726 |
| 7 zile | 1827×52 | 143 | 1775 | 1726 |

NOAA nu introduce lipsuri. Tabelul arată T pe **test 2024**, UMAP medie ± SD între cinci seed-uri; EVR este calculată numai pe train.

| Fereastră | Grup | EVR PCA train | T PCA test | T UMAP test ± SD |
|---|---|---:|---:|---:|
| 1 zi | ERA5 | 71,860% | 0,9364 | 0,9505 ± 0,0065 |
| 1 zi | MODIS | 98,559% | 0,9944 | 0,9468 ± 0,0146 |
| 1 zi | NOAA, 1D | 78,353% | 0,8761 | 0,8904 ± 0,0108 |
| 1 zi | ERA5+MODIS | 71,193% | 0,9436 | 0,9493 ± 0,0062 |
| 1 zi | ERA5+NOAA | 58,932% | 0,8808 | 0,9240 ± 0,0072 |
| 1 zi | TOATE | 61,137% | 0,9051 | 0,9180 ± 0,0042 |
| 7 zile | ERA5 | 76,725% | 0,9530 | 0,9317 ± 0,0131 |
| 7 zile | MODIS | 98,781% | 0,9953 | 0,9588 ± 0,0089 |
| 7 zile | NOAA, 1D | 79,708% | 0,8844 | 0,8977 ± 0,0171 |
| 7 zile | ERA5+MODIS | 75,649% | 0,9610 | 0,9362 ± 0,0061 |
| 7 zile | ERA5+NOAA | 63,038% | 0,9195 | 0,9134 ± 0,0067 |
| 7 zile | TOATE | 65,062% | 0,9420 | 0,9140 ± 0,0082 |

UMAP are T medie mai mare în 6/12 configurații, PCA în celelalte 6/12; diferențele UMAP−PCA sunt −0,0476…+0,0432. Retenția kNN și MSE PCA complete sunt în CSV; pentru MODIS zilnic, de exemplu, retenția pe test este 0,8742 PCA / 0,6910 UMAP.

**Comparațiile U11:** adăugarea NOAA la ERA5 schimbă T pe test cu −0,0555 PCA / −0,0265 UMAP zilnic, respectiv −0,0335 / −0,0184 pe șapte zile. PCA are T mai mare pe șapte zile în toate grupurile; UMAP nu are o evoluție uniformă. Schimbarea grupului sau ferestrei schimbă spațiul și vecinătățile originale: aceste diferențe nu măsoară îmbunătățirea predicției incendiilor. Comparația PCA–UMAP se interpretează în interiorul aceleiași configurații.

Suprapunerea medie a vecinătăților UMAP între seed-uri pe test variază între **0,4493 și 0,7796**. Pentru TOATE, T PCA train/validation/test este 0,8905 / 0,9209 / 0,9051 zilnic și 0,9144 / 0,9275 / 0,9420 pe șapte zile. T medie UMAP este 0,9766 / 0,9238 / 0,9180 zilnic și 0,9869 / 0,8982 / 0,9140 pe șapte zile. Evaluarea în eșantion pe train nu este echivalentă celei pe holdout.

Harta ERA5–NOAA are 18 corelații Spearman pe toate zilele valide comune fiecărei perechi, fără filtrarea la calendarul experimental: fiecare pereche are n=1826. Cea mai mare valoare absolută este temperatura medie–NAO, **ρ=−0,1761**; urmează punctul de rouă–NAO (−0,1595) și temperatura maximă–NAO (−0,1466). Nu se ajustează sezonalitatea și nu se raportează p-value bazate pe independența zilelor.

<a id="limite"></a>
## 8. Limitări metodologice

- O singură regiune și cinci ani; generalizarea spațială nu este demonstrată. Zilele și ferestrele suprapuse dintr-un split sunt dependente; n reprezintă zile, fără a echivala cu eșantioane independente.
- Mediile regionale neponderate ascund eterogenitatea spațială, iar suportul QA MODIS este variabil. Propagarea compozitelor produce observații repetate; convenția de departajare a vecinilor egali contează.
- D−1 și închiderea compozitelor evită datele viitoare în sensul observațiilor. Reanalizele, produsele satelitare și indicii retrospectivi nu garantează disponibilitatea operațională istorică la acea dată.
- Lipsesc date ERA5 înainte de 2020 și intervalul de flux final din 01.01.2025. Golurile nu sunt imputate; comparațiile se referă la calendarul comun filtrat.
- Sezonalitatea și autocorelația pot explica o parte din corelații și geometria proiecțiilor. Culoarea lunii din figuri evidențiază sezonalitatea, fără a o elimina.
- NAO/AO descriu circulația la scară mare și nu înlocuiesc meteorologia locală. Fidelitatea pe spații diferite nu măsoară valoarea predictivă adăugată.
- VIIRS nu este un inventar exhaustiv al incendiilor. Separarea vizuală într-o proiecție nu dovedește clase reale, cauzalitate sau tipare pre-incendiu. Un protocol predictiv ar necesita etichete și evaluare temporală distincte.

<a id="structura"></a>
## 9. Structura repository-ului

```text
README.md
.gitignore
requirements.txt                 # dependențe CP1–CP2
requirements_CP3.txt             # mediu CP3 cu versiuni fixate
run_pipeline.py / pipeline_methods.py / validate_outputs.py
run_cp2.py / cp2_analysis.py / cp2_delivery.py / cp2_figures.py
validate_cp2.py / prepare_publication.py
run_cp3.py / validate_cp3.py
cp3/                             # date, NOAA, modele, metrici, figuri, inventare, validare
tests/                           # teste CP1–CP2
tests_cp3/                       # teste CP3 și integritate inventar
metadata/                        # ferestre NASA și referința CSV CP2 validată
data/raw/INSTRUCTIUNI.txt         # arhivele originale se adaugă numai local
data/CP3_NOAA/                   # 2 snapshoturi CSV și provenienta_NOAA.json
outputs/CP2/                     # 7 CSV, 4 PNG și 3 JSON de control
outputs/CP3/                     # 6 CSV, 4 PNG și suportul verificabil al experimentelor
```

### Livrabile CP2

| CSV în `outputs/CP2/` | Conținut |
|---|---|
| `matrice_X.csv` | Cei 12 predictori și auxiliarii documentați, 1827×54 |
| `tabel_aliniat_complet.csv` | Sursele aliniate, observațiile zilei D și VIIRS low / nominal-high |
| `dictionar_variabile.csv` | Variabilă, sursă, rol, unitate și aliniere în cele două tabele |
| `statistici_predictori.csv` | Statistici exclusiv pentru cei 12 predictori |
| `corelatii_ERA5_MODIS.csv` | 27 perechi, Spearman și n valid |
| `acoperire_surse.csv` | Lipsuri pe sursă raportate la celulele predictorilor fizici |
| `acoperire_variabile.csv` | Acoperirea variabilelor matricei principale |

Figuri: [aliniere_surse.png](outputs/CP2/grafice/aliniere_surse.png), [preview_matrice_X.png](outputs/CP2/grafice/preview_matrice_X.png), [distributii_selectate.png](outputs/CP2/grafice/distributii_selectate.png) și [corelatii_intre_surse.png](outputs/CP2/grafice/corelatii_intre_surse.png). Prezintă alinierea, matricea grupată pe surse, trei histograme și heatmap-ul ERA5–MODIS. `manifest_CP2.json` păstrează proveniența și hash-urile, `validare_CP2.json` rezultatul controalelor, `publicatie_CP2.json` inventarul și hash-urile livrabilului.

### Livrabile CP3

| CSV în `outputs/CP3/` | Conținut |
|---|---|
| `matrice_CP3_zilnica.csv` | 14 predictori, data, auxiliarele și eligibilitatea experimentală, 1827×38 |
| `matrice_CP3_7zile.csv` | Reprezentarea pe șapte zile și suportul temporal, 1827×52 |
| `acoperire_CP3.csv` | Lipsuri și acoperire pe variabile, grupuri și split-uri |
| `rezultate_PCA_UMAP.csv` | 216 rânduri de metrici pe configurație, metodă, seed și split |
| `stabilitate_CP3.csv` | 180 rânduri de statistici între seed-uri și suprapuneri de vecinătate |
| `relatii_ERA5_NOAA.csv` | 18 perechi, Spearman și n valid |

Figuri: [baseline_PCA.png](outputs/CP3/grafice/baseline_PCA.png) — EVR, loadings și proiecții; [comparatie_PCA_UMAP.png](outputs/CP3/grafice/comparatie_PCA_UMAP.png) — aceleași zile și culoare a lunii; [stabilitate.png](outputs/CP3/grafice/stabilitate.png) — seed-uri și subperioade; [relatii_surse.png](outputs/CP3/grafice/relatii_surse.png) — heatmap ERA5–NOAA.

`experimente_CP3.json` conține protocolul, scaler-ele, PCA și auditul UMAP. `proiectii_CP3.npz` păstrează 74 tablouri numerice/date, fără pickle. `manifest_CP3.json` și `validare_CP3.json` documentează versiuni, hash-uri, selecția și controalele. Hash-urile normalizează numai CRLF→LF pentru text; PNG/NPZ sunt verificate pe octeți exacți. Singurul Markdown al livrabilului este acest README; rulările nu generează documente Markdown.

<a id="reproducere"></a>
## 10. Instalare, reproducere și validare

### Mediu verificat

Python **3.12.7**, Windows x64. `requirements_CP3.txt` fixează NumPy 1.26.4, pandas 2.2.2, SciPy 1.13.1, scikit-learn 1.5.1, UMAP 0.5.7, pynndescent 0.5.13, Numba 0.61.0, llvmlite 0.44.0, Matplotlib 3.9.2, h5py 3.11.0, threadpoolctl 3.5.0 și joblib 1.4.2. Mediul permite ambele etape. CP2 separat necesită Python 3.10+ și `requirements.txt`; identitatea imaginilor depinde și de versiunile grafice.

În PowerShell, din rădăcina repository-ului:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements_CP3.txt
```

Pe Linux/macOS se folosește `.venv/bin/python` în locul `.\.venv\Scripts\python.exe`. TensorFlow/ParametricUMAP nu sunt necesare. Cache-urile locale sunt excluse din Git; prima compilare Numba poate dura mai mult.

### Reproducerea CP2 pe arhivele originale

Adaugă în `data/raw/` cele trei ZIP-uri originale nedespachetate, câte unul pe sursă. Numele trebuie să includă ERA5, MODIS și VIIRS sau DL_FIRE. Hash-urile trebuie să corespundă referinței din `metadata/cp2_validated_reference.json`. Nu sunt necesare credențiale sau internet; metadatele NASA sunt versionate.

```powershell
.\.venv\Scripts\python.exe -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2
.\.venv\Scripts\python.exe -X utf8 -B validate_cp2.py --output-dir outputs/CP2
.\.venv\Scripts\python.exe -X utf8 -B prepare_publication.py
```

Comanda standard execută testele, recitește arhivele, validează ingestia și comparațiile QA, construiește X și produce exact **7 CSV, 4 PNG și 3 JSON de control**. Intermediarii ingestiei sunt temporari. Pentru fișiere suplimentare în ieșire se cere un director separat; scriptul nu le șterge automat.

### Reproducerea CP3 pe snapshoturi

Sunt suficiente livrabilul CP2 validat și cele trei fișiere din `data/CP3_NOAA/`; arhivele brute nu sunt necesare pentru această etapă. Rularea pe snapshoturile existente este offline.

```powershell
.\.venv\Scripts\python.exe -X utf8 -B run_cp3.py
.\.venv\Scripts\python.exe -X utf8 -B validate_cp3.py
```

Comanda standard execută testele CP2/CP3, verifică CP2, construiește matricile, ajustează modelele numai pe train, produce șase CSV și patru PNG, apoi validează rezultatele reale. Nu modifică fișierele CP2; amprentele lor sunt comparate pe octeți înainte/după rulare.

Pentru refolosirea experimentelor calculate, cu regenerarea matricilor, figurilor și controalelor:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B run_cp3.py --reuse-experiments
```

Reutilizarea este acceptată numai dacă amprenta datelor, calendarului, codului experimental și versiunilor este identică; altfel comanda se oprește. Rularea fără opțiune reface toate ajustările. Nu există recalibrare pe test.

Snapshoturile nu trebuie redescărcate pentru reproducere. Numai dacă lipsesc, importul inițial din produsele oficiale este:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m cp3.noaa --directory data/CP3_NOAA
```

Dacă accesul este blocat, descarcă manual cele două CSV-uri CDAS și importă-le într-un director nou, fără suprascrierea snapshoturilor validate:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m cp3.noaa --directory data/CP3_NOAA_import --nao-csv C:/date/nao.csv --ao-csv C:/date/ao.csv
.\.venv\Scripts\python.exe -X utf8 -B run_cp3.py --noaa-dir data/CP3_NOAA_import --output-dir outputs/CP3_import
```

O descărcare ulterioară poate conține revizii și reprezintă altă proveniență; nu este presupusă identică datelor validate. Produsele CORE/GFS/GEFS nu sunt substituite automat.

### Validare fără arhive brute

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests_cp3 -v
.\.venv\Scripts\python.exe -X utf8 -B validate_cp2.py
.\.venv\Scripts\python.exe -X utf8 -B prepare_publication.py
.\.venv\Scripts\python.exe -X utf8 -B validate_cp3.py
```

Testele folosesc date sintetice. Validatorul CP2 verifică D−1, completitudinea fluxurilor, QA/ferestre/vechime, VIIRS, statisticile, corelațiile, dicționarul și cele șapte CSV față de referința validată. Validatorul CP3 recalculează independent **25578 celule săptămânale**, verifică exact cei 12 predictori CP2, protocolul temporal și scaler-ele train, reface PCA/loadings, toate cele 216 rânduri de metrici, stabilitatea și relațiile NOAA. Verifică 12 repetări la seed fix, o reajustare UMAP independentă și 18 comparații reale ale trustworthiness cu scikit-learn. Ambii controlează inventarele și hash-urile; nu pretind o nouă ingestie brută atunci când aceasta nu este executată.

`prepare_publication.py --check-index` auditează selecția locală deja adăugată în Git: inventarul comun CP2/CP3, un singur README și absența fișierelor brute/temporare. Inventarul CP3 este în `proposed_github_files` din manifest. Arhivele ZIP/NetCDF, mediile Python și cache-urile nu fac parte din selecție.
