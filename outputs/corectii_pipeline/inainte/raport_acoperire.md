# Raport de acoperire – MEDE U11 CP1

- Unitate: zi × regiune, 2020–2024 (1827 zile).
- ERA5: 43848 ore în 30 puncte.
- VIIRS: 1249 detecții în 24 zile.
- MODIS: 116 NDVI, 230 LST.
- Zero detecții VIIRS nu înseamnă absența sigură a incendiului.

| Sursa | Variabila | Zile valide | Acoperire |
|---|---|---:|---:|
| ERA5-Land | temperature_mean_c | 1827/1827 | 100.0% |
| ERA5-Land | precipitation_total_mm | 1827/1827 | 100.0% |
| ERA5-Land | soil_moisture_mean_m3m3 | 1827/1827 | 100.0% |
| VIIRS Active Fire | viirs_detection_count | 1827/1827 | 100.0% |
| VIIRS Active Fire | viirs_has_detection | 1827/1827 | 100.0% |
| MODIS NDVI | ndvi_mean | 1824/1827 | 99.84% |
| MODIS LST | lst_day_mean_c | 1816/1827 | 99.4% |
| MODIS LST | lst_night_mean_c | 1800/1827 | 98.52% |

## Limitări

- Medii calculate în întreaga casetă, fără ponderare pe suprafața pixelilor.
- Filtrare MODIS după QA; valori propagate doar după sfârșitul ferestrei de observație.
- Acest pipeline încarcă și aliniază datele; nu evaluează încă un model predictiv.
