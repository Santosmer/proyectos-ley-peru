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

TODOS = "— TODOS —"
TODAS = "— TODAS —"

# Dos etiquetas "sin clasificar" DISTINTAS a propósito (bancada vs. temática).
BANCADA_OTROS = "Instituciones con Iniciativa Legislativa"
TEMA_OTROS = "Otros"

# Orden fijo para el selector de "Dashboard por partido" (no alfabético).
ORDEN_PARTIDOS = [
    "Fuerza Popular", "Juntos por el Perú", "Renovación Popular",
    "Partido del Buen Gobierno", "Partido Cívico Obras", "Ahora Nación",
]

# Colores por bancada, ajustados a los colores reales de cada logo/marca
# partidaria. Partido Cívico Obras se deja en blanco (excluido, a pedido).
COLOR_BANCADA = {
    "Fuerza Popular": "#F7931E",
    "Renovación Popular": "#29ABE2",
    "Partido del Buen Gobierno": "#FFD400",
    "Partido Cívico Obras": "#F5F5F5",
    "Ahora Nación": "#E4032E",
    "Juntos por el Perú": "#2E7D32",
    "Multipartidario": "#1E63C8",
    BANCADA_OTROS: "#C8A2C8",
}

LOGO_PARTIDO = {
    "Fuerza Popular": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/1366_FUERZA%20POPULAR.jpg",
    "Juntos por el Perú": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/1264_JUNTOS%20POR%20EL%20PERU.jpg",
    "Partido del Buen Gobierno": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2961_PARTIDO%20DEL%20BUEN%20GOBIERNO.jpg",
    "Renovación Popular": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/22_RENOVACION%20POPULAR.jpg",
    "Partido Cívico Obras": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2941_PARTIDO%20CIVICO%20OBRAS.jpg",
    "Ahora Nación": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2980_AHORA%20NACION%20-%20AN.jpg",
}

TEMAS_KEYWORDS = [
    ("Derechos Humanos", ["derechos humanos"]),
    ("Reglamentos del Congreso", ["reglamento del congreso", "reglamento del parlamento"]),
    ("Mujer", ["mujer", "igualdad de género", "igualdad de genero", "violencia de género", "violencia de genero", "feminicidio", "paridad"]),
    ("Salud", ["salud", "essalud", "hospital", "médic", "medic", "sanitari", "enfermedad", "vacuna", "minsa", "cáncer", "cancer"]),
    ("Universidades", ["universi", "sunedu", "licenciamiento"]),
    ("Educación", ["educ", "escolar", "docente", "estudiant", "colegio", "pedagóg"]),
    ("Pensiones", ["pension", "jubila", "afp", "onp", "cesant"]),
    ("Empleo", ["trabaj", "laboral", "empleo", "sindical", "remuneraci"]),
    ("Electoral", ["electoral", "elecciones", "voto", "onpe", "jne", "partido político", "sufragio"]),
    ("Niñez", ["niño", "niña", "infantil", "menor de edad", "adolescen"]),
    ("Agricultura", ["agricultura", "agrari", "agropecuari", "riego", "irrigaci", "campesin"]),
    ("Producción", ["industri", "pesc", "minero", "minería", "mype", "empresa", "comercio"]),
    ("Transportes", ["transporte", "vial", "tránsito", "transito", "carretera", "ferroviari", "aeropuerto", "puerto", "vehicular", "peaje"]),
    ("Vivienda", ["vivienda", "urbanístic", "urbanistic", "saneamiento físico legal", "saneamiento fisico legal", "titulación", "titulacion"]),
    ("Tributario", ["tributari", "impuesto", "sunat", "igv", " renta"]),
    ("Relaciones Exteriores", ["exterior", "diplomátic", "tratado internacional", "migrant", "frontera"]),
    ("OCDE", ["ocde", "cooperación y el desarrollo económicos", "cooperacion y el desarrollo economicos"]),
    ("Reforma Constitucional", ["constitución", "constitucional"]),
    ("Seguridad", ["seguridad ciudadana", "polic", "delin", "crimin", "penal"]),
    ("Justicia", ["judicial", "código civil", "código procesal", "justicia"]),
    ("Descentralización", ["gobierno regional", "gobierno local", "municipal", "descentraliza"]),
    ("Medio Ambiente", ["ambiental", "ecológ", "forestal", "recursos naturales", "residuos"]),
    ("Fenómeno El Niño", ["fenómeno del niño", "fenomeno del nino", "friaje", "sequía", "sequia", "emergencia climátic", "emergencia climatic"]),
    ("Consumidor", ["consumidor"]),
    ("Inteligencia Artificial", ["inteligencia artificial", "algoritmo", "big data", "machine learning"]),
    ("Cultura", ["cultura", "patrimonio cultural", "artesan", "museo", "folclor", "folklor"]),
    ("Normas Declarativas", ["declara de interés", "declara de interes", "declárase", "declarase",
                             "día del", "dia del", "día nacional", "dia nacional",
                             "reconócese", "reconocese", "denomínase", "denominase"]),
]


