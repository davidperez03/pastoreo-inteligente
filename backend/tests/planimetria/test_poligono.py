"""Tests de construcción y validación de polígonos (§3.3)."""

from __future__ import annotations

import pytest
from shapely.geometry import Polygon, shape

from srp.planimetria.poligono import (
    calcular_area_geodesica,
    construir_poligono_validado,
    validar_sin_traslape,
)
from tests.planimetria.conftest import AREA_ESPERADA_HA


class TestConstruirPoligonoValidado:
    def test_cuadrado_casanare_area_correcta(self, cuadrado_casanare):
        resultado = construir_poligono_validado(cuadrado_casanare)

        assert resultado["advertencia"] is None
        assert resultado["geojson"]["type"] == "Polygon"
        # ~19.6 ha con tolerancia del 5%
        assert resultado["area_ha"] == pytest.approx(AREA_ESPERADA_HA, rel=0.05)
        # cierre automático: 4 esquinas + punto de cierre
        assert resultado["n_puntos"] == 5

    def test_cierre_automatico_no_muta_entrada(self, cuadrado_casanare):
        copia = list(cuadrado_casanare)
        construir_poligono_validado(cuadrado_casanare)
        assert cuadrado_casanare == copia

    def test_anillo_ya_cerrado_da_mismo_resultado(self, cuadrado_casanare):
        cerrado = [*cuadrado_casanare, cuadrado_casanare[0]]
        abierto = construir_poligono_validado(cuadrado_casanare)
        resultado = construir_poligono_validado(cerrado)
        assert resultado["area_ha"] == pytest.approx(abierto["area_ha"])
        assert resultado["n_puntos"] == abierto["n_puntos"]

    def test_menos_de_3_puntos_lanza_valueerror(self):
        with pytest.raises(ValueError, match="mínimo 3 puntos"):
            construir_poligono_validado([(5.337, -72.396), (5.341, -72.392)])

    def test_dos_puntos_mas_cierre_lanza_valueerror(self):
        # 3 elementos pero solo 2 puntos distintos (el tercero es el cierre)
        with pytest.raises(ValueError, match="mínimo 3 puntos"):
            construir_poligono_validado(
                [(5.337, -72.396), (5.341, -72.392), (5.337, -72.396)]
            )

    def test_lista_vacia_lanza_valueerror(self):
        with pytest.raises(ValueError):
            construir_poligono_validado([])

    def test_moño_autointersectado_corregido_con_advertencia(self):
        # Orden de vértices que cruza las diagonales: "moño" (bowtie)
        moño = [
            (5.337, -72.396),
            (5.341, -72.392),
            (5.337, -72.392),
            (5.341, -72.396),
        ]
        resultado = construir_poligono_validado(moño)

        assert resultado["advertencia"] is not None
        assert "corregido" in resultado["advertencia"]
        geometria = shape(resultado["geojson"])
        assert geometria.is_valid
        assert not geometria.is_empty
        # el moño corregido son dos triángulos: la mitad del cuadrado
        assert resultado["area_ha"] == pytest.approx(AREA_ESPERADA_HA / 2, rel=0.05)

    def test_lat_lng_invertidas_produce_advertencia_de_plausibilidad(self, cuadrado_casanare):
        invertido = [(lng, lat) for lat, lng in cuadrado_casanare]
        resultado = construir_poligono_validado(invertido)

        assert resultado["advertencia"] is not None
        assert "fuera de rango plausible" in resultado["advertencia"]

    def test_poligono_minusculo_advierte(self):
        # ~1 m de lado: muy por debajo de 0.05 ha
        lado = 0.00001
        puntos = [
            (5.337, -72.396),
            (5.337, -72.396 + lado),
            (5.337 + lado, -72.396 + lado),
            (5.337 + lado, -72.396),
        ]
        resultado = construir_poligono_validado(puntos)
        assert resultado["advertencia"] is not None
        assert "fuera de rango plausible" in resultado["advertencia"]


class TestCalcularAreaGeodesica:
    def test_area_en_m2_del_cuadrado(self, cuadrado_casanare):
        poligono = Polygon([(lng, lat) for lat, lng in cuadrado_casanare])
        area_m2 = calcular_area_geodesica(poligono)
        assert area_m2 == pytest.approx(AREA_ESPERADA_HA * 10_000, rel=0.05)


class TestValidarSinTraslape:
    def _cuadrado(self, lng0: float, lat0: float, lado: float = 0.004) -> Polygon:
        return Polygon(
            [
                (lng0, lat0),
                (lng0 + lado, lat0),
                (lng0 + lado, lat0 + lado),
                (lng0, lat0 + lado),
            ]
        )

    def test_traslape_detectado(self):
        nuevo = self._cuadrado(-72.396, 5.337)
        solapado = self._cuadrado(-72.394, 5.339)  # desplazado media diagonal
        lejano = self._cuadrado(-72.380, 5.350)

        traslapes = validar_sin_traslape(
            nuevo, [("Potrero Solapado", solapado), ("Potrero Lejano", lejano)]
        )
        assert traslapes == ["Potrero Solapado"]

    def test_potreros_contiguos_que_comparten_cerca_no_cuentan(self):
        nuevo = self._cuadrado(-72.396, 5.337)
        vecino = self._cuadrado(-72.392, 5.337)  # comparte el borde este, sin área común
        assert validar_sin_traslape(nuevo, [("Vecino", vecino)]) == []

    def test_sin_existentes_no_hay_traslapes(self):
        nuevo = self._cuadrado(-72.396, 5.337)
        assert validar_sin_traslape(nuevo, []) == []

    def test_contenido_dentro_de_otro_cuenta_como_traslape(self):
        grande = self._cuadrado(-72.396, 5.337, lado=0.004)
        chico = self._cuadrado(-72.395, 5.338, lado=0.001)
        assert validar_sin_traslape(chico, [("Grande", grande)]) == ["Grande"]
