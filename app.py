import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Proyectos de Ley — Congreso del Perú", layout="wide")

DATA_DIR = Path(__file__).parent / "data"
ROOT_DIR = Path(__file__).parent

MESES_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

# Colores por bancada, según lo pedido. Los valores que no coincidan
# exactamente con estas llaves simplemente caen a un color por defecto de Plotly.
COLOR_BANCADA = {
    "Fuerza Popular": "#FF8C00",              # naranja
    "Renovación Popular": "#87CEEB",          # celeste
    "Partido del Buen Gobierno": "#FFD700",   # amarillo
    "Partido Cívico Obras": "#F5F5F5",        # blanco (con borde para que se vea)
    "Ahora Nación": "#FF3B30",                # rojo
    "Juntos por el Perú": "#2E8B57",          # verde
    "Multipartidario": "#1E63C8",             # azul
    "Instituciones con Iniciativa Legislativa": "#C8A2C8",  # lila
}

# Logos oficiales de cada partido, tomados de decideperu.com (fuente pública,
# resultados JNE 2026). Se muestran con st.image directo desde la URL.
LOGO_PARTIDO = {
    "Fuerza Popular": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/1366_FUERZA%20POPULAR.jpg",
    "Juntos por el Perú": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/1264_JUNTOS%20POR%20EL%20PERU.jpg",
    "Partido del Buen Gobierno": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2961_PARTIDO%20DEL%20BUEN%20GOBIERNO.jpg",
    "Renovación Popular": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/22_RENOVACION%20POPULAR.jpg",
    "Partido Cívico Obras": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2941_PARTIDO%20CIVICO%20OBRAS.jpg",
    "Ahora Nación": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2980_AHORA%20NACION%20-%20AN.jpg",
}

# Clasificación TEMÁTICA APROXIMADA, por palabras clave en el título.
# Esto NO es una clasificación oficial del Congreso — es una heurística
# simple. Un proyecto puede tocar varios temas; aquí se le asigna el
# primero que calce, en el orden de esta lista.
TEMAS_KEYWORDS = [
    ("Salud", ["salud", "essalud", "hospital", "médic", "medic", "sanitari", "enfermedad", "vacuna", "minsa"]),
    ("Educación", ["educ", "escolar", "universi", "docente", "estudiant", "colegio", "pedagóg"]),
    ("Empleo", ["trabaj", "laboral", "empleo", "sindical", "remuneraci", "pension", "jubila"]),
    ("Electoral", ["electoral", "elecciones", "voto", "onpe", "jne", "partido político", "sufragio"]),
    ("Niñez", ["niño", "niña", "infantil", "menor de edad", "adolescen"]),
    ("Producción", ["agrari", "agricultura", "industri", "pesc", "minero", "minería", "mype", "empresa", "comercio"]),
    ("Relaciones Exteriores", ["exterior", "diplomátic", "tratado internacional", "migrant", "frontera"]),
    ("Reforma Constitucional", ["constitución", "constitucional"]),
    ("Seguridad", ["seguridad ciudadana", "polic", "delin", "crimin", "penal"]),
    ("Justicia", ["judicial", "código civil", "código procesal", "justicia"]),
    ("Descentralización", ["gobierno regional", "gobierno local", "municipal", "descentraliza"]),
    ("Medio Ambiente", ["ambiental", "ecológ", "forestal", "recursos naturales", "residuos"]),
    ("Consumidor", ["consumidor"]),
]


def clasificar_tema(titulo: str) -> str:
    t = (titulo or "").lower()
    for tema, palabras in TEMAS_KEYWORDS:
        if any(p in t for p in palabras):
            return tema
    return "Otros / sin clasificar"