def clasificar_tema(titulo: str) -> str:
    t = (titulo or "").lower()
    for tema, palabras in TEMAS_KEYWORDS:
        if any(p in t for p in palabras):
            return tema
    return TEMA_OTROS


def norm_tokens(s: str) -> set:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z ]", " ", s).upper()
    return {t for t in s.split() if t not in ("DE", "DEL", "LA", "LOS", "LAS", "Y")}


def mejor_match(tokens_objetivo: set, candidatos: dict, min_score: int = 3):
    best_key, best_score, best_ratio = None, 0, 0.0
    for key, toks in candidatos.items():
        inter = tokens_objetivo & toks
        score = len(inter)
        smaller = min(len(tokens_objetivo), len(toks)) or 1
        ratio = score / smaller
        if score > best_score or (score == best_score and ratio > best_ratio):
            best_key, best_score, best_ratio = key, score, ratio
    if best_key and (best_score >= min_score or (best_score >= 2 and best_ratio == 1.0)):
        return best_key, best_score, best_ratio
    return None, 0, 0.0


def construir_link(row) -> str:
    """Enlace al expediente del proyecto en el portal público del Congreso.
    Patrón CONFIRMADO EN VIVO: se probó
    https://wb2server.congreso.gob.pe/spley-portal/#/diputados/expediente/2026/420
    y cargó exactamente el proyecto 00420-2026-2031-CD. Sin ceros a la
    izquierda, sin codTipoParl, con 'diputados' en la ruta (no 'congreso',
    que es lo que usa el Congreso anterior 2021-2026)."""
    try:
        periodo = int(row["periodo"])
        ply_num = int(row["ply_num"])
    except (TypeError, ValueError, KeyError):
        return ""
    return f"https://wb2server.congreso.gob.pe/spley-portal/#/diputados/expediente/{periodo}/{ply_num}"


@st.cache_data
def load_data():
    proyectos = json.loads((DATA_DIR / "proyectos.json").read_text(encoding="utf-8"))
    autorias = json.loads((DATA_DIR / "autorias.json").read_text(encoding="utf-8"))
    directorio_path = ROOT_DIR / "diputados_regiones.json"
    directorio = json.loads(directorio_path.read_text(encoding="utf-8")) if directorio_path.exists() else []
    for d in directorio:
        d["tokens"] = norm_tokens(d["nombre_fuente"])
    return pd.DataFrame(proyectos), pd.DataFrame(autorias), directorio


def buscar_region(persona: str, directorio: list):
    candidatos = {i: d["tokens"] for i, d in enumerate(directorio)}
    idx, score, ratio = mejor_match(norm_tokens(persona), candidatos)
    if idx is None:
        return None, None
    d = directorio[idx]
    return d["region"], d["partido"]


