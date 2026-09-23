"""
Scraper de proyectos de ley - Congreso del Perú (Cámara de Diputados / Senado)

Consume la API JSON real que usa el buscador público de wb2server.congreso.gob.pe
(confirmada por inspección de red, no es HTML scraping ni depende del Excel manual).

Endpoint: POST https://api.congreso.gob.pe/spley-portal-service/proyecto-ley/lista-con-filtro

Nota importante: este endpoint trae título, estado, fecha, proponente y el campo
'autores' (todos los nombres juntos en un string separado por '; ', sin distinguir
autor principal / coautor / adherente). La separación por rol y la bancada (grupo
parlamentario) viven en el endpoint de detalle por proyecto, que usa un ID
codificado que todavía no hemos descifrado — ver README.md, sección "Limitaciones".
"""

import json
import time
from pathlib import Path

import requests

BASE_URL = "https://api.congreso.gob.pe/spley-portal-service/proyecto-ley/lista-con-filtro"
PAGE_SIZE = 100
TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = 0.5  # no golpear el servidor del Congreso sin necesidad

HEADERS = {"Content-Type": "application/json"}


def fetch_page(per_par_id: int, cod_tipo_parl: str, row_start: int, page_size: int = PAGE_SIZE) -> dict:
    """Pide una página de resultados a la API del Congreso."""
    payload = {
        "perParId": per_par_id,
        "codTipoParl": cod_tipo_parl,
        "perLegId": None,
        "comisionId": None,
        "estadoId": None,
        "congresistaId": None,
        "grupoParlamentarioId": None,
        "proponenteId": None,
        "legislaturaId": None,
        "fecPresentacionDesde": None,
        "fecPresentacionHasta": None,
        "pleyNum": None,
        "palabras": None,
        "tipoFirmanteId": None,
        "pageSize": page_size,
        "rowStart": row_start,
    }
    resp = requests.post(BASE_URL, json=payload, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_all(per_par_id: int, cod_tipo_parl: str) -> list[dict]:
    """Pagina hasta traer todos los proyectos de un periodo/cámara."""
    all_items: list[dict] = []
    row_start = 0

    while True:
        data = fetch_page(per_par_id, cod_tipo_parl, row_start)
        proyectos = data.get("data", {}).get("proyectos", [])
        if not proyectos:
            break

        all_items.extend(proyectos)
        total = proyectos[0].get("rowsTotal", len(all_items))
        row_start += PAGE_SIZE

        print(f"  {cod_tipo_parl} {per_par_id}: {min(row_start, total)}/{total}")

        if row_start >= total:
            break
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    return all_items


def normalize(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Separa el campo 'autores' (string tipo "Nombre1; Nombre2; Nombre3")
    en una tabla puente proyecto<->persona. Esto NO distingue autor principal
    de coautor/adherente porque la API de lista no expone esa distinción
    (ver README.md).
    """
    proyectos = []
    autorias = []

    for it in items:
        proyecto_ley = it.get("proyectoLey")
        proyectos.append({
            "proyecto_ley": proyecto_ley,
            "ply_num": it.get("pleyNum"),
            "periodo": it.get("perParId"),
            "camara": it.get("codTipoParl"),
            "titulo": it.get("titulo"),
            "estado": it.get("desEstado"),
            "fecha_presentacion": it.get("fecPresentacion"),
            "proponente": it.get("desProponente"),
        })

        autores_raw = it.get("autores") or ""
        for nombre in [a.strip() for a in autores_raw.split(";") if a.strip()]:
            autorias.append({"proyecto_ley": proyecto_ley, "persona": nombre})

    return proyectos, autorias


def main():
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)

    todos_items = []
    # "D" = Diputados. Si confirmas el código para Senado (probablemente "S"),
    # agrégalo aquí para traer ambas cámaras.
    for cod_tipo_parl in ["D"]:
        print(f"Descargando proyectos de la cámara: {cod_tipo_parl}")
        todos_items.extend(fetch_all(per_par_id=2026, cod_tipo_parl=cod_tipo_parl))

    proyectos, autorias = normalize(todos_items)

    (out_dir / "proyectos.json").write_text(
        json.dumps(proyectos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "autorias.json").write_text(
        json.dumps(autorias, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nListo: {len(proyectos)} proyectos, {len(autorias)} relaciones autor-proyecto.")


if __name__ == "__main__":
    main()
