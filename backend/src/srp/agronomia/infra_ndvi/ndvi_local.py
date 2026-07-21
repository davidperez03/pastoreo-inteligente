"""Cálculo local de NDVI a partir de bandas Sentinel-2 (§6).

NDVI = (NIR - RED) / (NIR + RED), calculado sobre la ventana del ráster que
cubre el bbox del potrero. Guard explícito contra división por cero (píxeles
donde NIR + RED == 0 se tratan como 0) y media solo sobre píxeles válidos
(NDVI > -1, que descarta nodata extremo).
"""

from __future__ import annotations

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

Bbox = tuple[float, float, float, float]


class SinPixelesValidosError(ValueError):
    """La ventana del bbox no contiene ningún píxel válido para el NDVI."""


def bbox_a_window(bbox: Bbox, dataset: rasterio.DatasetReader) -> Window:
    """Ventana de lectura del dataset que cubre el bbox (mismo CRS del ráster).

    bbox = (min_x, min_y, max_x, max_y) en las coordenadas del dataset.
    """
    ventana = from_bounds(*bbox, transform=dataset.transform)
    # from_bounds devuelve offsets/tamaños en float; redondear a la grilla de
    # píxeles evita ventanas de 9.9999... filas por error de punto flotante.
    ventana = ventana.round_offsets(op="floor").round_lengths(op="ceil")
    # Intersecar con la extensión real del ráster evita leer fuera de rango.
    return ventana.intersection(Window(0, 0, dataset.width, dataset.height))


def calcular_ndvi_local(
    banda_red_path: str,
    banda_nir_path: str,
    bbox: Bbox,
) -> float:
    """NDVI promedio del bbox a partir de las bandas RED (B04) y NIR (B08)."""
    with (
        rasterio.open(banda_red_path) as red_src,
        rasterio.open(banda_nir_path) as nir_src,
    ):
        red = red_src.read(1, window=bbox_a_window(bbox, red_src)).astype(float)
        nir = nir_src.read(1, window=bbox_a_window(bbox, nir_src)).astype(float)

    if red.shape != nir.shape:
        raise ValueError(
            f"Las bandas RED {red.shape} y NIR {nir.shape} no coinciden "
            "en tamaño para el bbox dado"
        )

    suma = nir + red
    diferencia = nir - red
    # División protegida: donde suma == 0 el NDVI se fija en 0 sin evaluar
    # la división (np.divide con `where` no toca esos píxeles).
    ndvi = np.divide(
        diferencia,
        suma,
        out=np.zeros_like(suma, dtype=float),
        where=suma != 0,
    )

    validos = ndvi[ndvi > -1]
    if validos.size == 0:
        raise SinPixelesValidosError(
            "Ningún píxel válido (NDVI > -1) dentro del bbox"
        )
    return float(validos.mean())
