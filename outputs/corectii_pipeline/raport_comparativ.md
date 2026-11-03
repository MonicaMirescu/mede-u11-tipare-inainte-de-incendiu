# Comparație reală CP1 înainte / după corecțiile metodologice

Referință CP1: `e0c34bc071712bd77f96f94ee88f801d06fafc57`. Aceleași trei arhive reale din `data/raw/`; SHA-256 în `comparatie_manifest.json`.
Comparația numerică folosește valorile înainte de export, cu toleranță absolută 1e-10 și relativă zero. O diferență foarte mică poate să nu apară la cele 5 zecimale ale CSV-ului vechi.

| Variabilă | Zile înainte | Zile după | Valori comune schimbate | Zile pierdute | Zile câștigate | Diferența absolută maximă |
|---|---:|---:|---:|---:|---:|---:|
| temperature_mean_c | 1827 | 1827 | 0 | 0 | 0 | 0 |
| temperature_max_c | 1827 | 1827 | 0 | 0 | 0 | 0 |
| dewpoint_mean_c | 1827 | 1827 | 0 | 0 | 0 | 0 |
| relative_humidity_mean_pct | 1827 | 1827 | 1827 | 0 | 0 | 1.950523991 |
| wind_speed_mean_mps | 1827 | 1827 | 0 | 0 | 0 | 0 |
| wind_speed_max_mps | 1827 | 1827 | 0 | 0 | 0 | 0 |
| precipitation_total_mm | 1827 | 1826 | 1241 | 1 | 0 | 7.652419806 |
| solar_radiation_total_mjm2 | 1827 | 1826 | 86 | 1 | 0 | 1.533333336e-06 |
| soil_moisture_mean_m3m3 | 1827 | 1827 | 0 | 0 | 0 | 0 |
| era5_hourly_observations | 1827 | 1827 | 0 | 0 | 0 | 0 |
| viirs_detection_count | 1827 | 1827 | 0 | 0 | 0 | 0 |
| viirs_frp_sum_mw | 1827 | 1827 | 0 | 0 | 0 | 0 |
| viirs_frp_max_mw | 24 | 24 | 0 | 0 | 0 | 0 |
| viirs_has_detection | 1827 | 1827 | 0 | 0 | 0 | 0 |
| ndvi_mean | 1824 | 1824 | 1824 | 0 | 0 | 0.04445581159 |
| ndvi_valid_pixels_pct | 1824 | 1824 | 1824 | 0 | 0 | 76.07060185 |
| lst_day_mean_c | 1816 | 1819 | 11 | 0 | 3 | 4.286471495 |
| lst_day_valid_pixels_pct | 1824 | 1827 | 11 | 0 | 3 | 23.35648148 |
| lst_night_mean_c | 1800 | 1803 | 11 | 0 | 3 | 5.178605372 |
| lst_night_valid_pixels_pct | 1824 | 1827 | 11 | 0 | 3 | 38.19444444 |

## Interpretare și date incomplete

- Precipitația și radiația sunt deja dezacumulate. Mutăm intervalele cu o oră înainte de gruparea pe zi UTC; nu diferențiem valorile din nou.
- 31.12.2024 are 23 intervale disponibile pentru fiecare total. Totalurile sunt NaN; sumele parțiale sunt distincte, cu flag complete=0. Este necesar tp și ssrd la 01.01.2025 00:00 UTC, pe aceeași grilă și din aceeași sursă.
- RH se calculează pe celulă și oră, apoi se mediază spațial și zilnic. Coordonatele ERA5 sunt verificate între fișiere, în BBOX, cu pasul de 0,1°; punctele efective sunt în manifest.
- LST: 14 zile primesc altă înregistrare sau o înregistrare anterior lipsă după corectarea sfârșitului de an. NDVI: 0 zile cu alocare temporală schimbată. Limitele sunt din metadata NASA CMR salvate local.
- Coloana available_from LST diferă pe 40 rânduri; o parte indică același compozit, căruia i s-a corectat doar sfârșitul ferestrei. Acestea nu sunt toate schimbări ale valorii LST.
- available_from este închiderea ferestrei observațiilor, nu data istorică de publicare. NDVI de sfârșit de an poate traversa anul; LST se încheie la 31 decembrie.
- Lipsește compozitul LST cu începutul 16.10.2022. Se păstrează propagarea precedentului, cu vechime explicită; un compozit existent fără pixeli valizi rămâne lipsă.

## NDVI: strict / marginal justificat

Strict: reliability=0, MODLAND=0 și QA detaliat compatibil. Marginal justificat: adaugă reliability=1 cu MODLAND 0/1, usefulness documentat și utilizabil, teren, fără aerosol ridicat, nor adiacent/mixt, zăpadă sau umbră. Fără prag numeric impus pe usefulness între codurile utilizabile; varianta strictă rămâne implicită.

| Variantă | Observații pixel × compozit acceptate | Compozite cu pixeli |
|---|---:|---:|
| justified | 7732536 / 8017920 | 116 |
| legacy | 7921472 / 8017920 | 116 |
| strict | 7467660 / 8017920 | 116 |

Medii de compozit schimbate față de CP1: strict 116, marginal justificat 116.
Strict și marginal justificat: 1824, respectiv 1824 zile disponibile. Între variante diferă 1600 medii zilnice; vezi comparatie_ndvi_zilnic_strict_justificat.csv.
Acoperirea zilnică a ambelor variante este în `dupa/raport_acoperire.csv`. Comparația lor pe fiecare compozit este în `dupa/ndvi_qa_comparison.csv`.

## Pixeli puțini și vechime

Nu s-a aplicat un prag minim de acoperire. Numărul și procentul pixelilor valizi însoțesc fiecare valoare; `dupa/modis_coverage_sensitivity.csv` arată pierderea de zile la praguri ipotetice de 1, 5, 10, 25, 50 și 75%, fără a le aplica.
`*_age_days` măsoară zilele de la ultima zi a ferestrei (prima valoare=1); `*_carry_days` măsoară zilele de la prima alocare permisă (prima valoare=0). Nu cunoaștem ziua exactă de achiziție a fiecărui pixel din aceste straturi. Limita de propagare CP1 rămâne explicit 32 zile NDVI / 16 zile LST după închiderea ferestrei.

## VIIRS

Înainte și în varianta completă: 1249 detecții în 24 zile. Sunt 64 detecții low. Varianta nominal/high: 1185 detecții în 23 zile.
`comparatie_viirs_filtrat.csv` cuantifică zilele și valorile afectate; numărătoarea completă este păstrată, cu low separat. Zero înseamnă zero detecții în arhivă; acoperirea observațională și absența incendiului nu pot fi stabilite. Suma FRP peste achiziții este descriptivă, nu energie zilnică sau putere regională simultană.

## Validare și limite

Validatorul rezultatelor corectate și cele 19 teste automate au trecut în această rulare. Testele folosesc rastruri/CSV sintetice și verifică și calendarul NASA salvat. Jurnalul este în teste_sintetice.log; comenzile și hash-urile codului verificat sunt în manifest. Fixture-urile nu sunt confundate cu datele reale.
Totalurile incomplete nu sunt imputate. Medii spațiale neponderate; maximele ERA5 sunt maximele mediei regionale orare. Datele din ziua incendiului nu devin automat predictori anteriori incendiului; nu s-a implementat matricea X sau analiza statistică CP2.
