requests
streamlit
pandas
plotly
pycryptodome
streamlit-aggrid

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

st.set_page_config(page_title="Proyectos de Ley — Congreso del Perú", layout="wide")

DATA_DIR = Path(__file__).parent / "data"
ROOT_DIR = Path(__file__).parent

MESES_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

OTROS_LABEL = "Instituciones con Iniciativa Legislativa"

# Colores por bancada, ajustados a los colores reales de cada logo/marca
# partidaria (verificado contra fuentes públicas: Wikipedia, prensa).
# Partido Cívico Obras se deja en blanco a pedido explícito (excluido del ajuste).
COLOR_BANCADA = {
    "Fuerza Popular": "#F7931E",                # naranja (color histórico del fujimorismo)
    "Renovación Popular": "#29ABE2",             # celeste
    "Partido del Buen Gobierno": "#FFD400",      # amarillo ("cyber yellow")
    "Partido Cívico Obras": "#F5F5F5",           # blanco (sin cambios, con borde para que se vea)
    "Ahora Nación": "#E4032E",                   # rojo
    "Juntos por el Perú": "#2E7D32",             # verde
    "Multipartidario": "#1E63C8",                # azul
    OTROS_LABEL: "#C8A2C8",                      # lila
}

# Logos oficiales de cada partido, tomados de decideperu.com (fuente pública,
# resultados JNE 2026). Se muestran con st.image / HTML directo desde la URL.
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
# primero que calce, en el orden de esta lista (por eso los temas más
# específicos van antes que los más genéricos). Lo que no calza con
# ninguna palabra clave se etiqueta igual que la bancada institucional:
# "Instituciones con Iniciativa Legislativa" — en la práctica, buena parte
# de esos proyectos sin tema claro vienen de proponentes institucionales
# (Poder Ejecutivo, Poder Judicial, colegios profesionales, etc.).
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
    return OTROS_LABEL


def norm_tokens(s: str) -> set:
    """Normaliza un nombre a un conjunto de palabras en mayúsculas sin tildes,
    para poder cruzar 'Apellidos, Nombres' contra 'Nombres Apellidos' sin
    depender del orden."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z ]", " ", s).upper()
    return {t for t in s.split() if t not in ("DE", "DEL", "LA", "LOS", "LAS", "Y")}


def mejor_match(tokens_objetivo: set, candidatos: dict, min_score: int = 3):
    """candidatos: {clave: set_de_tokens}. Devuelve (clave, score, ratio) del mejor match,
    o (None, 0, 0) si ninguno supera el umbral. Match válido si hay 3+ palabras en
    común, o si 2+ palabras cubren TODO el conjunto más chico (nombre abreviado)."""
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
    Patrón confirmado contra oficios reales del Congreso que citan este
    mismo formato (.../expediente/{periodo}/{numero}) — no probado en vivo
    contra un proyecto de ESTE periodo en particular, así que si algún
    enlace no abre, avisa para ajustarlo."""
    try:
        periodo = int(row["periodo"])
        ply_num = int(row["ply_num"])
    except (TypeError, ValueError, KeyError):
        return ""
    return f"https://wb2server.congreso.gob.pe/spley-portal/#/expediente/{periodo}/{ply_num}?codTipoParl=D"


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
    """Cruza un nombre 'Apellidos, Nombres' (Congreso) contra la nómina oficial
    de diputados ('Nombres Apellidos', Excel provisto por el usuario)."""
    candidatos = {i: d["tokens"] for i, d in enumerate(directorio)}
    idx, score, ratio = mejor_match(norm_tokens(persona), candidatos)
    if idx is None:
        return None, None
    d = directorio[idx]
    return d["region"], d["partido"]


@st.cache_data
def contar_proyectos_por_diputado(_directorio, _df_autorias):
    """Para cada uno de los diputados de la nómina oficial, cuenta cuántos
    proyectos tiene (cruzando el nombre contra df_autorias). 0 si no aparece
    en ningún proyecto todavía."""
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


# ----------------------------------------------------------------------
# Tabla filtrable estilo Excel (AgGrid): cada columna trae su propio filtro
# (contiene / igual a / mayor-menor según el tipo de dato), no solo orden
# ascendente/descendente. La numeración de filas empieza en 1.
# ----------------------------------------------------------------------
_grid_counter = [0]

_LINK_RENDERER = JsCode("""
class UrlCellRenderer {
  init(params) {
    this.eGui = document.createElement('a');
    if (params.value) {
      this.eGui.innerText = 'Abrir ↗';
      this.eGui.setAttribute('href', params.value);
      this.eGui.setAttribute('target', '_blank');
    } else {
      this.eGui.innerText = '';
    }
  }
  getGui() { return this.eGui; }
}
""")


def mostrar_tabla(df: pd.DataFrame, height: int = 420):
    df = df.reset_index(drop=True)
    df.insert(0, "N°", df.index + 1)

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(filter=True, floatingFilter=True, sortable=True, resizable=True)
    gb.configure_column("N°", pinned="left", width=70, filter=False, floatingFilter=False)
    if "Enlace" in df.columns:
        gb.configure_column("Enlace", cellRenderer=_LINK_RENDERER, filter=False, floatingFilter=False)
    if "Título" in df.columns:
        gb.configure_column("Título", width=320)

    _grid_counter[0] += 1
    AgGrid(
        df,
        gridOptions=gb.build(),
        height=height,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        key=f"grid_{_grid_counter[0]}",
    )


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
    """Selecciona columnas, formatea la fecha sin hora, y renombra todo
    a los encabezados en español pedidos."""
    d = df[columnas].copy()
    if "fecha_presentacion" in d.columns:
        d["fecha_presentacion"] = d["fecha_presentacion"].dt.strftime("%d/%m/%Y")
    return d.rename(columns=RENOMBRAR_COLUMNAS)


