# CP2 – Alinierea surselor și matricea de trăsături

## Cerința oficială (din captura transmisă de utilizatoare)
> CP2_<cod>. Slide 2: cum ați adus sursele pe aceeași unitate și același pas de timp (grid, agregare, interpolare, goluri tratate) și matricea finală unitate × trăsături, cu trăsăturile grupate pe sursă și statistici descriptive (distribuții, corelații între surse). Link repo obligatoriu.

## Cadru de analiză
- Titlu: **Tipare înainte de incendiu**, unitatea U11, regiunea Bejís–Villanueva de Viver, Castellón, Spania.
- Interval: 2020-01-01 – 2024-12-31 (1827 zile).
- BBOX: [39.7, 40.2] lat și [-1.0, -0.4] lon.
- ERA5-Land: 43.848 ore, 30 puncte în extracția inițială; variabile orare.
- VIIRS S-NPP C2: 1.249 detecții în 24 zile distincte în extracția inițială. Acestea **nu** reprezintă 24 incendii distincte; zilele fără detecție nu demonstrează absența focului.
- MODIS AppEEARS: MOD13Q1.061 NDVI (250m/16 zile; 116 compozite), MOD11A2.061 LST (1km/8 zile; 230 compozite).
- Aceste statistici sunt din verificările și materialele CP1; reconfirmă-le prin rulare pe fișierele brute înainte de prezentarea rezultatelor CP2.

## Livrabile concrete CP2
1. Scripturile care citesc cele 3 arhive și verifică proveniența, metadata, datele, unitățile, QA, valori fill și coordonate.
2. O schemă clară pentru aliniere: selecția gridului/aria de studiu, agregări spațiale, unități fizice convertite, agregare la o zi, reguli pentru MODIS 8/16 zile și goluri. Explică alegerile, limitările și de ce nu există leakage temporal.
3. Matrice finală (CSV) **zi × trăsături**: un rând pe zi, coloană datei + predictori ERA5 + NDVI + LST, indicatoare QA/acoperire și, într-un fișier separat sau marcate distinct, coloane de etichetare VIIRS. Include dicționarul variabilelor/unităților.
4. Tabel cu acoperirea/lipsurile per sursă și per variabilă; număr de observații și valori completate.
5. Statistici descriptive real calculate: distribuții (histograme/boxplot, tabel describe cu minim, max, mediană, cuartile) și matrice de corelații între surse (de ex. Pearson sau Spearman, cu justificare). Nu interpreta mecanic corelația ca fiind cauzalitate.
6. Vizualizări pentru **slide-ul 2**: tabel sintetic al alinierii și un preview lizibil al matricei X; grafic(e) rezumate distribuții/corelații, cu numele și unitățile variabilelor. Se pot extinde pe continuări de slide 2, păstrând stilul CP1.
7. README care descrie exact cum se obțin aceste artefacte și un `metodologie_CP2.md` cu justificările și rezultatele măsurate.

## Restricții
- NU fabrica rezultate ori metrici. Dacă arhivele originale nu sunt accesibile, documentează ce lipsește și ce poate fi validat cu date sintetice.
- NU rula PCA, scree plot, loadings sau modele de predicție în această etapă decât dacă utilizatoarea cere explicit.
- Fără commit al datelor brute în repo.
- Propune soluții simple, explicabile profesorului la susținerea CP2.
