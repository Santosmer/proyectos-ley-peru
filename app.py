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

# Dos etiquetas "sin clasificar" DISTINTAS a propósito:
# - BANCADA_OTROS: para proyectos sin bancada (propuestos por el Ejecutivo,
#   Judicial, colegios profesionales, etc.) — aparece en gráficos de bancada.
# - TEMA_OTROS: para proyectos cuyo título no calzó con ninguna palabra
#   clave — aparece SOLO en gráficos de temática. Antes usaban el mismo
#   texto; ahora están separados a pedido.
BANCADA_OTROS = "Instituciones con Iniciativa Legislativa"
TEMA_OTROS = "Otros"

# Orden fijo para el selector de "Dashboard por partido" (no alfabético).
ORDEN_PARTIDOS = [
    "Fuerza Popular", "Juntos por el Perú", "Renovación Popular",
    "Partido del Buen Gobierno", "Partido Cívico Obras", "Ahora Nación",
]

# Colores por bancada, ajustados a los colores reales de cada logo/marca
# partidaria (verificado contra fuentes públicas: Wikipedia, prensa).
# Partido Cívico Obras se deja en blanco (excluido del ajuste, a pedido).
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

# Logos oficiales de cada partido, tomados de decideperu.com (fuente pública,
# resultados JNE 2026).
LOGO_PARTIDO = {
    "Fuerza Popular": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/1366_FUERZA%20POPULAR.jpg",
    "Juntos por el Perú": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/1264_JUNTOS%20POR%20EL%20PERU.jpg",
    "Partido del Buen Gobierno": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2961_PARTIDO%20DEL%20BUEN%20GOBIERNO.jpg",
    "Renovación Popular": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/22_RENOVACION%20POPULAR.jpg",
    "Partido Cívico Obras": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2941_PARTIDO%20CIVICO%20OBRAS.jpg",
    "Ahora Nación": "https://d26x1qb2ouso7w.cloudfront.net/PartidosPeru2026/2980_AHORA%20NACION%20-%20AN.jpg",
}