@st.cache_data
def contar_proyectos_por_diputado(_directorio, _df_autorias):
    personas_unicas = _df_autorias["persona"].dropna().unique().tolist()
    tokens_personas = {p: norm_tokens(p) for p in personas_unicas}
    conteo_total = _df_autorias["persona"].value_counts().to_dict()
    conteo_por_rol = _df_autorias.groupby(["persona", "rol"]).size().unstack(fill_value=0)

    filas = []
    for d in _directorio:
        persona_match, score, ratio = mejor_match(d["tokens"], tokens_personas)
        n_proyectos = conteo_total.get(persona_match, 0) if persona_match else 0
        n_autor = int(conteo_por_rol.loc[persona_match, "autor_principal"]) if (
            persona_match and persona_match in conteo_por_rol.index and "autor_principal" in conteo_por_rol.columns
        ) else 0
        n_coautor = int(conteo_por_rol.loc[persona_match, "coautor"]) if (
            persona_match and persona_match in conteo_por_rol.index and "coautor" in conteo_por_rol.columns
        ) else 0
        n_adherente = int(conteo_por_rol.loc[persona_match, "adherente"]) if (
            persona_match and persona_match in conteo_por_rol.index and "adherente" in conteo_por_rol.columns
        ) else 0
        filas.append({
            "Región": d["region"],
            "Partido": d["partido"],
            "Nombre": d["nombre_fuente"],
            "Proyectos": n_proyectos,
            "Como autor principal": n_autor,
            "Como coautor": n_coautor,
            "Como adherente": n_adherente,
        })
    return pd.DataFrame(filas)


@st.cache_data
def mapear_proyectos_a_region(_directorio, _df_autorias):
    """Une cada firma (persona, proyecto_ley) con la región de esa persona
    en la nómina oficial, para poder armar el dashboard por región. Un
    proyecto con coautores de dos regiones distintas cuenta para ambas."""
    tokens_dir = {i: d["tokens"] for i, d in enumerate(_directorio)}
    cache_persona = {}
    filas = []
    for _, row in _df_autorias.iterrows():
        persona = row["persona"]
        if persona not in cache_persona:
            idx, score, ratio = mejor_match(norm_tokens(persona), tokens_dir)
            cache_persona[persona] = _directorio[idx]["region"] if idx is not None else None
        region = cache_persona[persona]
        if region:
            filas.append({"proyecto_ley": row["proyecto_ley"], "region": region})
    return pd.DataFrame(filas).drop_duplicates()


def ordenar_partidos(lista: list) -> list:
    resto = sorted([p for p in lista if p not in ORDEN_PARTIDOS])
    ordenados = [p for p in ORDEN_PARTIDOS if p in lista]
    return ordenados + resto


RENOMBRAR_COLUMNAS = {
    "proyecto_ley": "Proposición legislativa",
    "fecha_presentacion": "Fecha de presentación",
    "titulo": "Título",
    "estado": "Estado",
    "proponente": "Proponente",
    "bancada": "Bancada",
    "tema_aprox": "Tema (aproximación)",
    "link": "Enlace",
}


def preparar_para_mostrar(df: pd.DataFrame, columnas: list) -> pd.DataFrame:
    d = df[columnas].copy()
    if "fecha_presentacion" in d.columns:
        d["fecha_presentacion"] = d["fecha_presentacion"].dt.strftime("%d/%m/%Y")
    return d.rename(columns=RENOMBRAR_COLUMNAS)


def filtros_multiselect(df: pd.DataFrame, columnas: list, prefix: str) -> pd.DataFrame:
    filtrado = df.copy()
    cols_widgets = st.columns(len(columnas))
    for col_widget, nombre_col in zip(cols_widgets, columnas):
        opciones = sorted(df[nombre_col].dropna().unique().tolist())
        with col_widget:
            seleccion = st.multiselect(nombre_col, opciones, key=f"{prefix}_{nombre_col}")
        if seleccion:
            filtrado = filtrado[filtrado[nombre_col].isin(seleccion)]
    return filtrado


_tabla_counter = [0]


def mostrar_tabla(df: pd.DataFrame, link_col: str = None):
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    config = {}
    if link_col and link_col in df.columns:
        config[link_col] = st.column_config.LinkColumn(link_col, display_text="Abrir ↗")
    _tabla_counter[0] += 1
    st.dataframe(df, use_container_width=True, column_config=config, key=f"tabla_{_tabla_counter[0]}")


