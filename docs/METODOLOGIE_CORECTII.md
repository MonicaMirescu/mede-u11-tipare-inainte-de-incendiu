# Corecții metodologice ale pipeline-ului CP1

Această etapă repară ingestia și alinierea CP1. Nu selectează predictorii X și nu implementează analiza statistică CP2. Rezultatele măsurate sunt în [raportul comparativ](../outputs/corectii_pipeline/raport_comparativ.md).

## ERA5: zi UTC și totaluri incomplete

Produsul este ERA5-Land **time-series**, deja dezacumulat. Marcajul GRIB `accum` păstrat în NetCDF nu justifică o nouă diferențiere. [ECMWF descrie dezacumularea și timestamp-urile](https://confluence.ecmwf.int/pages/viewpage.action?pageId=627854124).

Valoarea tp/ssrd de la t acoperă ora încheiată la t. Mutăm eticheta intervalului cu o oră în urmă pentru grupare, fără a muta temperatura, vântul sau umiditatea solului. Ziua UTC D însumează valorile D 01:00…D+1 00:00. O zi completă trebuie să aibă 24 de intervale distincte și valide pentru variabila respectivă.

| Indicator | Semnificație |
|---|---|
| `precipitation_total_mm` | Total pe zi UTC, doar la 24 intervale valide; altfel NaN |
| `solar_radiation_total_mjm2` | Total MJ/m² pe zi UTC, aceeași condiție |
| `precipitation_partial_mm`, `solar_radiation_partial_mjm2` | Suma intervalelor disponibile; nu este completată sau extrapolată |
| `precipitation_interval_hours`, `solar_radiation_interval_hours` | Număr de intervale valide, 0…24 |
| `precipitation_complete`, `solar_radiation_complete` | 1 doar când sunt 24 intervale; altfel 0 |
| `era5_*_valid_hours` | Ore regionale valide pentru fiecare variabilă instantanee/derivată |

Pentru 31.12.2024 există 23 intervale de totalizare. Valorile finale de la **01.01.2025 00:00 UTC**, tp în m și ssrd în J/m², sunt necesare pe toate cele 30 de puncte ale aceleiași grile, din aceeași sursă dezacumulată. Nu trebuie adus un cumul brut ERA5-Land standard în locul valorii orare time-series.

Micile valori negative din export se limitează la zero, ca în CP1, dar nu mai sunt ascunse fără control: acceptăm doar magnitudini până la 1e-7 m pentru tp și 5 J/m² pentru ssrd. Aceste toleranțe de control acoperă reziduurile minuscule observate în export (minime aproximativ −5,48e-8 m și −4 J/m²), nu o dezacumulare nouă. Valori mai negative opresc rularea. Numărul și minimul valorilor limitate sunt în manifest. NaN rămâne NaN; media regională nu ignoră celule lipsă.

## ERA5: umiditate și geografie

Aplicăm formula Magnus la temperatura/punctul de rouă în °C pe fiecare celulă și oră, limităm RH la 0–100%, apoi mediem regional și zilnic. Nu schimbăm coeficienții formulei CP1. Astfel, agregarea unei formule neliniare nu mai este confundată cu formula aplicată mediilor.

Verificăm unitățile, coordonate finite și unice, ordinea monotonă, pasul absolut de 0,1°, apartenența la BBOX și coincidența grilelor între fișiere. Grila reală are 5×6 centre: latitudini 39,7…40,1 și longitudini −1,0…−0,5. Nu inventăm punctele de pe marginile nordică/estică și nu declarăm o interpolare spațială. Media rămâne neponderată pe punctele efectiv extrase; o integrare exactă pe aria BBOX nu a fost implementată aici. `temperature_max_c` și `wind_speed_max_mps` sunt maxime zilnice ale mediei regionale orare.

## MODIS: ferestre și proveniență

NetCDF-urile reale nu includ time bounds sau date de publicare. ZIP-ul include două NetCDF și README; fișierele request/granule-list/XML enumerate în README nu sunt incluse. Am consultat metadata publice NASA CMR și am salvat în `metadata/modis_composite_periods.json` limite pentru toate datele de compozit din arhivă, confirmate pe două tile-uri de referință care intersectează regiunea: h17v04 și h17v05. Acestea confirmă calendarul produsului, fără a reconstitui lista originală AppEEARS.

Cititorul preferă time bounds din NetCDF dacă există; altfel caută data exactă în extrasul CMR. Dacă lipsesc metadata pentru o dată nouă, oprește rularea, fără a ghici durata din distanța până la următoarea înregistrare.

- LST: compozitul din 27.12.2019 se termină pe 31.12.2019; cel din 26.12.2020 se termină pe 31.12.2020. Sfârșitul exclusiv este 1 ianuarie. Ultima fereastră are 5/6 zile.
- NDVI: compozitul din 19.12.2019 are sfârșitul declarat la 03.01.2020 23:59:59, deci prima zi permisă este 4 ianuarie. Nu îl scurtăm la 31 decembrie. Compozitul din 18.12.2020 se încheie pe 02.01.2021.
- `*_composite_end_exclusive` este prima clipă din afara ferestrei; coincide cu `*_available_from`. Nu reprezintă publicarea istorică și nu garantează disponibilitate operațională imediată.

Unitățile temporale sunt citite din fișier. Calendarul `julian` AppEEARS este tratat explicit numai pentru originea 2000-01-01 și perioada 2000–2099, unde diferențele de timp față de acea origine coincid cu calendarul gregorian folosit aici. Alte calendare nesuportate produc eroare.

Exportul AppEEARS este deja reproiectat în EPSG:4326 prin nearest-neighbour, potrivit README-ului arhivei. Selectăm centrele din BBOX: NDVI 240×288 = 69.120 pixeli; LST 60×72 = 4.320 pixeli. Nu se face o nouă reproiectare în această etapă.

## NDVI: două politici QA

NDVI fizic trebuie să fie în [−0,2,1], cu factor 0,0001, fără fill −3000. Ambele politici verifică `pixel_reliability` și `VI_Quality`.

| Control | Strict | Marginal justificat |
|---|---|---|
| Reliability | 0 | Strict + observații cu reliability=1 |
| MODLAND, biții 0–1 | 0 | 0/1 pentru observațiile marginale |
| Usefulness, biții 2–5 | 0…12 | 0…12 |
| Aerosol ridicat, biții 6–7 = 3 | Respins | Respins |
| Nor adiacent/mixt, biții 8/10 | Respins | Respins |
| Land/water, biții 11–13 | 1 = teren | 1 = teren |
| Zăpadă/umbră, biții 14/15 | Respins | Respins |

Codurile usefulness 13–15 indică observații inutilizabile/defecte/neprocesate. Nu impunem un prag suplimentar între cele 13 niveluri utilizabile 0–12; codurile intermediare 3/5/6/7 sunt prezente în export. Ghidul și legenda exportului le descriu în intervalul nivelurilor de calitate, chiar dacă tabelul prescurtat nu le enumeră pe toate. [Ghidul MOD13 C6.1, secțiunea 5.5](https://lpdaac.usgs.gov/documents/621/MOD13_User_Guide_V61.pdf).

În varianta marginală, verificările detaliate elimină condițiile explicit suspecte; geometria observației sau alte condiții de procesare pot explica rangul marginal rămas. Nu declarăm aceste observații echivalente calitativ cu cele stricte. Valorile `ndvi_mean`/`ndvi_valid_pixels_pct` folosesc politica strictă; `ndvi_justified_mean`/`ndvi_justified_valid_pixels_pct` păstrează alternativa. `ndvi_justified_marginal_pixel_count` numără contribuțiile suplimentare acceptate. Comparația cu filtrul vechi reliability∈{0,1} se păstrează separat, pe compozit.

## LST, suport spațial și propagare

Păstrăm politica LST CP1: intervalul brut valid, control obligatoriu `(QC & 3)==0`, factor 0,02 K și conversie la °C, plus interval fizic 200–360 K. Acest interval fizic nu respinge nicio observație altfel acceptată din arhiva reală auditată. **QC=0 este valid**, indiferent de atributul `_FillValue=0` atașat stratului QC; temperatura brută zero rămâne fill. Citirea brută prin h5py evită mascarea greșită a QC=0.

Pentru fiecare variantă NDVI și fiecare LST zi/noapte păstrăm media, `*_valid_pixel_count` și `*_valid_pixels_pct`. Procentul are ca numitor toate centrele selectate în BBOX, fără reducerea numitorului după QA.

Nu este aplicat un prag minim spațial. O medie bazată pe 5 pixeli este păstrată cu suportul real de 5/4.320, fără a pretinde că reprezintă întreaga regiune. Tabelul de sensibilitate prezintă praguri ipotetice 1/5/10/25/50/75%; `applied_to_output=False` confirmă că nu au filtrat ieșirile.

Alinierea folosește ultimul compozit cu fereastra încheiată, prin `merge_asof(direction="backward")`, fără interpolare liniară. Păstrăm plafonul CP1: maximum 32 zile NDVI / 16 zile LST de la sfârșitul ferestrei, pentru a izola corecțiile cerute; plafonul este o regulă explicită de reportare, fără validare ca prag optim. O înregistrare de compozit existentă, dar fără pixeli valizi, rămâne lipsă. Dacă lipsește complet o înregistrare, compozitul anterior poate fi reportat în limita plafonului. Caz real: LST 16.10.2022 lipsește.

`*_age_days` este numărul de zile de la ultima zi a ferestrei, deci 1 la prima alocare; `*_carry_days` este numărul de zile de la închiderea ferestrei, deci 0 la prima alocare; `*_is_carried=1` indică repetarea după acea primă alocare. Indicatorii sunt separați pentru NDVI strict, NDVI marginal justificat, LST zi/noapte și lipsesc atunci când media lipsește. Vârsta este a ferestrei; ziua exactă a observației fiecărui pixel nu este disponibilă în straturile extrase.

## VIIRS și validare

Varianta completă păstrează toate detecțiile și numărul zilnic low. Varianta nominal/high elimină numai confidence=`l`; nu redenumește zilele rămase fără detecții ca zile fără incendiu. Datele sunt UTC. Verificăm confidence, versiunea/satelitul, ora, FRP și duplicatele. Suma FRP peste pixeli și achiziții descrie înregistrările din zi; nu este energie zilnică sau putere regională simultană. Nu există un jurnal al observațiilor fără detecții în acest CSV, deci acoperirea observațională este necunoscută.

Testele `unittest` folosesc fixture-uri sintetice marcate, inclusiv ZIP/NetCDF/CSV. Acoperă încadrarea intervalelor, ora de închidere, totaluri incomplete, RH pe celule, grile diferite cu aceeași formă, QA detaliat, QC=0, metadate temporale lipsă, ani bisecți, propagare, goluri și confidence VIIRS. Verificările rezultatelor reale controlează calendarul, totalurile/flag-urile, vârstele, suportul spațial și relațiile dintre variante; nu fixează numărul de detecții drept singură dovadă de corectitudine.
