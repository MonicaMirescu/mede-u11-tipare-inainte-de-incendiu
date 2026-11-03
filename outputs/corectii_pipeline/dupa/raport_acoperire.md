# Raport de acoperire – MEDE U11 CP1

- Unitate: zi × regiune, 2020–2024 (1827 zile).
- ERA5: 43848 ore în 30 puncte.
- VIIRS: 1249 detecții în 24 zile.
- MODIS: 116 NDVI, 230 LST.
- Totaluri ERA5 incomplete: 1 zile; totalul este NaN, suma parțială și orele sunt păstrate separat.
- Pentru ultima zi este necesar tp și ssrd la 2025-01-01 00:00 UTC, pe aceeași grilă și din aceeași sursă dezacumulată.
- VIIRS încredere scăzută: 64 detecții; varianta nominal/high: 1185 detecții în 23 zile.
- Zero detecții VIIRS nu înseamnă absența sigură a incendiului.

| Sursa | Variabila | Zile valide | Acoperire |
|---|---|---:|---:|
| ERA5-Land | temperature_mean_c | 1827/1827 | 100.00% |
| ERA5-Land | temperature_max_c | 1827/1827 | 100.00% |
| ERA5-Land | dewpoint_mean_c | 1827/1827 | 100.00% |
| ERA5-Land | relative_humidity_mean_pct | 1827/1827 | 100.00% |
| ERA5-Land | wind_speed_mean_mps | 1827/1827 | 100.00% |
| ERA5-Land | wind_speed_max_mps | 1827/1827 | 100.00% |
| ERA5-Land | precipitation_total_mm | 1826/1827 | 99.95% |
| ERA5-Land | solar_radiation_total_mjm2 | 1826/1827 | 99.95% |
| ERA5-Land | soil_moisture_mean_m3m3 | 1827/1827 | 100.00% |
| VIIRS detection records | viirs_detection_count | 1827/1827 | 100.00% |
| VIIRS detection records | viirs_has_detection | 1827/1827 | 100.00% |
| MODIS NDVI strict | ndvi_mean | 1824/1827 | 99.84% |
| MODIS NDVI justified | ndvi_justified_mean | 1824/1827 | 99.84% |
| MODIS LST | lst_day_mean_c | 1819/1827 | 99.56% |
| MODIS LST | lst_night_mean_c | 1803/1827 | 98.69% |

## Limitări

- Medii calculate în întreaga casetă, fără ponderare pe suprafața pixelilor.
- NDVI strict implicit; varianta marginală justificată este păstrată separat. Fără prag minim de acoperire spațială aplicat.
- Sensibilitatea la praguri ipotetice este în modis_coverage_sensitivity.csv; acestea nu modifică datele.
- *_age_days = zile de la ultima zi a ferestrei (minim 1); *_carry_days = zile de la prima alocare permisă (minim 0). Nu este ziua achiziției fiecărui pixel.
- available_from = sfârșitul exclusiv al ferestrei de observație, nu data istorică a publicării; nu simulează disponibilitatea operațională.
- Reportăm ultimul compozit încheiat, găsit prin căutare în trecut (merge_asof), fără interpolare liniară; limita CP1 rămâne 32 zile NDVI / 16 zile LST după sfârșitul ferestrei.
- Un compozit existent fără pixeli valizi rămâne lipsă; nu se înlocuiește cu un compozit mai vechi.
- Acoperirea numerică VIIRS nu măsoară acoperirea observațională a satelitului.
- Acest pipeline încarcă și aliniază datele; nu evaluează încă un model predictiv.
