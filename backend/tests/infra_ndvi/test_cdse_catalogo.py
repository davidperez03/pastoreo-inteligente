"""Contract test del catálogo OData del CDSE contra una respuesta grabada (§14).

La respuesta imita la forma real de
GET https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$expand=Attributes
para detectar si nuestro parseo diverge del contrato del proveedor.
"""

from __future__ import annotations

import urllib.parse
from datetime import date

import httpx
import respx

from srp.agronomia.infra_ndvi.cdse_auth import CdseAuth
from srp.agronomia.infra_ndvi.cdse_catalogo import (
    CATALOGO_URL,
    CatalogoCdse,
    bbox_a_wkt,
    construir_filtro_odata,
)

BBOX = (-72.40, 5.33, -72.39, 5.34)

# Respuesta grabada realista del catálogo OData (recortada a lo relevante).
RESPUESTA_ODATA = {
    "@odata.context": "$metadata#Products(Attributes())",
    "value": [
        {
            "@odata.mediaContentType": "application/octet-stream",
            "Id": "0e1b3f6a-9d0c-4c3f-8f21-3a5d8e9b7c01",
            "Name": "S2A_MSIL2A_20260712T152641_N0511_R025_T18NYM_20260712T201530.SAFE",
            "ContentType": "application/octet-stream",
            "ContentLength": 803942003,
            "OriginDate": "2026-07-12T20:31:04.000Z",
            "PublicationDate": "2026-07-12T21:05:11.000Z",
            "ModificationDate": "2026-07-12T21:05:11.000Z",
            "Online": True,
            "S3Path": "/eodata/Sentinel-2/MSI/L2A/2026/07/12/"
            "S2A_MSIL2A_20260712T152641_N0511_R025_T18NYM_20260712T201530.SAFE",
            "ContentDate": {
                "Start": "2026-07-12T15:26:41.024Z",
                "End": "2026-07-12T15:26:41.024Z",
            },
            "Attributes": [
                {
                    "@odata.type": "#OData.CSC.StringAttribute",
                    "Name": "productType",
                    "Value": "S2MSI2A",
                    "ValueType": "String",
                },
                {
                    "@odata.type": "#OData.CSC.DoubleAttribute",
                    "Name": "cloudCover",
                    "Value": 22.481533,
                    "ValueType": "Double",
                },
            ],
        },
        {
            "@odata.mediaContentType": "application/octet-stream",
            "Id": "7c2d9a44-1b5e-4f0a-9d63-f08a2b6c4e02",
            "Name": "S2B_MSIL2A_20260717T152639_N0511_R025_T18NYM_20260717T195012.SAFE",
            "ContentType": "application/octet-stream",
            "ContentLength": 791233120,
            "OriginDate": "2026-07-17T19:55:41.000Z",
            "PublicationDate": "2026-07-17T20:40:02.000Z",
            "ModificationDate": "2026-07-17T20:40:02.000Z",
            "Online": True,
            "S3Path": "/eodata/Sentinel-2/MSI/L2A/2026/07/17/"
            "S2B_MSIL2A_20260717T152639_N0511_R025_T18NYM_20260717T195012.SAFE",
            "ContentDate": {
                "Start": "2026-07-17T15:26:39.331Z",
                "End": "2026-07-17T15:26:39.331Z",
            },
            "Attributes": [
                {
                    "@odata.type": "#OData.CSC.StringAttribute",
                    "Name": "productType",
                    "Value": "S2MSI2A",
                    "ValueType": "String",
                },
                {
                    "@odata.type": "#OData.CSC.DoubleAttribute",
                    "Name": "cloudCover",
                    "Value": 7.103921,
                    "ValueType": "Double",
                },
            ],
        },
    ],
}


class AuthFalsa(CdseAuth):
    def __init__(self) -> None:
        super().__init__(client_id="x", client_secret="y")

    async def obtener_token(self) -> str:
        return "tok-fake"


@respx.mock
async def test_construye_filtro_odata_y_ordena_por_menor_nubosidad():
    ruta = respx.get(CATALOGO_URL).mock(
        return_value=httpx.Response(200, json=RESPUESTA_ODATA)
    )
    catalogo = CatalogoCdse(auth=AuthFalsa())

    escenas = await catalogo.buscar_escenas(
        BBOX, desde=date(2026, 7, 10), hasta=date(2026, 7, 20), max_nubes=30
    )

    # ---- Verificación de la request (contrato hacia el CDSE) ----
    request = ruta.calls.last.request
    assert request.headers["Authorization"] == "Bearer tok-fake"
    params = urllib.parse.parse_qs(urllib.parse.urlparse(str(request.url)).query)
    filtro = params["$filter"][0]
    assert "Collection/Name eq 'SENTINEL-2'" in filtro
    assert "att/OData.CSC.StringAttribute/Value eq 'S2MSI2A'" in filtro
    assert (
        "OData.CSC.Intersects(area=geography'SRID=4326;"
        "POLYGON((-72.4 5.33,-72.39 5.33,-72.39 5.34,-72.4 5.34,-72.4 5.33))')"
        in filtro
    )
    assert "ContentDate/Start gt 2026-07-10T00:00:00.000Z" in filtro
    assert "ContentDate/Start lt 2026-07-20T23:59:59.999Z" in filtro
    assert "att/OData.CSC.DoubleAttribute/Value lt 30" in filtro
    assert params["$expand"] == ["Attributes"]

    # ---- Verificación del parseo y del orden (menor nubosidad primero) ----
    assert [e["cloudCover"] for e in escenas] == [7.103921, 22.481533]
    assert escenas[0] == {
        "id": "7c2d9a44-1b5e-4f0a-9d63-f08a2b6c4e02",
        "nombre": "S2B_MSIL2A_20260717T152639_N0511_R025_T18NYM_20260717T195012.SAFE",
        "cloudCover": 7.103921,
        "fecha": "2026-07-17T15:26:39.331Z",
    }


@respx.mock
async def test_catalogo_vacio_devuelve_lista_vacia():
    respx.get(CATALOGO_URL).mock(
        return_value=httpx.Response(
            200, json={"@odata.context": "$metadata#Products", "value": []}
        )
    )
    catalogo = CatalogoCdse(auth=AuthFalsa())
    escenas = await catalogo.buscar_escenas(
        BBOX, desde=date(2026, 7, 10), hasta=date(2026, 7, 20)
    )
    assert escenas == []


def test_bbox_a_wkt_cierra_el_anillo():
    wkt = bbox_a_wkt(BBOX)
    assert wkt.startswith("POLYGON((") and wkt.endswith("))")
    puntos = wkt[len("POLYGON((") : -2].split(",")
    assert len(puntos) == 5
    assert puntos[0] == puntos[-1]  # anillo cerrado


def test_filtro_respeta_max_nubes_personalizado():
    filtro = construir_filtro_odata(
        BBOX, date(2026, 1, 1), date(2026, 1, 10), max_nubes=15
    )
    assert "att/OData.CSC.DoubleAttribute/Value lt 15" in filtro
