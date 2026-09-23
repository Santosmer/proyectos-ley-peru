# Proyectos de Ley — Congreso del Perú (dashboard automático)

Pipeline de tres piezas:

1. `scraper.py` — consume la API JSON real del Congreso (no scraping de HTML,
   no depende del Excel manual). Guarda `data/proyectos.json` y `data/autorias.json`.
2. `.github/workflows/scrape.yml` — corre `scraper.py` cada 6 horas gratis en
   GitHub Actions y commitea los datos actualizados al repo.
3. `app.py` — dashboard interactivo en Streamlit que lee esos JSON.

3. `app.py` — dashboard interactivo en Streamlit que lee esos JSON, más
   `diputados_regiones.json` (directorio externo, ver sección "Región y
   directorio de diputados" más abajo).

## Qué muestra el dashboard

- Proyectos por mes (nombre del mes en español), con la fecha exacta
  disponible solo en las tablas de detalle.
- Proyectos por estado procesal.
- Proyectos por bancada, coloreados según el mapa `COLOR_BANCADA` en
  `app.py` (colores elegidos a pedido: Fuerza Popular naranja, Renovación
  Popular celeste, Buen Gobierno amarillo, Cívico Obras blanco, Ahora Nación
  rojo, Juntos por el Perú verde, Multipartidario azul, Instituciones con
  Iniciativa Legislativa lila).
- Proyectos por temática — **clasificación aproximada por palabras clave en
  el título** (`TEMAS_KEYWORDS` en `app.py`: salud, educación, empleo,
  electoral, niñez, producción, relaciones exteriores, reforma
  constitucional, seguridad, justicia, descentralización, medio ambiente,
  consumidor). No es una clasificación oficial del Congreso.
- Proyectos y congresistas por sexo.
- Congresistas por rol (autor principal / coautor / adherente), con
  selector para explorar a cada uno: bancada, región (si se identificó) y
  sus proyectos.
- Directorio de diputados electos, filtrable por región.

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
   que el workflow actualiza `data/`. **Ojo:** a veces el redeploy automático
   se queda con una versión vieja de los datos aunque el repo ya cambió — si
   ves un `KeyError` o datos desactualizados, entra a "Manage app" → menú de
   tres puntos → **Reboot** (limpiar caché no siempre alcanza, hace falta el
   reboot completo).
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

## Región y directorio de diputados

El Congreso no expone la región de cada diputado junto a los proyectos de
ley. Esa información viene de una **fuente externa**: el directorio de
diputados electos publicado por [decideperu.com](https://decideperu.com/diputados)
(resultados JNE 2026), descargado de
`https://dwin6afrwpy9h.cloudfront.net/publish/diputados/diputados_electos.json`
y guardado tal cual (nombre, región, partido) en `diputados_regiones.json`
en la raíz del repo — un archivo estático, no lo regenera `scraper.py`.

`app.py` cruza el nombre de cada congresista ("Apellidos, Nombres", como
viene del Congreso) contra ese directorio ("NOMBRES APELLIDOS", como viene
de decideperu.com) comparando **conjuntos de palabras** normalizadas (sin
tildes, mayúsculas), no el texto exacto — así no importa el orden ni los
acentos. La función es `buscar_region()` en `app.py`.

Resultado del cruce la primera vez que se probó: **120 de 127** personas
identificadas correctamente (verificado a mano que no hay colisiones: dos
personas distintas nunca mapearon al mismo registro del directorio). Las 7
que no cruzaron son probablemente reemplazos o accesitarios que entraron
después de la lista original de electos.

El directorio en sí trae **127 de los 130** diputados — no es un padrón
oficial completo y actualizado, es lo que decideperu.com tenía publicado al
momento de la descarga.

Los logos de cada partido (mostrados junto a la bancada) también vienen de
decideperu.com, referenciados por URL directa en `LOGO_PARTIDO` — no están
descargados ni alojados en este repo.

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
- **La región no es del Congreso, es de una fuente externa cruzada por
  nombre** — puede tener errores de cruce o quedar desactualizada si cambian
  los diputados (renuncias, reemplazos).
- **La clasificación temática es una heurística de palabras clave**, no la
  clasificación oficial de comisiones del Congreso. Un proyecto de ley suele
  tocar varios temas a la vez; aquí se le asigna solo el primero que calza.
- **El directorio de diputados no cubre a los 130** — solo a los 127 que
  decideperu.com tenía publicados al momento de la descarga.
