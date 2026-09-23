"""
Scraper de proyectos de ley - Congreso del Perú (Cámara de Diputados / Senado)

Consume la API JSON real que usa el buscador público de wb2server.congreso.gob.pe
(confirmada por inspección de red, no es HTML scraping ni depende del Excel manual).

Dos endpoints:
1. Lista:   POST /spley-portal-service/proyecto-ley/lista-con-filtro
            Trae título, estado, fecha, proponente y todos los proyectos paginados.
2. Detalle: GET  /spley-portal-service/expediente/{token1}/{token2}?codTipoParl=D
            Trae el desglose por rol (autor principal / coautor / adherente) y la
            bancada (grupo parlamentario). token1 y token2 son el periodo y el
            número de proyecto (con 5 dígitos), cifrados con AES-128-ECB/PKCS7
            usando una clave fija embebida en el bundle JS del sitio, y luego
            codificados en base64 URL-safe. La función encrypt_id() de abajo
            reproduce exactamente esa función (verificado contra valores reales
            capturados del sitio).
"""

import json
import time
from base64 import b64encode
from pathlib import Path

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

BASE_URL = "https://api.congreso.gob.pe/spley-portal-service/proyecto-ley/lista-con-filtro"
DETAIL_URL = "https://api.congreso.gob.pe/spley-portal-service/expediente/{t1}/{t2}"
ENCRYPTION_KEY = "ProdALg5ZrAsxBMD"  # clave fija encontrada en el bundle JS del sitio
PAGE_SIZE = 100
TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = 0.5  # no golpear el servidor del Congreso sin necesidad

# tipoFirmanteId -> rol, según lo observado en la API (verificado contra la UI)
TIPO_FIRMANTE = {1: "autor_principal", 2: "coautor", 3: "adherente"}


def encrypt_id(value: str, key: str = ENCRYPTION_KEY) -> str:
    """
    Reproduce la función de cifrado del sitio (AES-128-ECB + PKCS7 + base64 URL-safe)
    para generar los dos tokens que pide el endpoint de detalle por proyecto.
    """
    cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
    padded = pad(value.encode("utf-8"), AES.block_size)
    ciphertext = cipher.encrypt(padded)
    b64 = b64encode(ciphertext).decode("utf-8")
    return b64.replace("+", "-").replace("/", "_").replace("=", "")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Origin": "https://wb2server.congreso.gob.pe",
    "Referer": "https://wb2server.congreso.gob.pe/",
}


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


def fetch_detail(per_par_id: int, ply_num: int, cod_tipo_parl: str) -> dict | None:
    """Trae el detalle de un proyecto (bancada + firmantes con rol) usando los tokens cifrados."""
    t1 = encrypt_id(str(per_par_id))
    t2 = encrypt_id(str(ply_num).zfill(5))
    url = DETAIL_URL.format(t1=t1, t2=t2)
    resp = requests.get(url, headers=HEADERS, params={"codTipoParl": cod_tipo_parl}, timeout=TIMEOUT)
    if resp.status_code != 200:
        return None
    return resp.json().get("data")


def normalize(items: list[dict], fetch_details: bool = True) -> tuple[list[dict], list[dict]]:
    """
    Arma la tabla de proyectos (con bancada, si se pudo obtener) y la tabla puente
    proyecto<->persona, con el rol separado (autor_principal / coautor / adherente)
    cuando fetch_details=True. Si el detalle de un proyecto puntual falla, cae de
    vuelta al campo 'autores' de la lista (todos los nombres juntos, sin rol).
    """
    proyectos = []
    autorias = []

    for i, it in enumerate(items):
        proyecto_ley = it.get("proyectoLey")
        ply_num = it.get("pleyNum")
        per_par_id = it.get("perParId")
        cod_tipo_parl = it.get("codTipoParl")

        bancada = None
        detail = None
        if fetch_details and ply_num and per_par_id:
            try:
                detail = fetch_detail(per_par_id, ply_num, cod_tipo_parl)
            except requests.RequestException:
                detail = None
            time.sleep(SLEEP_BETWEEN_REQUESTS)

        if detail:
            bancada = detail.get("general", {}).get("desGpar")
            for f in detail.get("firmantes", []):
                autorias.append({
                    "proyecto_ley": proyecto_ley,
                    "persona": f.get("nombre"),
                    "dni": f.get("dni"),
                    "congresista_id": f.get("congresistaId"),
                    "sexo": f.get("sexo"),
                    "rol": TIPO_FIRMANTE.get(f.get("tipoFirmanteId"), f"tipo_{f.get('tipoFirmanteId')}"),
                })
        else:
            # Sin detalle disponible: usamos el campo combinado de la lista, sin rol.
            autores_raw = it.get("autores") or ""
            for nombre in [a.strip() for a in autores_raw.split(";") if a.strip()]:
                autorias.append({
                    "proyecto_ley": proyecto_ley,
                    "persona": nombre,
                    "dni": None,
                    "congresista_id": None,
                    "sexo": None,
                    "rol": None,
                })

        proyectos.append({
            "proyecto_ley": proyecto_ley,
            "ply_num": ply_num,
            "periodo": per_par_id,
            "camara": cod_tipo_parl,
            "titulo": it.get("titulo"),
            "estado": it.get("desEstado"),
            "fecha_presentacion": it.get("fecPresentacion"),
            "proponente": it.get("desProponente"),
            "bancada": bancada,
        })

        if fetch_details and (i + 1) % 25 == 0:
            print(f"  detalle: {i + 1}/{len(items)} proyectos procesados")

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
