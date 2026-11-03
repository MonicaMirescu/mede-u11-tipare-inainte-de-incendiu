# Pachetul GitHub pentru predarea CP1 și CP2

Ramură propusă: `cp2-matrice-statistici`, cu Pull Request către `main`. Corecțiile CP1 sunt păstrate în commit-ul `5671125`; nu se rescrie istoricul și nu se face îmbinarea automată.

## Selecția publicată

Se păstrează codul, testele, documentația CP1/CP2, metadata temporale NASA și rapoartele comparative CP1. Pentru CP2 se publică toate tabelele CSV, metodologia, proveniența și validările: 40 artefacte, incluzând inventarul publicării, dintre care 7 PNG-uri.

| Grafic | Utilitate la predare |
|---|---|
| `X_principal_predictori_histograme_01.png` | Distribuțiile celor 12 predictori principali, cu unități și n |
| `X_principal_predictori_boxploturi_01.png` | Mediană, dispersie și valori extreme pentru predictorii principali |
| `corelatii_spearman.png` | Spearman cu n pe fiecare pereche, pentru NDVI strict |
| `numar_observatii_corelatii.png` | Acoperirea perechilor de predictori |
| `corelatii_sensibilitate_ndvi.png` | Verificarea sensibilității la politica NDVI marginală justificată |
| `aliniere_surse.png` | Sinteza gridului, agregării, QA și alinierii pentru slide-ul 2 |
| `preview_matrice_X.png` | Exemplu lizibil al matricei X, cu lipsurile păstrate |

Celelalte 24 de imagini sunt distribuții ale indicatorilor auxiliari, ale tabelului complet ori ale variantei de sensibilitate. Rămân pe calculator și se regenerează prin comanda integrală; sunt excluse prin `.gitignore`, fără ștergere și fără schimbarea statisticilor sau metodologiei. `index_grafice.csv` și inventarul din metodologia CP2 descriu rularea integrală, nu numai subsetul GitHub.

Lista exactă a artefactelor publicate/excluse și hash-urile fișierelor sunt în [`outputs/CP2/publicatie_CP2.json`](../outputs/CP2/publicatie_CP2.json). Acesta păstrează referința la verificarea integrală cu 31 de PNG-uri. Nu modificăm retroactiv manifestul sau raportul acelei rulări. Pentru text se normalizează exclusiv CRLF→LF la verificarea pachetului publicat, fiindcă Git poate schimba sfârșiturile de linie; nu se rotunjesc valori și nu se modifică alt conținut.

## Verificare fără arhivele brute

După clonare și instalarea dependențelor:

```bash
python -m pip install -r requirements.txt
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B prepare_publication.py
```

Această verificare controlează integritatea surselor și a artefactelor selectate, calendarul/dimensiunile X și imaginile esențiale. Nu pretinde recitirea arhivelor originale absente și nici regenerarea celor 24 de PNG-uri nepublicate.

## Reproducere integrală cu datele originale

Arhivele originale se copiază local în `data/raw/`, fără a le adăuga în Git:

```bash
python -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2
python -X utf8 -B validate_cp2.py --output-dir outputs/CP2
python -X utf8 -B prepare_publication.py --write
```

`validate_cp2.py` este validatorul rulării integrale, cu toate cele 31 de grafice, și se folosește după reproducere. `prepare_publication.py --write` verifică mai întâi întreaga rulare și apoi actualizează inventarul subsetului publicabil. Testele sintetice și rezultatele reale rămân distincte.

## Date și limitări

Nu se publică ZIP-uri, NetCDF-uri, observații brute din `data/raw/`, credențiale sau fișiere temporare. Singurul fișier versionat în `data/raw/` este `INSTRUCTIUNI.txt`. Tabelele publicate sunt rezultate derivate zilnic/regional, nu arhivele brute.

Metodologia validată rămâne: ERA5 din D−1 în X, NDVI strict principal și marginal justificat ca sensibilitate, VIIRS separat, NaN explicit și corelații Spearman descriptive pe perechi valide. Rămân documentate lipsurile inițiale, totalurile ERA5 incomplete din ultima zi a tabelului complet și limitele de acoperire/vechime MODIS. Nu sunt implementate PCA sau modele predictive.