def bar_con_etiquetas(df: pd.DataFrame, x: str, y: str, color: str = None,
                       color_discrete_map: dict = None, **kwargs):
    """px.bar con el número y el porcentaje del total escritos encima de cada barra."""
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


def agregar_logos_sobre_barras(fig, categorias_en_orden: list, y_frac: float = 1.14,
                                sizex: float = 0.6, sizey: float = 0.16):
    """Superpone el logo de cada partido encima de su barra correspondiente.
    Las posiciones son aproximadas (Plotly no da un ancla pixel-perfecta
    para ejes categóricos) — si algún logo queda desalineado, ajusta
    sizex/sizey/y_frac a ojo, es la única parte de este archivo que
    depende de "verlo" para afinar."""
    for cat in categorias_en_orden:
        url = LOGO_PARTIDO.get(cat)
        if not url:
            continue
        fig.add_layout_image(dict(
            source=url, xref="x", yref="paper",
            x=cat, y=y_frac, sizex=sizex, sizey=sizey,
            xanchor="center", yanchor="bottom",
        ))
    fig.update_layout(margin=dict(t=110))
    return fig


def fila_logos_con_hover(conteo: dict, total: int):
    """Fila de logos con tooltip nativo del navegador (al pasar el cursor)
    mostrando el número de proyectos y el porcentaje de cada partido."""
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
df_proyectos["bancada"] = df_proyectos["bancada"].fillna("").replace("", OTROS_LABEL)
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
    fig_banc = agregar_logos_sobre_barras(fig_banc, banc["bancada"].tolist())
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
    st.caption("Filtra cualquier columna con el ícono de filtro en su encabezado.")
    busqueda = st.text_input("Buscar por palabra clave en el título")
    tabla = df_proyectos
    if busqueda:
        tabla = tabla[tabla["titulo"].str.contains(busqueda, case=False, na=False)]
    mostrar_tabla(preparar_para_mostrar(
        tabla, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "proponente", "bancada", "tema_aprox", "link"]
    ))

# ----------------------------------------------------------------------
# TAB: DASHBOARD POR PARTIDO
# ----------------------------------------------------------------------
with tab_partidos:
    partidos_disponibles = sorted(df_proyectos["bancada"].dropna().unique().tolist())
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
        "no es oficial del Congreso. Puede haber errores o temas mal asignados."
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
    fig_tema = agregar_logos_sobre_barras(fig_tema, banc_tema["bancada"].tolist())
    st.plotly_chart(fig_tema, use_container_width=True)

    st.subheader(f"Proyectos de '{tema_sel}'")
    mostrar_tabla(preparar_para_mostrar(
        proy_tema, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "bancada", "link"]
    ))

# ----------------------------------------------------------------------
# TAB: DIPUTADOS
# ----------------------------------------------------------------------
with tab_diputados:
    st.subheader("Todos los diputados y sus proyectos")
    st.caption(
        "Los 130 diputados de la nómina oficial, con la cantidad de proyectos en los que "
        "participó cada uno (0 si todavía no presenta ninguno). Usa el filtro de cada "
        "columna (ícono en el encabezado) para acotar por región, partido o cantidad de "
        "proyectos — igual que un filtro de Excel."
    )
    tabla_diputados = contar_proyectos_por_diputado(directorio, df_autorias)
    tabla_diputados = tabla_diputados.sort_values(["Partido", "Proyectos"], ascending=[True, False])
    mostrar_tabla(tabla_diputados, height=500)

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
        mostrar_tabla(preparar_para_mostrar(
            detalle, ["proyecto_ley", "fecha_presentacion", "titulo", "estado", "tema_aprox", "link"]
        ))

    st.subheader("Directorio de diputados electos")
    st.caption(
        f"Nómina oficial de los {len(directorio)} de 130 diputados proclamados para el "
        "periodo 2026-2031, con su región y partido — provista por el usuario, no viene "
        "del Congreso junto a los proyectos de ley."
    )
    if directorio:
        dir_df = pd.DataFrame([{"Región": d["region"], "Partido": d["partido"], "Nombre": d["nombre_fuente"]}
                                for d in directorio])
        region_filtro = st.selectbox("Filtrar por región", ["Todas"] + sorted(dir_df["Región"].unique().tolist()))
        if region_filtro != "Todas":
            dir_df = dir_df[dir_df["Región"] == region_filtro]
        mostrar_tabla(dir_df.sort_values(["Región", "Partido", "Nombre"]), height=500)

st.caption(
    "Notas: (1) la región y el directorio completo vienen de la nómina oficial de los "
    "130 diputados proclamados (no del Congreso, que no la expone junto a los proyectos "
    "de ley); el cruce de nombres entre ambas fuentes es automático por coincidencia de "
    "palabras, no exacto. (2) La clasificación temática es una aproximación por palabras "
    "clave, no oficial. (3) El enlace a cada proyecto sigue el patrón usado en oficios "
    "reales del Congreso, pero no se probó en vivo contra este periodo — si algún enlace "
    "no abre, avisa para ajustar el patrón."
)
