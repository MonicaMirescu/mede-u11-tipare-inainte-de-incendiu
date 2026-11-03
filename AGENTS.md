# Instrucțiuni pentru Codex – proiect MEDE U11

## Obiectiv și date
- Studiu: tipare meteorologice și satelitare înaintea incendiilor, regiunea Bejís–Villanueva de Viver, Castellón, Spania.
- Perioada 2020-01-01…2024-12-31 (inclusiv): 1827 zile, unitatea finală **zi × regiune**.
- Sursă 1: ERA5-Land, variabile orare (temperatură 2m, punct de rouă 2m, precipitații, radiație, umiditate sol nivel 1, componente de vânt 10m).
- Sursă 2: VIIRS S-NPP Active Fire C2, observații punctuale/detecții (nu inventa absența incendiului din lipsa detecției).
- Sursă 3: MODIS MOD13Q1.061 NDVI 250m/16 zile și MOD11A2.061 LST 1km/8 zile; controlează calitatea QA.
- BBOX: lat 39.7…40.2, lon -1.0…-0.4.

## Cerința CP2 (următorul livrabil)
Urmează exact `docs/CP2_CERINTE.md`. Profesorul cere documentarea gridului, agregării, interpolării, tratării golurilor; matricea unitară și statistici descriptive (distribuții și corelații între surse). Nu cere încă PCA, scree plot ori model predictiv.

## Reguli de implementare
1. Audit **înainte de extindere**: verifică citirea NetCDF/CSV/ZIP în codul existent, timestamp-urile/metadata NetCDF, agregarea variabilelor acumulative, coordonatele, QA și unitățile. Nu presupune că scriptul publicat deja este corect doar pentru că README conține niște cifre.
2. Rulări reale din `data/raw/`, sau un director dat explicit. Arhivele brute nu sunt pe GitHub și rămân excluse din git. Dacă datele reale lipsesc, declară acest lucru; testează doar pe fixture-uri sintetice distinct marcate.
3. Nu fabrica valori, rezultate, grafice, rapoarte, performanțe sau afirmații „testat cu succes” dacă nu există rulare concretă.
4. Asigură agregarea la zi × regiune cu 1827 rânduri pentru perioada fixă. Spune precis ce înseamnă orice interpolare/forward-fill al compozitelor MODIS; fără *future leakage*. Nu deduce «no fire» din 0 detecții VIIRS.
5. `X` trebuie să conțină predictori selectați cu denumiri și unități clare, grupați pe sursă. Ține datele VIIRS de etichetare/descriere separate de predictorii înainte de incendiu, cu explicarea alegerii.
6. Evită imputarea arbitrară sau modelarea nesolicitată; păstrează indicatori de lipsă/QA și documentează orice regulă.
7. Codul modular, determinist și verificabil: teste unitare pe date sintetice, validări pe date reale, fără dependențe/credențiale inutile.
8. Generează rezultate reale și documentație: `outputs/CP2/` cu CSV matrice, tabel de acoperire, statistici, figuri și un `metodologie_CP2.md`; actualizează README cu comenzi și limitări.
9. Fă schimbările pe o ramură separată, apoi propune PR; nu rescrie istoricul și nu forța push pe main. Revizuirea rezultatelor finale aparține utilizatoarei.

## Stilul răspunsului
Explică pe scurt fiecare decizie metodologică în română, astfel încât o studentă să poată prezenta oral procedura și motivația.
