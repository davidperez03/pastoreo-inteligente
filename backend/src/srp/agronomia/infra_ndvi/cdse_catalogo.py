"""Búsqueda de escenas Sentinel-2 en el catálogo OData del CDSE (§6).

Consulta https://catalogue.dataspace.copernicus.eu/odata/v1/Products con un
filtro OData: colección SENTINEL-2, producto de nivel 2A (S2MSI2A, reflectancia
de superficie con corrección atmosférica), intersección espacial con el bbox
del potrero, ventana temporal y nubosidad máxima. Devuelve las escenas
ordenadas por menor nubosidad.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from srp.agronomia.infra_ndvi.cdse_auth import CdseAuth

CATALOGO_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"


def bbox_a_wkt(bbox_wgs84: tuple[float, float, float, float]) -> str:
    """Convierte (min_lng, min_lat, max_lng, max_lat) a un POLYGON WKT cerrado."""
    min_lng, min_lat, max_lng, max_lat = bbox_wgs84
    return (
        "POLYGON(("
        f"{min_lng} {min_lat},{max_lng} {min_lat},"
        f"{max_lng} {max_lat},{min_lng} {max_lat},"
        f"{min_lng} {min_lat}))"
    )


def construir_filtro_odata(
    bbox_wgs84: tuple[float, float, float, float],
    desde: date,
    hasta: date,
    max_nubes: float,
) -> str:
    """Filtro OData del CDSE (reemplaza la vieja query del Open Access Hub)."""
    wkt = bbox_a_wkt(bbox_wgs84)
    return (
        "Collection/Name eq 'SENTINEL-2' and "
        "Attributes/OData.CSC.StringAttribute/any("
        "att:att/Name eq 'productType' and "
        "att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}') and "
        f"ContentDate/Start gt {desde.isoformat()}T00:00:00.000Z and "
        f"ContentDate/Start lt {hasta.isoformat()}T23:59:59.999Z and "
        "Attributes/OData.CSC.DoubleAttribute/any("
        "att:att/Name eq 'cloudCover' and "
        f"att/OData.CSC.DoubleAttribute/Value lt {max_nubes})"
    )


def _extraer_cloud_cover(producto: dict[str, Any]) -> float | None:
    for atributo in producto.get("Attributes", []):
        if atributo.get("Name") == "cloudCover":
            try:
                return float(atributo["Value"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


class CatalogoCdse:
    """Cliente del catálogo OData del CDSE con token OAuth2 inyectado."""

    def __init__(
        self,
        auth: CdseAuth,
        http: httpx.AsyncClient | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self._auth = auth
        self._http = http
        self._timeout_s = timeout_s

    async def buscar_escenas(
        self,
        bbox_wgs84: tuple[float, float, float, float],
        desde: date,
        hasta: date,
        max_nubes: float = 30,
    ) -> list[dict[str, Any]]:
        """Escenas S2MSI2A que intersectan el bbox, ordenadas por menor nubosidad.

        Cada escena es un dict con: id, nombre, cloudCover, fecha (ISO-8601 del
        inicio de adquisición).
        """
        token = await self._auth.obtener_token()
        params = {
            "$filter": construir_filtro_odata(bbox_wgs84, desde, hasta, max_nubes),
            "$expand": "Attributes",
            "$orderby": "ContentDate/Start desc",
            "$top": "20",
        }
        headers = {"Authorization": f"Bearer {token}"}
        if self._http is not None:
            respuesta = await self._http.get(
                CATALOGO_URL, params=params, headers=headers
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout_s) as cliente:
                respuesta = await cliente.get(
                    CATALOGO_URL, params=params, headers=headers
                )
        respuesta.raise_for_status()
        productos = respuesta.json().get("value", [])

        escenas: list[dict[str, Any]] = []
        for producto in productos:
            cloud_cover = _extraer_cloud_cover(producto)
            escenas.append(
                {
                    "id": producto["Id"],
                    "nombre": producto.get("Name", ""),
                    "cloudCover": cloud_cover,
                    "fecha": (producto.get("ContentDate") or {}).get("Start"),
                }
            )
        # El $orderby de OData sobre atributos expandidos no es fiable en el
        # CDSE: ordenamos aquí por menor nubosidad (None al final).
        escenas.sort(
            key=lambda e: (e["cloudCover"] is None, e["cloudCover"] or 0.0)
        )
        return escenas
