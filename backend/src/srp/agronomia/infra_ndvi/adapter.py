"""CopernicusNdviAdapter — implementación de ProveedorNdvi vía CDSE (§6, §18.4).

Flujo por potrero:
1. Buscar escenas S2MSI2A en la ventana [fecha - 10 días, fecha] con nubosidad
   aceptable (reintentos con backoff exponencial 2/4/8 s, §11).
2. Si hay escena: descargar bandas RED/NIR (callable inyectado — ver TODO
   abajo), calcular NDVI local y devolver LecturaNdvi con
   calidad = 1 - cloudCover/100.
3. Si NO hay escena utilizable (o el catálogo falla tras los reintentos):
   fallback a la última lectura conocida del potrero marcada stale=True (§11).
4. Si tampoco hay lectura previa: NdviNoDisponibleError con mensaje claro.

TODO(credenciales): la descarga real de bandas se hace desde el bucket S3
`eodata` del CDSE (endpoint https://eodata.dataspace.copernicus.eu, credenciales
S3 emitidas en https://eodata-s3keysmanager.dataspace.copernicus.eu — distintas
del client OAuth2). Hasta tener esas credenciales aprovisionadas, la descarga
se inyecta como callable `descargar_bandas(producto_id) -> (red_path, nir_path)`
lo que además permite fakearla en tests sin tocar la red.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date, datetime, timedelta

import asyncpg
import httpx

from srp.agronomia.infra_ndvi.cdse_catalogo import CatalogoCdse
from srp.agronomia.infra_ndvi.ndvi_local import calcular_ndvi_local
from srp.agronomia.infra_ndvi.repositorio_ndvi import ultima_lectura
from srp.shared.ports import ProveedorNdvi
from srp.shared.types import LecturaNdvi

logger = logging.getLogger(__name__)

# Ventana de búsqueda hacia atrás: Sentinel-2 revisita cada ~5 días; 10 días
# dan margen ante nubosidad persistente (§6).
VENTANA_BUSQUEDA_DIAS = 10

# Reintentos con backoff exponencial antes de degradar al fallback (§11).
_BACKOFF_S: tuple[float, ...] = (2.0, 4.0, 8.0)

DescargarBandas = Callable[[str], Awaitable[tuple[str, str]]]


class NdviNoDisponibleError(RuntimeError):
    """Sin escena utilizable en la ventana Y sin lectura previa para fallback."""


def bbox_de_poligono(poligono_geojson: dict) -> tuple[float, float, float, float]:
    """(min_lng, min_lat, max_lng, max_lat) del anillo exterior del polígono."""
    if poligono_geojson.get("type") != "Polygon":
        raise ValueError(
            f"Se esperaba un GeoJSON Polygon, llegó {poligono_geojson.get('type')!r}"
        )
    anillo = poligono_geojson["coordinates"][0]
    lngs = [punto[0] for punto in anillo]
    lats = [punto[1] for punto in anillo]
    return (min(lngs), min(lats), max(lngs), max(lats))


def _fecha_de_escena(escena: dict, por_defecto: date) -> date:
    crudo = escena.get("fecha")
    if not crudo:
        return por_defecto
    try:
        return datetime.fromisoformat(str(crudo).replace("Z", "+00:00")).date()
    except ValueError:
        return por_defecto


class CopernicusNdviAdapter(ProveedorNdvi):
    """Adaptador NDVI contra el Copernicus Data Space Ecosystem."""

    def __init__(
        self,
        catalogo: CatalogoCdse,
        descargar_bandas: DescargarBandas,
        pool: asyncpg.Pool,
        max_nubes: float = 30,
        backoff_s: tuple[float, ...] = _BACKOFF_S,
    ) -> None:
        self._catalogo = catalogo
        self._descargar_bandas = descargar_bandas
        self._pool = pool
        self._max_nubes = max_nubes
        self._backoff_s = backoff_s

    async def obtener_ndvi(
        self, poligono_geojson: dict, fecha: date
    ) -> LecturaNdvi:
        bbox = bbox_de_poligono(poligono_geojson)
        desde = fecha - timedelta(days=VENTANA_BUSQUEDA_DIAS)

        escenas = await self._buscar_con_reintentos(bbox, desde, fecha)
        if escenas:
            escena = escenas[0]  # la de menor nubosidad (ya ordenadas)
            ruta_red, ruta_nir = await self._descargar_bandas(escena["id"])
            ndvi = calcular_ndvi_local(ruta_red, ruta_nir, bbox)
            cloud_cover = escena.get("cloudCover") or 0.0
            return LecturaNdvi(
                fecha=_fecha_de_escena(escena, fecha),
                ndvi_promedio=ndvi,
                calidad=1.0 - cloud_cover / 100.0,
                fuente="sentinel-2",
                stale=False,
            )

        return await self._fallback_ultima_conocida(poligono_geojson, fecha)

    async def _buscar_con_reintentos(
        self,
        bbox: tuple[float, float, float, float],
        desde: date,
        hasta: date,
    ) -> list[dict]:
        """Búsqueda con backoff exponencial; [] si el catálogo no responde (§11)."""
        ultimo_error: Exception | None = None
        for intento, espera_s in enumerate((0.0, *self._backoff_s)):
            if espera_s:
                await asyncio.sleep(espera_s)
            try:
                return await self._catalogo.buscar_escenas(
                    bbox, desde, hasta, max_nubes=self._max_nubes
                )
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                ultimo_error = exc
                logger.warning(
                    "Catálogo CDSE falló (intento %d): %s", intento + 1, exc
                )
        logger.error(
            "Catálogo CDSE agotó reintentos; se degrada al fallback stale: %s",
            ultimo_error,
        )
        return []

    async def _fallback_ultima_conocida(
        self, poligono_geojson: dict, fecha: date
    ) -> LecturaNdvi:
        """Última lectura del potrero marcada stale=True (§11)."""
        potrero_id = await self._pool.fetchval(
            """
            SELECT id FROM potreros
            WHERE ST_Equals(geom::geometry, ST_GeomFromGeoJSON($1))
            LIMIT 1
            """,
            json.dumps(poligono_geojson),
        )
        lectura_previa = (
            await ultima_lectura(self._pool, potrero_id)
            if potrero_id is not None
            else None
        )
        if lectura_previa is not None:
            logger.info(
                "Sin escena CDSE utilizable hasta %s para potrero %s: "
                "se reusa la lectura del %s como stale",
                fecha,
                potrero_id,
                lectura_previa.fecha,
            )
            return replace(lectura_previa, stale=True)

        raise NdviNoDisponibleError(
            f"Sin escena Sentinel-2 utilizable (nubes < {self._max_nubes}%) en la "
            f"ventana [{fecha - timedelta(days=VENTANA_BUSQUEDA_DIAS)}, {fecha}] "
            "y sin lectura NDVI previa del potrero para usar como fallback"
        )