def tabla_con_agrupado(df: pd.DataFrame, columna_valor: str = "Proyectos"):
    """Selector 'Agrupar por' + resumen (N° de filas y suma de la columna
    de valor por cada grupo — cada opción dentro de la columna, p. ej.
    Lima Metropolitana y Lima Provincias, aparece como su propio grupo)
    más la tabla de detalle ordenada por ese mismo criterio."""
    opciones_agrupar = [c for c in ["Región", "Partido"] if c in df.columns]
    agrupar_por = st.selectbox("Agrupar por", ["Sin agrupar"] + opciones_agrupar, key=f"agrupar_{id(df)}")
    if agrupar_por != "Sin agrupar":
        resumen = (
            df.groupby(agrupar_por)
            .agg(Diputados=("Nombre", "count"), **{f"{columna_valor} (total)": (columna_valor, "sum")})
            .reset_index()
            .sort_values(f"{columna_valor} (total)", ascending=False)
        )
        st.caption(f"Resumen agrupado por {agrupar_por} (cada valor de la columna es su propio grupo):")
        mostrar_tabla(resumen)
        df = df.sort_values([agrupar_por, columna_valor], ascending=[True, False])
    mostrar_tabla(df)


def bar_con_etiquetas(df: pd.DataFrame, x: str, y: str, color: str = None,
                       color_discrete_map: dict = None, orientation: str = "v", **kwargs):
    """px.bar con el número y el porcentaje del total escritos junto a cada barra.
    orientation='h' para barras horizontales (x=valores, y=categorías)."""
    df = df.copy()
    val_col = y if orientation == "v" else x
    total = df[val_col].sum()
    df["_pct"] = (df[val_col] / total * 100) if total else 0
    df["_label"] = df.apply(lambda r: f"{int(r[val_col])} ({r['_pct']:.1f}%)", axis=1)
    fig = px.bar(
        df, x=x, y=y, color=color, color_discrete_map=color_discrete_map,
        text="_label", orientation=orientation, **kwargs,
    )
    if orientation == "h":
        fig.update_traces(textposition="outside")
        fig.update_layout(margin=dict(r=90))
    else:
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(margin=dict(t=60))
    return fig


def agregar_logos_dentro_de_barras(fig, df: pd.DataFrame, x_col: str, y_col: str,
                                    fraccion_alto: float = 0.35, sizex: float = 0.55):
    for _, row in df.iterrows():
        cat, val = row[x_col], row[y_col]
        url = LOGO_PARTIDO.get(cat)
        if not url or val <= 0:
            continue
        alto_logo = val * fraccion_alto
        fig.add_layout_image(dict(
            source=url, xref="x", yref="y",
            x=cat, y=alto_logo, sizex=sizex, sizey=alto_logo,
            xanchor="center", yanchor="middle",
        ))
    return fig


