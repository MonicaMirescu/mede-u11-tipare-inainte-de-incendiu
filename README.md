# MEDE U11 · CP2 final

**Tipare înainte de incendiu**, regiunea Bejís–Villanueva de Viver, Castellón, Spania.
Perioada **01.01.2020–31.12.2024**; unitatea **zi × regiune**, 1.827 zile.

[Repository și livrabil final](https://github.com/MonicaMirescu/mede-u11-tipare-inainte-de-incendiu/tree/cp2-final).
Cerința CP2: alinierea surselor, matricea de trăsături grupate pe sursă, distribuții și corelații între surse.
Nu sunt implementate PCA, clustering sau modele predictive.

## Surse și aliniere

| Sursă | Suport și agregare | Aliniere la zi × regiune |
|---|---|---|
| ERA5-Land | 30 centre, grilă 0,1°; medii regionale orare; RH calculată întâi pe celule | Zi UTC; fluxuri orare încheiate la timestamp. În X datat D: ERA5 din D−1 |
| MODIS MOD13Q1.061 NDVI | 250 m nominal; media pixelilor care trec QA strict | Ultimul compozit cu fereastra încheiată până la D, reportat în trecut, fără interpolare liniară |
| MODIS MOD11A2.061 LST | 1 km nominal; medii QA valide, zi/noapte | Ferestre din metadata NASA: 8 zile, respectiv 5/6 la sfârșit de an; aceeași regulă de reportare |
| VIIRS S-NPP Active Fire C2 | Detecții punctuale în BBOX; număr și FRP zilnic UTC | Numai în tabelul complet, cu low separat și nominal/high; exclus din X |

BBOX: lat 39,7…40,2; lon −1,0…−0,4. Sursele sunt reunite la nivel de regiune, fără a pretinde aceeași grilă de pixeli. **X are 1.827 × 12 predictori fizici**: 9 ERA5, NDVI strict și LST zi/noapte. CSV-ul are 54 coloane, incluzând data, QA, acoperire, vechime și lipsuri. Dicționarul separă aceste roluri.

## Reproducere pe arhivele originale

Python 3.10+ și dependențele din requirements.txt:

```bash
python -m pip install -r requirements.txt
python -X utf8 -B run_cp2.py --input-dir data/raw --output-dir outputs/CP2
python -X utf8 -B validate_cp2.py --output-dir outputs/CP2
python -X utf8 -B prepare_publication.py
```

Copiază în data/raw/ cele trei ZIP-uri originale, nedespachetate, câte unul pe sursă; numele trebuie să includă ERA5, MODIS și VIIRS sau DL_FIRE. Arhivele nu sunt incluse în Git. Nu sunt necesare credențiale sau internet la rulare; metadatele NASA sunt versionate.

Comanda standard execută testele, recitește și verifică arhivele, construiește X, apoi produce **exact 7 CSV și 4 PNG**. Intermediarii ingestiei/QA sunt temporari; verificările lor sunt executate înainte de eliminare. Rezultatele se verifică și față de selecția numerică din commit-ul validat 4778251. Dacă directorul de ieșire conține livrabile din altă versiune, comanda cere un director separat și nu le șterge automat.

## Verificare fără arhive brute

Pentru pachetul clonat de pe GitHub:

```bash
python -m pip install -r requirements.txt
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B validate_cp2.py
python -X utf8 -B prepare_publication.py
```

Testele folosesc date sintetice distincte. Validatorul controlează calendarul, D−1, lipsurile, ferestrele/vechimea MODIS, VIIRS, statisticile, Spearman și numărul de zile pe pereche, dicționarul, acoperirea, PNG-urile și hash-urile. Fără arhive, nu pretinde o nouă citire a datelor brute. Pentru auditul selecției Git se poate adăuga --check-index la prepare_publication.py.

## Livrabile în outputs/CP2/

| CSV | Conținut |
|---|---|
| matrice_X.csv | 1.827 zile × 12 predictori fizici, plus indicatori auxiliari necesari |
| tabel_aliniat_complet.csv | Observațiile contemporane ale zilei D, QA și VIIRS; fără scenariul alternativ NDVI |
| dictionar_variabile.csv | Nume, sursă, rol, unitate și aliniere pentru fiecare coloană din cele două tabele |
| statistici_predictori.csv | Numai cei 12 predictori: n valid/lipsă, medie, mediană, std, minim, Q1, Q2, Q3, maxim |
| corelatii_ERA5_MODIS.csv | 27 perechi ERA5–MODIS: Spearman și n zile valide comune |
| acoperire_surse.csv | Lipsuri raportate la celulele predictorilor fizici, pe sursă |
| acoperire_variabile.csv | Acoperirea coloanelor numerice din X principal, fără scenarii auxiliare |

În grafice/ sunt numai:

1. [aliniere_surse.png](outputs/CP2/grafice/aliniere_surse.png) — grid, agregare, timp, QA și goluri.
2. [preview_matrice_X.png](outputs/CP2/grafice/preview_matrice_X.png) — cei 12 predictori grupați pe sursă, cu unități.
3. [distributii_selectate.png](outputs/CP2/grafice/distributii_selectate.png) — histograme: temperatură medie ERA5, NDVI, LST zi.
4. [corelatii_intre_surse.png](outputs/CP2/grafice/corelatii_intre_surse.png) — heatmap 9×3, exclusiv ERA5–MODIS, cu ρ și n.

[Metodologia CP2](outputs/CP2/metodologie_CP2.md) explică exact conversiile, QA, propagarea și limitele. Cele trei JSON-uri de control sunt manifest_CP2.json (proveniență și hash-uri), validare_CP2.json (rezultatul verificării) și publicatie_CP2.json (inventarul exact). Nu se publică analize suplimentare sau jurnale temporare.

## Decizii și limite

- ERA5: K→°C; m→mm; J/m²→MJ/m²; vânt în m/s; RH calculată pe celulă înaintea medierii. Totalurile tp/ssrd folosesc D 01:00…D+1 00:00 și necesită 24 intervale, fără o nouă dezacumulare.
- Lipsurile rămân NaN, fără imputare. În X: ERA5 0,055%, NDVI 0,164%, LST 0,876% din celulele predictorilor acelei surse. Prima zi nu are ERA5 din 31.12.2019; în tabelul complet, totalurile din 31.12.2024 necesită tp/ssrd la 01.01.2025 00:00 UTC.
- NDVI folosește QA strict detaliat; LST păstrează QC=0 valid. Nu se aplică un prag arbitrar de pixeli. Numărul/procentul pixelilor valizi și vechimea sunt explicite.
- Reportarea MODIS folosește numai ferestre încheiate, cel mult 32 zile NDVI / 16 zile LST după închidere. Nu este interpolare sau observație zilnică independentă. Închiderea ferestrei nu garantează disponibilitatea operațională istorică a produsului.
- Mediile regionale sunt neponderate pe aria pixelilor; suportul QA poate fi redus. Zero detecții VIIRS nu demonstrează absența incendiului.
- Spearman folosește zilele valide ale fiecărei perechi, cu ranguri medii la egalități. Nu ajustează sezonalitatea sau dependența temporală și nu demonstrează cauzalitate. Deviația standard este de eșantion; cuantilele folosesc interpolare liniară.

Ramura cp2-final pornește din cp2-matrice-statistici. [PR #1](https://github.com/MonicaMirescu/mede-u11-tipare-inainte-de-incendiu/pull/1) și ramura extinsă rămân intacte pentru referință. main nu este modificată; revizuirea și îmbinarea aparțin utilizatoarei.
