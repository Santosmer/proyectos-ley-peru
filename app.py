import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Proyectos de Ley — Congreso del Perú", layout="wide")

DATA_DIR = Path(__file__).parent / "data"


@st.cache_data
def load_data():
    proyectos = json.loads((DATA_DIR / "proyectos.json").read_text(encoding="utf-8"))
    autorias = json.loads((DATA_DIR / "autorias.json").read_text(encoding="utf-8"))
    return pd.DataFrame(proyectos), pd.DataFrame(autorias)


df_proyectos, df_autorias = load_data()
df_proyectos["fecha_presentacion"] = pd.to_datetime(df_proyectos["fecha_presentacion"])

st.title("Proyectos de Ley — Congreso del Perú (2026-2031)")
st.caption(f"{len(df_proyectos)} proyectos registrados · datos actualizados automáticamente")

col1, col2, col3 = st.columns(3)
col1.metric("Total de proyectos", len(df_proyectos))
col2.metric("Personas involucradas", df_autorias["persona"].nunique())
col3.metric("Proponentes distintos", df_proyectos["proponente"].nunique())

st.subheader("Proyectos presentados por mes")
timeline = (
    df_proyectos.groupby(df_proyectos["fecha_presentacion"].dt.to_period("M").astype(str))
    .size()
    .reset_index(name="proyectos")
    .rename(columns={"fecha_presentacion": "mes"})
)
st.plotly_chart(px.bar(timeline, x="mes", y="proyectos"), use_container_width=True)

st.subheader("Proyectos por estado procesal")
st.plotly_chart(px.pie(df_proyectos, names="estado"), use_container_width=True)

st.subheader("Proyectos por bancada")
if "bancada" in df_proyectos.columns and df_proyectos["bancada"].notna().any():
    st.plotly_chart(px.bar(df_proyectos["bancada"].value_counts().reset_index(), x="bancada", y="count"), use_container_width=True)
else:
    st.info("Sin datos de bancada todavía — corre el scraper de nuevo.")

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
    tabla[["proyecto_ley", "fecha_presentacion", "titulo", "estado", "proponente", "bancada"]],
    use_container_width=True,
)

st.caption(
    "Nota: la clasificación por región del congresista todavía no está disponible — "
    "el Congreso no expone esa información por API junto con los proyectos, y cruzarla "
    "requiere un directorio externo (ONPE) que aún no está integrado."
)