def fila_logos_con_hover(conteo: dict, total: int):
    html = "<div style='display:flex; gap:28px; align-items:flex-end; flex-wrap:wrap;'>"
    for partido, url in LOGO_PARTIDO.items():
        n = int(conteo.get(partido, 0))
        pct = (n / total * 100) if total else 0
        html += (
            f"<div style='text-align:center;' title='{partido}: {n} proyectos ({pct:.1f}%)'>"
            f"<img src='{url}' width='60' style='display:block; margin:0 auto;'>"
            f"<div style='font-size:12px; margin-top:4px;'>{partido}</div>"
            f"<div style='font-size:11px; color:#666;'>{n} · {pct:.1f}%</div>"
            f"</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


df_proyectos, df_autorias, directorio = load_data()
df_proyectos["fecha_presentacion"] = pd.to_datetime(df_proyectos["fecha_presentacion"])
df_proyectos["tema_aprox"] = df_proyectos["titulo"].apply(clasificar_tema)
df_proyectos["bancada"] = df_proyectos["bancada"].fillna("").replace("", BANCADA_OTROS)
df_proyectos["link"] = df_proyectos.apply(construir_link, axis=1)

st.title("Proyectos de Ley — Congreso del Perú (2026-2031)")
st.caption(f"{len(df_proyectos)} proyectos registrados · datos actualizados automáticamente")

col1, col2, col3 = st.columns(3)
col1.metric("Total de proyectos", len(df_proyectos))
col2.metric("Personas involucradas", df_autorias["persona"].nunique())
col3.metric("Proponentes distintos", df_proyectos["proponente"].nunique())

tab_general, tab_partidos, tab_temas, tab_regiones, tab_diputados = st.tabs(
    ["📊 General", "🏛️ Dashboard por partido", "📚 Dashboard por temática",
     "🗺️ Dashboard por región", "🧑‍💼 Diputados"]
)

# ----------------------------------------------------------------------
# TAB: GENERAL
# ----------------------------------------------------------------------
with tab_general:
    st.subheader("Proyectos presentados por mes")
    tmp = df_proyectos.copy()
    tmp["mes_num"] = tmp["fecha_presentacion"].dt.month
    tmp["anio"] = tmp["fecha_presentacion"].dt.year
    tmp["mes_orden"] = tmp["fecha_presentacion"].dt.to_period("M")
    timeline = (
        tmp.groupby(["mes_orden", "mes_num", "anio"]).size().reset_index(name="proyectos").sort_values("mes_orden")
    )
    timeline["mes"] = timeline.apply(lambda r: f"{MESES_ES[r['mes_num']]} {r['anio']}", axis=1)
    st.plotly_chart(bar_con_etiquetas(timeline, x="mes", y="proyectos"), use_container_width=True, key="chart_1")

    st.subheader("Proyectos por estado procesal")
    st.plotly_chart(px.pie(df_proyectos, names="estado"), use_container_width=True, key="chart_2")

    st.subheader("Proyectos por bancada")
    banc = df_proyectos["bancada"].value_counts().reset_index()
    banc.columns = ["bancada", "count"]

    st.caption("Pasa el cursor sobre cada logo para ver su número de proyectos y porcentaje.")
    fila_logos_con_hover(df_proyectos["bancada"].value_counts().to_dict(), len(df_proyectos))

    fig_banc = bar_con_etiquetas(banc, x="bancada", y="count", color="bancada", color_discrete_map=COLOR_BANCADA)
    fig_banc.update_traces(marker_line_color="#999", marker_line_width=1)
    fig_banc.update_layout(showlegend=False)
    fig_banc = agregar_logos_dentro_de_barras(fig_banc, banc, "bancada", "count")
    st.plotly_chart(fig_banc, use_container_width=True, key="chart_3")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Por sexo (personas distintas)")
        if "sexo" in df_autorias.columns and df_autorias["sexo"].notna().any():
            personas_sexo = df_autorias.drop_duplicates("persona")["sexo"].value_counts().reset_index()
            personas_sexo.columns = ["Sexo", "Congresistas"]
            st.plotly_chart(px.pie(personas_sexo, names="Sexo", values="Congresistas"), use_container_width=True, key="chart_4")
        else:
            st.info("Sin datos de sexo todavía — corre el scraper de nuevo.")
    with col_b:
        st.subheader("Proyectos por sexo del firmante")
        if "sexo" in df_autorias.columns and df_autorias["sexo"].notna().any():
            st.plotly_chart(px.pie(df_autorias, names="sexo"), use_container_width=True, key="chart_5")
        else:
            st.info("Sin datos de sexo todavía — corre el scraper de nuevo.")

    st.subheader("Explorar proyectos")
    busqueda = st.text_input("Buscar por palabra clave en el título")
    tabla = df_proyectos
    if busqueda:
        tabla = tabla[tabla["titulo"].str.contains(busqueda, case=False, na=False)]
    tabla_f = filtros_multiselect(tabla, ["bancada", "estado", "tema_aprox"], prefix="explorar")
    mostrar_tabla(
        preparar_para_mostrar(
            tabla_f, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "bancada", "tema_aprox", "link"]
        ),
        link_col="Enlace",
    )

