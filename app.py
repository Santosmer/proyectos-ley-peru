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

st.subheader("Proyectos presentados por día")
timeline = (
    df_proyectos.groupby(df_proyectos["fecha_presentacion"].dt.date)
    .size()
    .reset_index(name="proyectos")
)
st.plotly_chart(px.bar(timeline, x="fecha_presentacion", y="proyectos"), use_container_width=True)

st.subheader("Proyectos por estado procesal")
st.plotly_chart(px.pie(df_proyectos, names="estado"), use_container_width=True)

st.subheader("Congresistas con más proyectos (autor, coautor o adherente)")
st.caption(
    "Nota: la API de lista no distingue el rol de cada firmante — este conteo "
    "junta autor principal, coautores y adherentes. Ver README.md."
)
top_autores = df_autorias["persona"].value_counts().head(25).reset_index()
top_autores.columns = ["Congresista", "Proyectos"]
st.dataframe(top_autores, use_container_width=True)

st.subheader("Explorar proyectos")
busqueda = st.text_input("Buscar por palabra clave en el título")
tabla = df_proyectos
if busqueda:
    tabla = tabla[tabla["titulo"].str.contains(busqueda, case=False, na=False)]
st.dataframe(
    tabla[["proyecto_ley", "fecha_presentacion", "titulo", "estado", "proponente"]],
    use_container_width=True,
)
