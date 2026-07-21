"""Tests del CopernicusNdviAdapter: éxito, fallback stale desde DB real y
reintentos (§6, §11). El catálogo y la descarga de bandas se fakean; la base
de datos es Postgres real (fixtures pool/potrero).
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from srp.agronomia.infra_ndvi.adapter import (
    VENTANA_BUSQUEDA_DIAS,
    CopernicusNdviAdapter,
    NdviNoDisponibleError,
    bbox_de_poligono,
)
from srp.agronomia.infra_ndvi.repositorio_ndvi import guardar_lectura
from srp.shared.types import LecturaNdvi

FECHA_CONSULTA = date(2026, 7, 19)


class CatalogoFake:
    """Registra los argumentos de búsqueda y devuelve escenas predefinidas."""

    def __init__(self, escenas=None, errores_antes_de_exito: int = 0):
        self.escenas = escenas or []
        self.errores_restantes = errores_antes_de_exito
        self.llamadas: list[dict] = []

    async def buscar_escenas(self, bbox_wgs84, desde, hasta, max_nubes=30):
        self.llamadas.append(
            {"bbox": bbox_wgs84, "desde": desde, "hasta": hasta, "max_nubes": max_nubes}
        )
        if self.errores_restantes > 0:
            self.errores_restantes -= 1
            raise httpx.ConnectError("catálogo CDSE caído (simulado)")
        return self.escenas


async def _descarga_prohibida(producto_id: str) -> tuple[str, str]:
    raise AssertionError("No debería descargarse ninguna banda en este test")


def _descarga_sintetica(tmp_path, bbox):
    """Fabrica un `descargar_bandas` que genera GeoTIFFs con NDVI=0.5 en el bbox."""

    async def descargar(producto_id: str) -> tuple[str, str]:
        min_lng, _min_lat, max_lng, max_lat = bbox
        paso = (max_lng - min_lng) / 10
        transform = from_origin(min_lng, max_lat, paso, paso)
        rutas = []
        for nombre, valor in (("B04.tif", 1000), ("B08.tif", 3000)):
            perfil = {
                "driver": "GTiff",
                "width": 10,
                "height": 10,
                "count": 1,
                "dtype": "uint16",
                "crs": "EPSG:4326",
                "transform": transform,
            }
            ruta = tmp_path / f"{producto_id}-{nombre}"
            with rasterio.open(ruta, "w", **perfil) as destino:
                destino.write(np.full((10, 10), valor, np.uint16), 1)
            rutas.append(str(ruta))
        return rutas[0], rutas[1]

    return descargar


async def test_con_escena_calcula_ndvi_y_calidad(
    pool, potrero, poligono_geojson, tmp_path
):
    escena = {
        "id": "prod-001",
        "nombre": "S2B_MSIL2A_20260717T152639_N0511_R025_T18NYM.SAFE",
        "cloudCover": 12.0,
        "fecha": "2026-07-17T15:26:39.331Z",
    }
    catalogo = CatalogoFake(escenas=[escena])
    bbox = bbox_de_poligono(poligono_geojson)
    adapter = CopernicusNdviAdapter(
        catalogo, _descarga_sintetica(tmp_path, bbox), pool
    )

    lectura = await adapter.obtener_ndvi(poligono_geojson, FECHA_CONSULTA)

    assert lectura.ndvi_promedio == 0.5
    assert lectura.calidad == pytest.approx(1 - 12.0 / 100)  # 1 - cloudCover/100
    assert lectura.stale is False
    assert lectura.fuente == "sentinel-2"
    assert lectura.fecha == date(2026, 7, 17)  # fecha de la escena, no de consulta

    # La ventana de búsqueda es [fecha - 10 días, fecha] (§6)
    llamada = catalogo.llamadas[0]
    assert llamada["desde"] == FECHA_CONSULTA - timedelta(days=VENTANA_BUSQUEDA_DIAS)
    assert llamada["hasta"] == FECHA_CONSULTA
    assert llamada["max_nubes"] == 30


async def test_sin_escena_fallback_stale_desde_db(pool, potrero, poligono_geojson):
    lectura_previa = LecturaNdvi(
        fecha=FECHA_CONSULTA - timedelta(days=12),
        ndvi_promedio=0.63,
        calidad=0.9,
    )
    await guardar_lectura(pool, potrero, lectura_previa)
    adapter = CopernicusNdviAdapter(CatalogoFake([]), _descarga_prohibida, pool)

    lectura = await adapter.obtener_ndvi(poligono_geojson, FECHA_CONSULTA)

    assert lectura.stale is True  # §11: último-conocido marcado stale
    assert lectura.ndvi_promedio == pytest.approx(0.63)
    assert lectura.fecha == lectura_previa.fecha
    assert lectura.calidad == pytest.approx(0.9)


async def test_sin_escena_ni_historial_lanza_error_claro(
    pool, potrero, poligono_geojson
):
    adapter = CopernicusNdviAdapter(CatalogoFake([]), _descarga_prohibida, pool)

    with pytest.raises(NdviNoDisponibleError, match="fallback"):
        await adapter.obtener_ndvi(poligono_geojson, FECHA_CONSULTA)


async def test_reintenta_con_backoff_ante_fallos_transitorios(
    pool, potrero, poligono_geojson, tmp_path
):
    # Dos fallos de red y luego éxito: el adaptador debe recuperarse (§11).
    escena = {"id": "prod-002", "nombre": "x", "cloudCover": 5.0, "fecha": None}
    catalogo = CatalogoFake(escenas=[escena], errores_antes_de_exito=2)
    bbox = bbox_de_poligono(poligono_geojson)
    adapter = CopernicusNdviAdapter(
        catalogo,
        _descarga_sintetica(tmp_path, bbox),
        pool,
        backoff_s=(0.0, 0.0, 0.0),  # sin esperas reales en tests
    )

    lectura = await adapter.obtener_ndvi(poligono_geojson, FECHA_CONSULTA)

    assert len(catalogo.llamadas) == 3
    assert lectura.ndvi_promedio == 0.5
    assert lectura.fecha == FECHA_CONSULTA  # escena sin fecha => fecha de consulta


async def test_catalogo_caido_persistente_degrada_a_fallback(
    pool, potrero, poligono_geojson
):
    await guardar_lectura(
        pool,
        potrero,
        LecturaNdvi(fecha=FECHA_CONSULTA - timedelta(days=7), ndvi_promedio=0.41),
    )
    catalogo = CatalogoFake(escenas=[], errores_antes_de_exito=99)
    adapter = CopernicusNdviAdapter(
        catalogo, _descarga_prohibida, pool, backoff_s=(0.0, 0.0, 0.0)
    )

    lectura = await adapter.obtener_ndvi(poligono_geojson, FECHA_CONSULTA)

    assert len(catalogo.llamadas) == 4  # 1 intento + 3 reintentos
    assert lectura.stale is True
    assert lectura.ndvi_promedio == pytest.approx(0.41)


def test_bbox_de_poligono():
    poligono = {
        "type": "Polygon",
        "coordinates": [
            [[-72.40, 5.33], [-72.39, 5.33], [-72.39, 5.34], [-72.40, 5.34], [-72.40, 5.33]]
        ],
    }
    assert bbox_de_poligono(poligono) == (-72.40, 5.33, -72.39, 5.34)

    with pytest.raises(ValueError, match="Polygon"):
        bbox_de_poligono({"type": "Point", "coordinates": [0, 0]})