def norm_tokens(s: str) -> set:
    """Normaliza un nombre a un conjunto de palabras en mayúsculas sin tildes,
    para poder cruzar 'Apellidos, Nombres' contra 'NOMBRES APELLIDOS' sin
    depender del orden ni de los acentos."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z ]", " ", s).upper()
    return {t for t in s.split() if t not in ("DE", "DEL", "LA", "LOS", "LAS", "Y")}


@st.cache_data
def load_data():
    proyectos = json.loads((DATA_DIR / "proyectos.json").read_text(encoding="utf-8"))
    autorias = json.loads((DATA_DIR / "autorias.json").read_text(encoding="utf-8"))
    directorio_path = ROOT_DIR / "diputados_regiones.json"
    directorio = json.loads(directorio_path.read_text(encoding="utf-8")) if directorio_path.exists() else []
    for d in directorio:
        d["tokens"] = norm_tokens(d["nombre_fuente"])
    return pd.DataFrame(proyectos), pd.DataFrame(autorias), directorio


def buscar_region(persona: str, directorio: list, min_score: int = 3):
    """Cruza un nombre 'Apellidos, Nombres' contra el directorio oficial
    (fuente: JNE vía decideperu.com) usando coincidencia de palabras, no el
    string exacto, porque el orden y los acentos difieren entre fuentes."""
    toks = norm_tokens(persona)
    best, best_score = None, 0
    for d in directorio:
        score = len(toks & d["tokens"])
        if score > best_score:
            best, best_score = d, score
    if best and best_score >= min(min_score, len(toks)):
        return best["region"].replace("_", " ").title(), best["partido"]
    return None, None


df_proyectos, df_autorias, directorio = load_data()
df_proyectos["fecha_presentacion"] = pd.to_datetime(df_proyectos["fecha_presentacion"])
df_proyectos["tema_aprox"] = df_proyectos["titulo"].apply(clasificar_tema)

st.title("Proyectos de Ley — Congreso del Perú (2026-2031)")
st.caption(f"{len(df_proyectos)} proyectos registrados · datos actualizados automáticamente")

col1, col2, col3 = st.columns(3)
col1.metric("Total de proyectos", len(df_proyectos))
col2.metric("Personas involucradas", df_autorias["persona"].nunique())
col3.metric("Proponentes distintos", df_proyectos["proponente"].nunique())

st.subheader("Proyectos presentados por mes")
tmp = df_proyectos.copy()
tmp["mes_num"] = tmp["fecha_presentacion"].dt.month
tmp["anio"] = tmp["fecha_presentacion"].dt.year
tmp["mes_orden"] = tmp["fecha_presentacion"].dt.to_period("M")
timeline = (
    tmp.groupby(["mes_orden", "mes_num", "anio"]).size().reset_index(name="proyectos").sort_values("mes_orden")
)
timeline["mes"] = timeline.apply(lambda r: f"{MESES_ES[r['mes_num']]} {r['anio']}", axis=1)
st.plotly_chart(px.bar(timeline, x="mes", y="proyectos"), use_container_width=True)

st.subheader("Proyectos por estado procesal")
st.plotly_chart(px.pie(df_proyectos, names="estado"), use_container_width=True)

st.subheader("Proyectos por bancada")
if "bancada" in df_proyectos.columns and df_proyectos["bancada"].notna().any():
    banc = df_proyectos["bancada"].value_counts().reset_index()
    banc.columns = ["bancada", "count"]

    logo_cols = st.columns(len(LOGO_PARTIDO))
    for col, (partido, url) in zip(logo_cols, LOGO_PARTIDO.items()):
        with col:
            st.image(url, width=60)
            st.caption(partido)

    st.plotly_chart(
        px.bar(banc, x="bancada", y="count", color="bancada", color_discrete_map=COLOR_BANCADA)
        .update_traces(marker_line_color="#999", marker_line_width=1)
        .update_layout(showlegend=False),
        use_container_width=True,
    )
else:
    st.info("Sin datos de bancada todavía — corre el scraper de nuevo.")

st.subheader("Proyectos por temática (clasificación aproximada)")
st.caption(
    "Esta clasificación NO es oficial del Congreso: se calcula buscando palabras clave "
    "en el título de cada proyecto. Puede haber errores o temas mal asignados — úsala "
    "como una primera aproximación, no como dato definitivo."
)
tema_counts = df_proyectos["tema_aprox"].value_counts().reset_index()
tema_counts.columns = ["tema", "proyectos"]
st.plotly_chart(px.bar(tema_counts, x="tema", y="proyectos"), use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Por sexo (personas distintas)")
    if "sexo" in df_autorias.columns and df_autorias["sexo"].notna().any():
        personas_sexo = df_autorias.drop_duplicates("persona")["sexo"].value_counts().reset_index()
        personas_sexo.columns = ["Sexo", "Congresistas"]
        st.plotly_chart(px.pie(personas_sexo, names="Sexo", values="Congresistas"), use_container_width=True)
    else:
        st.info("Sin datos de sexo todavía — corre el scraper de nuevo.")
with col_b:
    st.subheader("Proyectos por sexo del firmante")
    if "sexo" in df_autorias.columns and df_autorias["sexo"].notna().any():
        st.plotly_chart(px.pie(df_autorias, names="sexo"), use_container_width=True)
    else:
        st.info("Sin datos de sexo todavía — corre el scraper de nuevo.")

st.subheader("Congresistas con más proyectos, por rol")
if "rol" in df_autorias.columns and df_autorias["rol"].notna().any():
    rol_filtro = st.multiselect(
        "Filtrar por rol", options=["autor_principal", "coautor", "adherente"],
        default=["autor_principal", "coautor", "adherente"],
    )
    filtrado = df_autorias[df_autorias["rol"].isin(rol_filtro)]
else:
    filtrado = df_autorias
top_autores = filtrado["persona"].value_counts().head(25).reset_index()
top_autores.columns = ["Congresista", "Proyectos"]
st.dataframe(top_autores, use_container_width=True)

st.subheader("Buscar diputado/a")
st.caption(
    "Selecciona un nombre para ver su bancada, región y los proyectos en los que "
    "participó. Esta lista solo incluye a quienes ya presentaron, coautoraron o se "
    "adhirieron a algún proyecto en el Congreso — no a los 130 diputados electos; "
    "para ver el padrón completo, baja hasta 'Directorio de diputados electos'."
)
nombres = sorted(df_autorias["persona"].dropna().unique().tolist())
if nombres:
    seleccionado = st.selectbox("Diputado/a", nombres)
    proyectos_persona = df_autorias[df_autorias["persona"] == seleccionado]["proyecto_ley"]
    detalle = df_proyectos[df_proyectos["proyecto_ley"].isin(proyectos_persona)]
    bancada_persona = detalle["bancada"].mode()
    bancada_persona = bancada_persona.iloc[0] if not bancada_persona.empty and bancada_persona.iloc[0] else None

    region_persona, partido_fuente = buscar_region(seleccionado, directorio)

    c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
    with c1:
        if bancada_persona and bancada_persona in LOGO_PARTIDO:
            st.image(LOGO_PARTIDO[bancada_persona], width=70)
    c2.metric("Bancada", bancada_persona or "No disponible")
    c3.metric("Región", region_persona or "No identificada")
    c4.metric("Proyectos", len(detalle))
    if region_persona is None:
        st.caption(
            "No se pudo identificar la región para este nombre en el directorio "
            "público cruzado (JNE / decideperu.com) — puede tratarse de un "
            "reemplazo o accesitario que entró después de la lista original."
        )

    st.dataframe(
        detalle[["proyecto_ley", "fecha_presentacion", "titulo", "estado", "tema_aprox"]],
        use_container_width=True,
    )

st.subheader("Directorio de diputados electos (fuente externa: JNE / decideperu.com)")
st.caption(
    f"{len(directorio)} de 130 diputados electos, con región y partido, tomados de una "
    "fuente pública externa (no del Congreso) porque el Congreso no publica este "
    "directorio junto a los proyectos de ley. Puede haber pequeñas diferencias frente "
    "al padrón oficial vigente (reemplazos, licencias, etc.)."
)
if directorio:
    dir_df = pd.DataFrame([{"Región": d["region"].replace("_", " ").title(),
                             "Partido": d["partido"],
                             "Nombre": d["nombre_fuente"].title()} for d in directorio])
    region_filtro = st.selectbox("Filtrar por región", ["Todas"] + sorted(dir_df["Región"].unique().tolist()))
    if region_filtro != "Todas":
        dir_df = dir_df[dir_df["Región"] == region_filtro]
    st.dataframe(dir_df.sort_values(["Región", "Partido", "Nombre"]), use_container_width=True)

st.subheader("Explorar proyectos")
st.caption(
    "La fecha exacta se muestra aquí, en el detalle por proyecto. Los gráficos "
    "generales de arriba agregan por mes."
)
busqueda = st.text_input("Buscar por palabra clave en el título")
tabla = df_proyectos
if busqueda:
    tabla = tabla[tabla["titulo"].str.contains(busqueda, case=False, na=False)]
st.dataframe(
    tabla[["proyecto_ley", "fecha_presentacion", "titulo", "estado", "proponente", "bancada", "tema_aprox"]],
    use_container_width=True,
)

st.caption(
    "Notas: (1) la región y el directorio completo vienen de una fuente externa "
    "(JNE vía decideperu.com), cruzada por nombre — no del Congreso, que no expone "
    "esa información junto a los proyectos. (2) El cruce de nombres es automático "
    "por coincidencia de palabras, no exacto; 7 de 127 personas no se pudieron "
    "identificar con certeza. (3) La clasificación temática es una aproximación por "
    "palabras clave, no oficial."
)
