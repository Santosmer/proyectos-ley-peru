# Proyectos de Ley — Congreso del Perú (dashboard automático)

Pipeline de tres piezas:

1. `scraper.py` — consume la API JSON real del Congreso (no scraping de HTML,
   no depende del Excel manual). Guarda `data/proyectos.json` y `data/autorias.json`.
2. `.github/workflows/scrape.yml` — corre `scraper.py` cada 6 horas gratis en
   GitHub Actions y commitea los datos actualizados al repo.
3. `app.py` — dashboard interactivo en Streamlit que lee esos JSON.

## Cómo publicarlo (gratis, sin servidor)

1. Crea un repo en GitHub y sube esta carpeta completa.
2. Ve a **Settings → Actions → General** del repo y habilita
   "Read and write permissions" para el `GITHUB_TOKEN` (lo necesita el workflow
   para poder commitear `data/`).
3. Corre el workflow una vez manualmente (pestaña **Actions** → "Actualizar
   datos de proyectos de ley" → **Run workflow**) para generar los datos
   iniciales.
4. Ve a [streamlit.io/cloud](https://streamlit.io/cloud), conecta tu cuenta de
   GitHub, y despliega apuntando a `app.py` de este repo. Streamlit Cloud
   redeploya automáticamente cada vez que el repo cambia — es decir, cada vez
   que el workflow actualiza `data/`.
5. Streamlit Cloud te da una URL pública tipo `tu-app.streamlit.app`.

## Cómo se obtiene el desglose por rol y bancada

El endpoint de detalle por proyecto (`/expediente/{token1}/{token2}`) usa dos
IDs cifrados en la URL. Se descifró el esquema inspeccionando el bundle
JavaScript del sitio: es AES-128 en modo ECB con relleno PKCS7, usando una
clave fija embebida en el código (`ProdALg5ZrAsxBMD`), codificado después en
base64 URL-safe. `token1` es el periodo parlamentario (p. ej. `"2026"`) y
`token2` es el número de proyecto con 5 dígitos (p. ej. `"00417"`). La función
`encrypt_id()` en `scraper.py` reproduce esto y fue verificada contra valores
reales del sitio antes de usarse.

Ese endpoint de detalle trae `firmantes[]` con un `tipoFirmanteId` por persona
(1 = autor principal, 2 = coautor, 3 = adherente — inferido comparando contra
lo que muestra la página, no confirmado por documentación oficial) y `desGpar`
con el nombre de la bancada.

## Limitaciones conocidas (léelas antes de confiar en los números)

- **Solo Cámara de Diputados por ahora** (`codTipoParl: "D"`). El código
  probable para Senado es `"S"`, pero no lo confirmé — probarlo es el primer
  ajuste si quieres cubrir ambas cámaras.
- **El scraper ahora hace una petición extra por proyecto** (para el detalle),
  así que una corrida completa tarda varios minutos, no segundos. Si un
  proyecto puntual falla al traer el detalle, ese proyecto queda sin rol ni
  bancada pero no rompe el resto de la corrida.
- **El mapeo de `tipoFirmanteId` es una inferencia**, no viene documentado por
  el Congreso — se validó comparando un par de proyectos contra lo que
  muestra la página, pero no se revisó exhaustivamente.
- **Los nombres no están deduplicados entre variantes de escritura**
  (p. ej. "Pérez, Juan" vs "Perez Juan"). Antes de usar esto para conclusiones
  serias sobre quién presenta más proyectos, vale la pena revisar y limpiar
  esa columna.
