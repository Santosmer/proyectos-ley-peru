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

## Limitaciones conocidas (léelas antes de confiar en los números)

- **Solo Cámara de Diputados por ahora** (`codTipoParl: "D"`). El código
  probable para Senado es `"S"`, pero no lo confirmé — probarlo es el primer
  ajuste si quieres cubrir ambas cámaras.
- **El rol de cada firmante no está separado.** La API de lista trae a todos
  los nombres (autor principal, coautores, adherentes) juntos en un solo
  campo de texto. El endpoint de detalle sí los separa, pero usa un ID
  codificado por proyecto que todavía no hemos descifrado — así que por ahora
  el dashboard cuenta "proyectos por persona" sin distinguir el rol.
- **No hay bancada (grupo parlamentario) por proyecto todavía**, por la misma
  razón: vive en el endpoint de detalle.
- **Los nombres no están deduplicados entre variantes de escritura**
  (p. ej. "Pérez, Juan" vs "Perez Juan"). Antes de usar esto para conclusiones
  serias sobre quién presenta más proyectos, vale la pena revisar y limpiar
  esa columna.

## Próximo paso sugerido

Si quieres el desglose por rol y bancada, el siguiente trabajo es encontrar
cómo el sitio genera el ID codificado del endpoint de detalle
(`/expediente/{token1}/{token2}`) inspeccionando el bundle de JavaScript de
`wb2server.congreso.gob.pe`. No lo resolvimos en esta primera pasada.
