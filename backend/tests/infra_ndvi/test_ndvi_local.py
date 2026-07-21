"""Tests del cálculo local de NDVI con GeoTIFFs sintéticos (§6, §14).

Las bandas se generan en el propio test con rasterio: valores conocidos =>
NDVI esperado exacto, sin depender de escenas reales.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from srp.agronomia.infra_ndvi.ndvi_local import (
    SinPixelesValidosError,
    bbox_a_window,
    calcular_ndvi_local,
)

# Ráster 10x10 de 0.001° por píxel: lng [-72.40, -72.39], lat [5.33, 5.34].
TRANSFORM = from_origin(-72.40, 5.34, 0.001, 0.001)
BBOX_COMPLETO = (-72.40, 5.33, -72.39, 5.34)


def _escribir_banda(ruta: Path, datos: np.ndarray) -> str:
    perfil = {
        "driver": "GTiff",
        "width": datos.shape[1],
        "height": datos.shape[0],
        "count": 1,
        "dtype": datos.dtype.name,
        "crs": "EPSG:4326",
        "transform": TRANSFORM,
    }
    with rasterio.open(ruta, "w", **perfil) as destino:
        destino.write(datos, 1)
    return str(ruta)


def test_ndvi_uniforme_valor_exacto(tmp_path):
    # red=1000, nir=3000 en todos los píxeles => NDVI = 2000/4000 = 0.5 exacto
    red = _escribir_banda(tmp_path / "B04.tif", np.full((10, 10), 1000, np.uint16))
    nir = _escribir_banda(tmp_path / "B08.tif", np.full((10, 10), 3000, np.uint16))

    assert calcular_ndvi_local(red, nir, BBOX_COMPLETO) == 0.5


def test_guard_division_por_cero(tmp_path):
    # Un píxel con red=nir=0: el guard lo fija en NDVI=0 en vez de NaN/inf.
    datos_red = np.full((10, 10), 1000, np.uint16)
    datos_nir = np.full((10, 10), 3000, np.uint16)
    datos_red[0, 0] = 0
    datos_nir[0, 0] = 0
    red = _escribir_banda(tmp_path / "B04.tif", datos_red)
    nir = _escribir_banda(tmp_path / "B08.tif", datos_nir)

    resultado = calcular_ndvi_local(red, nir, BBOX_COMPLETO)

    # 99 píxeles con 0.5 y 1 píxel con 0.0
    assert resultado == pytest.approx((99 * 0.5 + 0.0) / 100)
    assert np.isfinite(resultado)


def test_window_recorta_al_bbox(tmp_path):
    # Mitad izquierda NDVI=+0.5, mitad derecha NDVI=-0.5; el bbox de la mitad
    # izquierda debe ignorar por completo la derecha.
    datos_red = np.empty((10, 10), np.uint16)
    datos_nir = np.empty((10, 10), np.uint16)
    datos_red[:, :5], datos_nir[:, :5] = 1000, 3000
    datos_red[:, 5:], datos_nir[:, 5:] = 3000, 1000
    red = _escribir_banda(tmp_path / "B04.tif", datos_red)
    nir = _escribir_banda(tmp_path / "B08.tif", datos_nir)

    bbox_izquierda = (-72.40, 5.33, -72.395, 5.34)
    assert calcular_ndvi_local(red, nir, bbox_izquierda) == 0.5

    # El ráster completo mezcla ambas mitades => promedio 0.
    assert calcular_ndvi_local(red, nir, BBOX_COMPLETO) == 0.0


def test_bbox_a_window_usa_from_bounds(tmp_path):
    ruta = _escribir_banda(
        tmp_path / "banda.tif", np.zeros((10, 10), np.uint16)
    )
    with rasterio.open(ruta) as dataset:
        ventana = bbox_a_window((-72.40, 5.33, -72.395, 5.34), dataset)
        assert (ventana.height, ventana.width) == (10, 5)
        assert (ventana.row_off, ventana.col_off) == (0, 0)

        # bbox mayor que el ráster: la ventana se recorta a la extensión real
        gigante = bbox_a_window((-73.0, 5.0, -72.0, 6.0), dataset)
        assert (gigante.height, gigante.width) == (10, 10)


def test_todos_los_pixeles_invalidos_lanza_error(tmp_path):
    # NDVI=-1 exacto en todos los píxeles (nir=0, red>0): nada supera el
    # umbral de validez y debe fallar con un error claro.
    red = _escribir_banda(tmp_path / "B04.tif", np.full((10, 10), 500, np.uint16))
    nir = _escribir_banda(tmp_path / "B08.tif", np.zeros((10, 10), np.uint16))

    with pytest.raises(SinPixelesValidosError):
        calcular_ndvi_local(red, nir, BBOX_COMPLETO)
