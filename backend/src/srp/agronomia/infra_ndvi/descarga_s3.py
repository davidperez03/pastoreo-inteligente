"""Descarga de bandas Sentinel-2 desde el bucket S3 `eodata` del CDSE.

Implementa el callable `DescargarBandas` que espera `CopernicusNdviAdapter`:
`descargar(producto_id) -> (ruta_banda_red, ruta_banda_nir)`.

Flujo:
1. Resuelve el `S3Path` del producto vía OData (`Products(<id>)`, público).
2. Lista el `.SAFE` bajo ese prefijo y localiza las bandas B04 (rojo) y B08
   (NIR) en resolución 10 m dentro de `GRANULE/*/IMG_DATA/R10m/`.
3. Descarga ambas a un caché local (idempotente: si ya existen, no re-descarga
   — una escena pesa cientos de MB y varios potreros comparten tile).

Credenciales: par de llaves S3 del CDSE (se generan en el portal, distintas
del client OAuth) vía `SRP_CDSE_S3_ACCESS_KEY` / `SRP_CDSE_S3_SECRET_KEY`.
boto3 es síncrono: el trabajo bloqueante corre en un thread aparte para no
frenar el event loop del worker.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

ENDPOINT_S3 = "https://eodata.dataspace.copernicus.eu"
BUCKET = "eodata"
URL_ODATA_PRODUCTO = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({id})"
CACHE_DIR_DEFAULT = Path(
    os.environ.get("SRP_NDVI_CACHE_DIR", "/tmp/srp-ndvi-cache")  # noqa: S108
)

_PATRON_B04 = re.compile(r"GRANULE/.+/IMG_DATA/R10m/.+_B04_10m\.jp2$")
_PATRON_B08 = re.compile(r"GRANULE/.+/IMG_DATA/R10m/.+_B08_10m\.jp2$")


class DescargaBandasError(RuntimeError):
    """No fue posible obtener las bandas del producto (S3Path, listado o descarga)."""


class DescargadorBandasS3:
    """Descargador de bandas B04/B08 con caché local.

    `s3` acepta cualquier objeto con la interfaz de cliente boto3
    (`get_paginator("list_objects_v2")`, `download_file`) — en tests se
    inyecta un stub; en producción se construye con `crear_desde_env()`.
    """

    def __init__(
        self,
        s3,
        http: httpx.AsyncClient | None = None,
        cache_dir: Path = CACHE_DIR_DEFAULT,
        timeout_s: float = 60.0,
    ) -> None:
        self._s3 = s3
        self._http = http
        self._cache_dir = cache_dir
        self._timeout_s = timeout_s

    async def __call__(self, producto_id: str) -> tuple[str, str]:
        return await self.descargar(producto_id)

    async def descargar(self, producto_id: str) -> tuple[str, str]:
        ruta_red = self._cache_dir / f"{producto_id}_B04_10m.jp2"
        ruta_nir = self._cache_dir / f"{producto_id}_B08_10m.jp2"
        if ruta_red.exists() and ruta_nir.exists():
            logger.info("Bandas de %s ya en caché", producto_id)
            return str(ruta_red), str(ruta_nir)

        s3_path = await self._resolver_s3_path(producto_id)
        prefijo = s3_path.removeprefix(f"/{BUCKET}/").removeprefix(BUCKET + "/")

        def _trabajo_bloqueante() -> None:
            clave_red, clave_nir = self._localizar_bandas(prefijo)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._descargar_a(clave_red, ruta_red)
            self._descargar_a(clave_nir, ruta_nir)

        await asyncio.to_thread(_trabajo_bloqueante)
        logger.info("Bandas de %s descargadas a %s", producto_id, self._cache_dir)
        return str(ruta_red), str(ruta_nir)

    # --- Pasos ------------------------------------------------------------

    async def _resolver_s3_path(self, producto_id: str) -> str:
        url = URL_ODATA_PRODUCTO.format(id=producto_id)
        try:
            if self._http is not None:
                resp = await self._http.get(url, timeout=self._timeout_s)
            else:
                async with httpx.AsyncClient() as http:
                    resp = await http.get(url, timeout=self._timeout_s)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DescargaBandasError(
                f"No se pudo resolver S3Path del producto {producto_id}: {exc}"
            ) from exc
        s3_path = resp.json().get("S3Path")
        if not s3_path:
            raise DescargaBandasError(
                f"Producto {producto_id} sin S3Path en la respuesta OData"
            )
        return s3_path

    def _localizar_bandas(self, prefijo: str) -> tuple[str, str]:
        clave_red = clave_nir = None
        paginador = self._s3.get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=BUCKET, Prefix=prefijo):
            for objeto in pagina.get("Contents", []):
                clave = objeto["Key"]
                if _PATRON_B04.search(clave):
                    clave_red = clave
                elif _PATRON_B08.search(clave):
                    clave_nir = clave
            if clave_red and clave_nir:
                break
        if not (clave_red and clave_nir):
            raise DescargaBandasError(
                f"No se hallaron B04/B08 R10m bajo {prefijo!r} "
                f"(¿producto L1C en vez de L2A?)"
            )
        return clave_red, clave_nir

    def _descargar_a(self, clave: str, destino: Path) -> None:
        # Descarga a archivo temporal + rename: un proceso interrumpido no
        # deja en caché un jp2 truncado que rasterio leería como corrupto.
        temporal = destino.with_suffix(destino.suffix + ".part")
        try:
            self._s3.download_file(BUCKET, clave, str(temporal))
        except Exception as exc:
            temporal.unlink(missing_ok=True)
            raise DescargaBandasError(f"Fallo descargando {clave}: {exc}") from exc
        temporal.rename(destino)


def crear_desde_env(
    cache_dir: Path = CACHE_DIR_DEFAULT,
) -> DescargadorBandasS3 | None:
    """Construye el descargador con las llaves S3 del entorno, o None si faltan."""
    access_key = os.environ.get("SRP_CDSE_S3_ACCESS_KEY")
    secret_key = os.environ.get("SRP_CDSE_S3_SECRET_KEY")
    if not (access_key and secret_key):
        return None
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT_S3,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="default",
    )
    return DescargadorBandasS3(s3, cache_dir=cache_dir)
