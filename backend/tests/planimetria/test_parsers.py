"""Tests de parsers de coordenadas: lista manual (decimal y GMS) y CSV (§3.3)."""

from __future__ import annotations

import pytest

from srp.planimetria.parsers import parsear_csv_coordenadas, parsear_lista_manual


class TestParsearListaManual:
    def test_decimal_simple(self):
        texto = "5.3378, -72.3959\n5.3378, -72.3919\n5.3418, -72.3919"
        assert parsear_lista_manual(texto) == [
            (5.3378, -72.3959),
            (5.3378, -72.3919),
            (5.3418, -72.3919),
        ]

    def test_gms_correcto(self):
        # 5°20'16.1" = 5 + 20/60 + 16.1/3600; W y S son negativos
        texto = '5°20\'16.1"N 72°23\'45.2"W'
        [(lat, lng)] = parsear_lista_manual(texto)
        assert lat == pytest.approx(5 + 20 / 60 + 16.1 / 3600, abs=1e-9)
        assert lng == pytest.approx(-(72 + 23 / 60 + 45.2 / 3600), abs=1e-9)

    def test_gms_hemisferios_sur_y_oeste_con_o(self):
        # 'O' (Oeste) es sinónimo de W; S niega la latitud
        texto = '4°30\'00.0"S 70°00\'30.0"O'
        [(lat, lng)] = parsear_lista_manual(texto)
        assert lat == pytest.approx(-4.5)
        assert lng == pytest.approx(-(70 + 30 / 3600))

    def test_gms_orden_lng_primero(self):
        # el hemisferio decide qué es lat y qué es lng, no el orden
        texto = '72°23\'45.2"W 5°20\'16.1"N'
        [(lat, lng)] = parsear_lista_manual(texto)
        assert lat > 0 and lng < 0
        assert lat == pytest.approx(5.337805555, abs=1e-6)

    def test_mezcla_decimal_y_gms(self):
        texto = '5.3378, -72.3959\n5°20\'16.1"N 72°23\'45.2"W'
        puntos = parsear_lista_manual(texto)
        assert len(puntos) == 2
        assert puntos[0] == (5.3378, -72.3959)
        assert puntos[1][0] == pytest.approx(5.337805555, abs=1e-6)

    def test_lineas_vacias_ignoradas(self):
        texto = "\n5.337, -72.396\n\n  \n5.341, -72.392\n"
        assert len(parsear_lista_manual(texto)) == 2

    def test_gms_incompleto_lanza_valueerror(self):
        with pytest.raises(ValueError, match="GMS incompleta"):
            parsear_lista_manual('5°20\'16.1"N')

    def test_linea_decimal_invalida_lanza_valueerror(self):
        with pytest.raises(ValueError):
            parsear_lista_manual("esto no es una coordenada")


class TestParsearCsvCoordenadas:
    def test_con_cabecera_lat_lng(self):
        csv_texto = "lat,lng\n5.337,-72.396\n5.341,-72.392\n"
        assert parsear_csv_coordenadas(csv_texto) == [(5.337, -72.396), (5.341, -72.392)]

    def test_con_cabecera_en_espanol_y_orden_invertido(self):
        csv_texto = "longitud,latitud\n-72.396,5.337\n-72.392,5.341\n"
        assert parsear_csv_coordenadas(csv_texto) == [(5.337, -72.396), (5.341, -72.392)]

    def test_sin_cabecera_asume_lat_lng(self):
        csv_texto = "5.337,-72.396\n5.341,-72.392\n"
        assert parsear_csv_coordenadas(csv_texto) == [(5.337, -72.396), (5.341, -72.392)]

    def test_desde_archivo(self, tmp_path):
        ruta = tmp_path / "coordenadas.csv"
        ruta.write_text("lat,lng\n5.337,-72.396\n5.341,-72.392\n", encoding="utf-8")
        assert parsear_csv_coordenadas(ruta) == [(5.337, -72.396), (5.341, -72.392)]
        # también como str de ruta
        assert parsear_csv_coordenadas(str(ruta)) == [(5.337, -72.396), (5.341, -72.392)]

    def test_fila_invalida_lanza_valueerror(self):
        with pytest.raises(ValueError, match="Fila CSV inválida"):
            parsear_csv_coordenadas("lat,lng\n5.337,abc\n")

    def test_vacio_devuelve_lista_vacia(self):
        assert parsear_csv_coordenadas("") == []
