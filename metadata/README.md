# Metadata temporale MODIS

`modis_composite_periods.json` este un extras real din API-ul public NASA CMR, consultat pentru corecțiile CP1. Include 116 date NDVI și 230 date LST, exact datele existente în arhiva locală, fiecare confirmată pe tile-urile de referință h17v04/h17v05.

Fiecare intrare păstrează începutul, sfârșitul exclusiv, identificatorii granulelor/conceptelor NASA, sfârșitul inclusiv original și linkul metadata. Sfârșitul exclusiv este `time_end` NASA + o secundă. Interogările originale și momentul consultării sunt în JSON; repetarea interogărilor poate întoarce revizii NASA mai noi.

Extrasul permite rularea fără internet. Hash-ul său este inclus în manifestul pipeline-ului. Cititorul refuză să ghicească limite pentru date inexistente în extras. Pentru altă perioadă este necesară actualizarea metadatelor din NASA CMR sau furnizarea de time bounds explicite în NetCDF.

Tile-urile de referință verifică calendarul produselor. Nu substituie fișierul AppEEARS granule-list, absent din ZIP-ul local, și nu certifică lista originală completă de granule a extracției.
