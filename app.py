import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Proyectos de Ley — Congreso del Perú", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

MESES_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

# Colores por bancada, según lo pedido. Los valores que no coincidan
# exactamente con estas llaves (por ejemplo si el nombre real en los
# datos difiere un poco) simplemente caen a un color por defecto de Plotly.
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


@st.cache_data
def load_data():
    proyectos = json.loads((DATA_DIR / "proyectos.json").read_text(encoding="utf-8"))
    autorias = json.loads((DATA_DIR / "autorias.json").read_text(encoding="utf-8"))
    return pd.DataFrame(proyectos), pd.DataFrame(autorias)


df_proyectos, df_autorias = load_data()
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
    "Selecciona un nombre para ver su bancada y los proyectos en los que participó. "
    "La región todavía no está disponible (ver nota al final de la página) y esta "
    "lista solo incluye a quienes ya presentaron, coautoraron o se adhirieron a algún "
    "proyecto — no a los 130 diputados; los que aún no participan en ningún proyecto "
    "no tienen datos en el Congreso para mostrar."
)
nombres = sorted(df_autorias["persona"].dropna().unique().tolist())
if nombres:
    seleccionado = st.selectbox("Diputado/a", nombres)
    proyectos_persona = df_autorias[df_autorias["persona"] == seleccionado]["proyecto_ley"]
    detalle = df_proyectos[df_proyectos["proyecto_ley"].isin(proyectos_persona)]
    bancada_persona = detalle["bancada"].mode()
    bancada_persona = bancada_persona.iloc[0] if not bancada_persona.empty and bancada_persona.iloc[0] else "No disponible"

    c1, c2, c3 = st.columns(3)
    c1.metric("Bancada", bancada_persona)
    c2.metric("Región", "No disponible")
    c3.metric("Proyectos", len(detalle))

    st.dataframe(
        detalle[["proyecto_ley", "fecha_presentacion", "titulo", "estado", "tema_aprox"]],
        use_container_width=True,
    )

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
    "Notas: (1) la región del congresista todavía no está integrada — el Congreso no "
    "la expone junto a los proyectos, y cruzarla requiere un directorio externo (ONPE) "
    "que aún no está conectado. (2) La lista de diputados de arriba no cubre a los 130 "
    "electos, solo a quienes ya aparecen en algún proyecto — no encontramos todavía un "
    "directorio oficial completo y actualizado para el periodo 2026-2031."
)