# ----------------------------------------------------------------------
# TAB: DASHBOARD POR PARTIDO
# ----------------------------------------------------------------------
with tab_partidos:
    partidos_disponibles = [TODOS] + ordenar_partidos(df_proyectos["bancada"].dropna().unique().tolist())
    partido_sel = st.selectbox("Elige un partido / bancada", partidos_disponibles)

    if partido_sel == TODOS:
        proy_partido = df_proyectos
        st.metric("Proyectos (todos los partidos)", len(proy_partido))

        st.subheader("Proyectos por partido")
        banc_todos = proy_partido["bancada"].value_counts().reset_index()
        banc_todos.columns = ["bancada", "proyectos"]
        fig_todos = bar_con_etiquetas(banc_todos, x="bancada", y="proyectos", color="bancada",
                                       color_discrete_map=COLOR_BANCADA)
        fig_todos.update_layout(showlegend=False)
        st.plotly_chart(fig_todos, use_container_width=True, key="chart_6")

        st.subheader("Temáticas (todos los partidos)")
        temas_todos = proy_partido["tema_aprox"].value_counts().reset_index()
        temas_todos.columns = ["tema", "proyectos"]
        st.plotly_chart(
            bar_con_etiquetas(temas_todos.sort_values("proyectos"), x="proyectos", y="tema", orientation="h"),
            use_container_width=True,
        key="chart_11",
    )

        st.subheader("Todos los diputados y sus proyectos")
        tabla_diputados = contar_proyectos_por_diputado(directorio, df_autorias)
        tabla_con_agrupado(tabla_diputados.sort_values("Proyectos", ascending=False))
    else:
        proy_partido = df_proyectos[df_proyectos["bancada"] == partido_sel]
        color_partido = COLOR_BANCADA.get(partido_sel, "#4C78A8")

        c1, c2, c3 = st.columns([1, 2, 2])
        with c1:
            if partido_sel in LOGO_PARTIDO:
                st.image(LOGO_PARTIDO[partido_sel], width=90)
        c2.metric("Proyectos de este partido", len(proy_partido))
        c2.metric("% del total", f"{len(proy_partido) / len(df_proyectos) * 100:.1f}%")
        diputados_partido = [d for d in directorio if d["partido"] == partido_sel]
        c3.metric("Diputados en la nómina", len(diputados_partido))

        st.subheader(f"Temáticas de {partido_sel}")
        temas_partido = proy_partido["tema_aprox"].value_counts().reset_index()
        temas_partido.columns = ["tema", "proyectos"]
        fig_tp = bar_con_etiquetas(temas_partido.sort_values("proyectos"), x="proyectos", y="tema", orientation="h")
        fig_tp.update_traces(marker_color=color_partido, marker_line_color="#999", marker_line_width=1)
        st.plotly_chart(fig_tp, use_container_width=True, key="chart_7")

        st.subheader(f"Diputados de {partido_sel} y sus proyectos")
        tabla_diputados = contar_proyectos_por_diputado(directorio, df_autorias)
        tabla_partido = tabla_diputados[tabla_diputados["Partido"] == partido_sel].sort_values(
            "Proyectos", ascending=False
        )
        if tabla_partido.empty:
            st.info("Esta bancada no tiene diputados en la nómina oficial (es una categoría institucional, no un partido).")
        else:
            tabla_con_agrupado(tabla_partido)

