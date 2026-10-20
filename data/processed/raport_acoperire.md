# Raport de acoperire – MEDE U11 CP1

- Unitate: zi × regiune; perioada: 2020–2024 (1827 zile).
- ERA5-Land: 43.848 ore; 30 de puncte de grilă.
- VIIRS: 1.249 detecții în 24 zile distincte. Fără detecție **nu** înseamnă absența incendiului.
- MODIS: 116 compozite NDVI / 230 compozite LST.
- Calitatea datelor MODIS este controlată prin codurile QA; compozitele sunt folosite doar după încheierea ferestrei de observație.

| Sursă | Variabilă | Zile valide | Acoperire |
|---|---|---:|---:|
| ERA5-Land | temperature_mean_c | 1827/1827 | 100% |
| ERA5-Land | precipitation_total_mm | 1827/1827 | 100% |
| ERA5-Land | soil_moisture_mean_m3m3 | 1827/1827 | 100% |
| VIIRS | viirs_detection_count | 1827/1827 | 100% (0 = fără detecție în fișier) |
| MODIS | ndvi_mean | 1824/1827 | 99,84% |
| MODIS | lst_day_mean_c | 1816/1827 | 99,40% |
| MODIS | lst_night_mean_c | 1800/1827 | 98,52% |

## Limitări

- Datele reprezintă medii în întreaga casetă geografică.
- Zilele fără detecții VIIRS nu sunt neapărat zile fără incendiu.
- Nu s-a antrenat un model predictiv și nu s-a calculat un scor de performanță: acesta este pipeline-ul CP1.