# Clasificación TEMÁTICA APROXIMADA, por palabras clave en el título.
# Esto NO es una clasificación oficial del Congreso. Un proyecto puede
# tocar varios temas; aquí se le asigna el primero que calce.
TEMAS_KEYWORDS = [
    ("Derechos Humanos", ["derechos humanos"]),
    ("Salud", ["salud", "essalud", "hospital", "médic", "medic", "sanitari", "enfermedad", "vacuna", "minsa", "cáncer", "cancer"]),
    ("Educación", ["educ", "escolar", "universi", "docente", "estudiant", "colegio", "pedagóg"]),
    ("Empleo", ["trabaj", "laboral", "empleo", "sindical", "remuneraci", "pension", "jubila"]),
    ("Electoral", ["electoral", "elecciones", "voto", "onpe", "jne", "partido político", "sufragio"]),
    ("Niñez", ["niño", "niña", "infantil", "menor de edad", "adolescen"]),
    ("Agricultura", ["agricultura", "agrari", "agropecuari", "riego", "irrigaci", "campesin"]),
    ("Producción", ["industri", "pesc", "minero", "minería", "mype", "empresa", "comercio"]),
    ("Transportes", ["transporte", "vial", "tránsito", "transito", "carretera", "ferroviari", "aeropuerto", "puerto", "vehicular", "peaje"]),
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
    Patrón CONFIRMADO EN VIVO (no es una inferencia esta vez): se probó
    https://wb2server.congreso.gob.pe/spley-portal/#/diputados/expediente/2026/420
    y cargó exactamente el proyecto 00420-2026-2031-CD. Sin ceros a la
    izquierda en el número, sin codTipoParl, con 'diputados' en la ruta
    (no 'congreso', que es lo que usa el Congreso anterior 2021-2026)."""
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
    conteo = _df_autorias["persona"].value_counts().to_dict()

    filas = []
    for d in _directorio:
        persona_match, score, ratio = mejor_match(d["tokens"], tokens_personas)
        n_proyectos = conteo.get(persona_match, 0) if persona_match else 0
        filas.append({
            "Región": d["region"],
            "Partido": d["partido"],
            "Nombre": d["nombre_fuente"],
            "Proyectos": n_proyectos,
        })
    return pd.DataFrame(filas)


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
    "tema_aprox": "Tema",
    "link": "Enlace",
}


def preparar_para_mostrar(df: pd.DataFrame, columnas: list) -> pd.DataFrame:
    d = df[columnas].copy()
    if "fecha_presentacion" in d.columns:
        d["fecha_presentacion"] = d["fecha_presentacion"].dt.strftime("%d/%m/%Y")
    return d.rename(columns=RENOMBRAR_COLUMNAS)


def filtros_multiselect(df: pd.DataFrame, columnas: list, prefix: str) -> pd.DataFrame:
    """Un desplegable de selección múltiple por columna, con las opciones
    reales que existen en los datos — el equivalente práctico en Streamlit
    al filtro de Excel (elige qué valores ver), aunque vive arriba de la
    tabla en vez de dentro del clic del encabezado."""
    filtrado = df.copy()
    cols_widgets = st.columns(len(columnas))
    for col_widget, nombre_col in zip(cols_widgets, columnas):
        opciones = sorted(df[nombre_col].dropna().unique().tolist())
        with col_widget:
            seleccion = st.multiselect(nombre_col, opciones, key=f"{prefix}_{nombre_col}")
        if seleccion:
            filtrado = filtrado[filtrado[nombre_col].isin(seleccion)]
    return filtrado


def mostrar_tabla(df: pd.DataFrame, link_col: str = None):
    """Tabla con el índice empezando en 1, y la columna de enlace (si existe)
    como link clicable de verdad (st.column_config.LinkColumn)."""
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    config = {}
    if link_col and link_col in df.columns:
        config[link_col] = st.column_config.LinkColumn(link_col, display_text="Abrir ↗")
    st.dataframe(df, use_container_width=True, column_config=config)


def bar_con_etiquetas(df: pd.DataFrame, x: str, y: str, color: str = None,
                       color_discrete_map: dict = None, **kwargs):
    df = df.copy()
    total = df[y].sum()
    df["_pct"] = (df[y] / total * 100) if total else 0
    df["_label"] = df.apply(lambda r: f"{int(r[y])} ({r['_pct']:.1f}%)", axis=1)
    fig = px.bar(
        df, x=x, y=y, color=color, color_discrete_map=color_discrete_map,
        text="_label", **kwargs,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(margin=dict(t=60))
    return fig


def agregar_logos_dentro_de_barras(fig, df: pd.DataFrame, x_col: str, y_col: str,
                                    fraccion_alto: float = 0.35, sizex: float = 0.55):
    """Coloca el logo DENTRO de cada barra (no encima), a una altura
    proporcional al valor de esa barra. Como Plotly no ancla imágenes a
    ejes categóricos con precisión de píxel, esto es aproximado — si un
    logo se ve cortado o desbordado, ajusta 'fraccion_alto' o 'sizex'."""
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

tab_general, tab_partidos, tab_temas, tab_diputados = st.tabs(
    ["📊 General", "🏛️ Dashboard por partido", "📚 Dashboard por temática", "🧑‍💼 Diputados"]
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
    st.plotly_chart(bar_con_etiquetas(timeline, x="mes", y="proyectos"), use_container_width=True)

    st.subheader("Proyectos por estado procesal")
    st.plotly_chart(px.pie(df_proyectos, names="estado"), use_container_width=True)

    st.subheader("Proyectos por bancada")
    banc = df_proyectos["bancada"].value_counts().reset_index()
    banc.columns = ["bancada", "count"]

    st.caption("Pasa el cursor sobre cada logo para ver su número de proyectos y porcentaje.")
    fila_logos_con_hover(df_proyectos["bancada"].value_counts().to_dict(), len(df_proyectos))

    fig_banc = bar_con_etiquetas(banc, x="bancada", y="count", color="bancada", color_discrete_map=COLOR_BANCADA)
    fig_banc.update_traces(marker_line_color="#999", marker_line_width=1)
    fig_banc.update_layout(showlegend=False)
    fig_banc = agregar_logos_dentro_de_barras(fig_banc, banc, "bancada", "count")
    st.plotly_chart(fig_banc, use_container_width=True)

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

    st.subheader("Explorar proyectos")
    busqueda = st.text_input("Buscar por palabra clave en el título")
    tabla = df_proyectos
    if busqueda:
        tabla = tabla[tabla["titulo"].str.contains(busqueda, case=False, na=False)]
    tabla_f = filtros_multiselect(tabla, ["bancada", "estado", "tema_aprox"], prefix="explorar")
    mostrar_tabla(
        preparar_para_mostrar(
            tabla_f, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "proponente", "bancada", "tema_aprox", "link"]
        ),
        link_col="Enlace",
    )

# ----------------------------------------------------------------------
# TAB: DASHBOARD POR PARTIDO
# ----------------------------------------------------------------------
with tab_partidos:
    partidos_disponibles = ordenar_partidos(df_proyectos["bancada"].dropna().unique().tolist())
    partido_sel = st.selectbox("Elige un partido / bancada", partidos_disponibles)

    proy_partido = df_proyectos[df_proyectos["bancada"] == partido_sel]

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
    st.plotly_chart(bar_con_etiquetas(temas_partido, x="tema", y="proyectos"), use_container_width=True)

    st.subheader(f"Diputados de {partido_sel} y sus proyectos")
    tabla_diputados = contar_proyectos_por_diputado(directorio, df_autorias)
    tabla_partido = tabla_diputados[tabla_diputados["Partido"] == partido_sel].sort_values(
        "Proyectos", ascending=False
    )
    if tabla_partido.empty:
        st.info("Esta bancada no tiene diputados en la nómina oficial (es una categoría institucional, no un partido).")
    else:
        mostrar_tabla(tabla_partido)

# ----------------------------------------------------------------------
# TAB: DASHBOARD POR TEMÁTICA
# ----------------------------------------------------------------------
with tab_temas:
    st.caption(
        "La clasificación temática es una aproximación por palabras clave en el título — "
        "no es oficial del Congreso."
    )
    temas_disponibles = sorted(df_proyectos["tema_aprox"].unique().tolist())
    tema_sel = st.selectbox("Elige una temática", temas_disponibles)

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
    st.plotly_chart(fig_tema, use_container_width=True)

    st.subheader(f"Proyectos de '{tema_sel}'")
    proy_tema_f = filtros_multiselect(proy_tema, ["bancada", "estado"], prefix="tema")
    mostrar_tabla(
        preparar_para_mostrar(proy_tema_f, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "bancada", "link"]),
        link_col="Enlace",
    )

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
                "No se pudo identificar la región para este nombre en la nómina oficial — "
                "puede tratarse de una diferencia de escritura del nombre entre ambas fuentes."
            )
        mostrar_tabla(
            preparar_para_mostrar(detalle, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "tema_aprox", "link"]),
            link_col="Enlace",
        )

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