# ----------------------------------------------------------------------
# TAB: DASHBOARD POR TEMÁTICA
# ----------------------------------------------------------------------
with tab_temas:
    st.caption(
        "La clasificación temática es una aproximación por palabras clave en el título — "
        "no es oficial del Congreso."
    )
    temas_disponibles = [TODAS] + sorted(df_proyectos["tema_aprox"].unique().tolist())
    tema_sel = st.selectbox("Elige una temática", temas_disponibles)

    if tema_sel == TODAS:
        proy_tema = df_proyectos
        st.metric("Proyectos (todas las temáticas)", len(proy_tema))

        st.subheader("Proyectos por temática")
        temas_todos = proy_tema["tema_aprox"].value_counts().reset_index()
        temas_todos.columns = ["tema", "proyectos"]
        st.plotly_chart(
            bar_con_etiquetas(temas_todos.sort_values("proyectos"), x="proyectos", y="tema", orientation="h"),
            use_container_width=True,
        key="chart_12",
    )

        st.subheader("Por bancada (todas las temáticas)")
        banc_todos = proy_tema["bancada"].value_counts().reset_index()
        banc_todos.columns = ["bancada", "proyectos"]
        fig_bt = bar_con_etiquetas(banc_todos, x="bancada", y="proyectos", color="bancada",
                                    color_discrete_map=COLOR_BANCADA)
        fig_bt.update_layout(showlegend=False)
        st.plotly_chart(fig_bt, use_container_width=True, key="chart_8")
    else:
        proy_tema = df_proyectos[df_proyectos["tema_aprox"] == tema_sel]

        c1, c2 = st.columns(2)
        c1.metric("Proyectos en esta temática", len(proy_tema))
        c2.metric("% del total", f"{len(proy_tema) / len(df_proyectos) * 100:.1f}%")

        st.subheader(f"'{tema_sel}' por bancada")
        banc_tema = proy_tema["bancada"].value_counts().reset_index()
        banc_tema.columns = ["bancada", "proyectos"]
        fig_tema = bar_con_etiquetas(banc_tema, x="bancada", y="proyectos", color="bancada",
                                      color_discrete_map=COLOR_BANCADA)
        fig_tema.update_traces(marker_line_color="#999", marker_line_width=1)
        fig_tema.update_layout(showlegend=False)
        fig_tema = agregar_logos_dentro_de_barras(fig_tema, banc_tema, "bancada", "proyectos")
        st.plotly_chart(fig_tema, use_container_width=True, key="chart_9")

    st.subheader(f"Proyectos de '{tema_sel}'" if tema_sel != TODAS else "Todos los proyectos")
    proy_tema_f = filtros_multiselect(proy_tema, ["bancada", "estado"], prefix="tema")
    mostrar_tabla(
        preparar_para_mostrar(proy_tema_f, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "bancada", "link"]),
        link_col="Enlace",
    )

# ----------------------------------------------------------------------
# TAB: DASHBOARD POR REGIÓN
# ----------------------------------------------------------------------
with tab_regiones:
    st.caption(
        "Un proyecto cuenta para una región si al menos uno de sus firmantes es diputado "
        "de esa región (según la nómina oficial). Un proyecto con coautores de dos "
        "regiones distintas cuenta para ambas."
    )
    proy_region_map = mapear_proyectos_a_region(directorio, df_autorias)
    proy_con_region = proy_region_map.merge(df_proyectos, on="proyecto_ley", how="left")

    regiones_disponibles = [TODAS] + sorted(proy_region_map["region"].unique().tolist())
    region_sel = st.selectbox("Elige una región", regiones_disponibles)

    if region_sel == TODAS:
        proy_r = proy_con_region
        st.metric("Firmas región × proyecto (todas las regiones)", len(proy_r))

        st.subheader("Proyectos por región")
        por_region = proy_region_map["region"].value_counts().reset_index()
        por_region.columns = ["region", "proyectos"]
        st.plotly_chart(
            bar_con_etiquetas(por_region.sort_values("proyectos"), x="proyectos", y="region", orientation="h"),
            use_container_width=True,
        key="chart_13",
    )
    else:
        proy_r = proy_con_region[proy_con_region["region"] == region_sel]
        diputados_region = [d for d in directorio if d["region"] == region_sel]

        c1, c2 = st.columns(2)
        c1.metric("Proyectos con algún firmante de esta región", proy_r["proyecto_ley"].nunique())
        c2.metric("Diputados de la región en la nómina", len(diputados_region))

        st.subheader(f"Temáticas — {region_sel}")
        temas_region = proy_r["tema_aprox"].value_counts().reset_index()
        temas_region.columns = ["tema", "proyectos"]
        st.plotly_chart(
            bar_con_etiquetas(temas_region.sort_values("proyectos"), x="proyectos", y="tema", orientation="h"),
            use_container_width=True,
        key="chart_14",
    )

        st.subheader(f"Bancadas — {region_sel}")
        banc_region = proy_r["bancada"].value_counts().reset_index()
        banc_region.columns = ["bancada", "proyectos"]
        fig_br = bar_con_etiquetas(banc_region, x="bancada", y="proyectos", color="bancada",
                                    color_discrete_map=COLOR_BANCADA)
        fig_br.update_layout(showlegend=False)
        st.plotly_chart(fig_br, use_container_width=True, key="chart_10")

        st.subheader(f"Diputados de {region_sel}")
        tabla_diputados = contar_proyectos_por_diputado(directorio, df_autorias)
        mostrar_tabla(tabla_diputados[tabla_diputados["Región"] == region_sel].sort_values("Proyectos", ascending=False))

# ----------------------------------------------------------------------
# TAB: DIPUTADOS
# ----------------------------------------------------------------------
with tab_diputados:
    st.subheader("Todos los diputados y sus proyectos")
    st.caption(
        "Los 130 diputados de la nómina oficial, con la cantidad de proyectos en los que "
        "participó cada uno (0 si todavía no presenta ninguno)."
    )
    tabla_diputados = contar_proyectos_por_diputado(directorio, df_autorias)
    tabla_diputados = tabla_diputados.sort_values(["Partido", "Proyectos"], ascending=[True, False])
    tabla_diputados_f = filtros_multiselect(tabla_diputados, ["Partido", "Región", "Nombre"], prefix="diputados")
    mostrar_tabla(tabla_diputados_f)

    st.subheader("Buscar diputado/a (con región y proyectos)")
    nombres = sorted(df_autorias["persona"].dropna().unique().tolist())
    if nombres:
        seleccionado = st.selectbox("Diputado/a", nombres)
        autorias_persona = df_autorias[df_autorias["persona"] == seleccionado][["proyecto_ley", "rol"]]
        detalle = df_proyectos.merge(autorias_persona, on="proyecto_ley", how="inner")
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
                "No se pudo identificar la región para este nombre en la nómina oficial — "
                "puede tratarse de una diferencia de escritura del nombre entre ambas fuentes."
            )
        c5, c6, c7 = st.columns(3)
        c5.metric("Como autor principal", int((detalle["rol"] == "autor_principal").sum()))
        c6.metric("Como coautor", int((detalle["rol"] == "coautor").sum()))
        c7.metric("Como adherente", int((detalle["rol"] == "adherente").sum()))

        ROL_LEGIBLE = {"autor_principal": "Autor principal", "coautor": "Coautor", "adherente": "Adherente"}
        detalle["rol"] = detalle["rol"].map(ROL_LEGIBLE).fillna(detalle["rol"])
        detalle_mostrar = preparar_para_mostrar(
            detalle, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "tema_aprox", "rol", "link"]
        ).rename(columns={"rol": "Rol"})
        mostrar_tabla(detalle_mostrar, link_col="Enlace")

    st.subheader("Directorio de diputados electos")
    st.caption(
        f"Nómina oficial de los {len(directorio)} de 130 diputados proclamados para el "
        "periodo 2026-2031 — provista por el usuario."
    )
    if directorio:
        dir_df = pd.DataFrame([{"Región": d["region"], "Partido": d["partido"], "Nombre": d["nombre_fuente"]}
                                for d in directorio])
        dir_df_f = filtros_multiselect(dir_df, ["Región", "Partido", "Nombre"], prefix="directorio")
        mostrar_tabla(dir_df_f.sort_values(["Región", "Partido", "Nombre"]))

st.caption(
    "Notas: (1) la región y el directorio completo vienen de la nómina oficial de los "
    "130 diputados proclamados; el cruce de nombres entre ambas fuentes es automático "
    "por coincidencia de palabras, no exacto. (2) La clasificación temática es una "
    "aproximación por palabras clave, no oficial. (3) El enlace a cada proyecto se "
    "verificó en vivo contra el portal del Congreso."
)
