"""Tests del pipeline agnóstico a la fuente (§3.2): GPX, KML, CSV, DXF y manual."""

from __future__ import annotations

import ezdxf
import pytest
from pyproj import Transformer

from srp.planimetria.dxf import dxf_a_geojson, reproyectar_geojson
from srp.planimetria.formatos import FormatoEntrada, normalizar_entrada
from srp.planimetria.poligono import construir_poligono_validado
from tests.planimetria.conftest import AREA_ESPERADA_HA, CUADRADO_CASANARE

GPX_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>lindero potrero 1</name><trkseg>
    <trkpt lat="5.337" lon="-72.396"/>
    <trkpt lat="5.337" lon="-72.392"/>
    <trkpt lat="5.341" lon="-72.392"/>
    <trkpt lat="5.341" lon="-72.396"/>
  </trkseg></trk>
</gpx>
"""

KML_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document><Placemark><name>Potrero 1</name>
    <Polygon><outerBoundaryIs><LinearRing><coordinates>
      -72.396,5.337,0 -72.392,5.337,0 -72.392,5.341,0 -72.396,5.341,0 -72.396,5.337,0
    </coordinates></LinearRing></outerBoundaryIs></Polygon>
  </Placemark></Document>
</kml>
"""


def _es_cuadrado_casanare(puntos: list[tuple[float, float]]) -> None:
    """El resultado normalizado debe reconstruir el cuadrado de ~19.6 ha."""
    resultado = construir_poligono_validado(puntos)
    assert resultado["area_ha"] == pytest.approx(AREA_ESPERADA_HA, rel=0.05)
    assert resultado["advertencia"] is None


def _crear_dxf_epsg9377(ruta, cerrar: bool = True) -> list[tuple[float, float]]:
    """Genera un DXF con el cuadrado de Casanare en MAGNA-SIRGAS (EPSG:9377)."""
    a_9377 = Transformer.from_crs("EPSG:4326", "EPSG:9377", always_xy=True)
    vertices = [a_9377.transform(lng, lat) for lat, lng in CUADRADO_CASANARE]

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(vertices, close=cerrar, dxfattribs={"layer": "POTRERO_1"})
    doc.saveas(str(ruta))
    return vertices


class TestNormalizarEntrada:
    def test_lista_manual(self):
        texto = "\n".join(f"{lat}, {lng}" for lat, lng in CUADRADO_CASANARE)
        puntos = normalizar_entrada(texto, FormatoEntrada.LISTA_MANUAL)
        assert puntos == CUADRADO_CASANARE
        _es_cuadrado_casanare(puntos)

    def test_csv(self, tmp_path):
        ruta = tmp_path / "potrero.csv"
        filas = "\n".join(f"{lat},{lng}" for lat, lng in CUADRADO_CASANARE)
        ruta.write_text(f"lat,lng\n{filas}\n", encoding="utf-8")
        puntos = normalizar_entrada(ruta, FormatoEntrada.CSV)
        assert puntos == CUADRADO_CASANARE
        _es_cuadrado_casanare(puntos)

    def test_gpx(self, tmp_path):
        ruta = tmp_path / "lindero.gpx"
        ruta.write_text(GPX_FIXTURE, encoding="utf-8")
        puntos = normalizar_entrada(ruta, FormatoEntrada.GPX)
        assert [(round(lat, 6), round(lng, 6)) for lat, lng in puntos] == CUADRADO_CASANARE
        _es_cuadrado_casanare(puntos)

    def test_kml(self, tmp_path):
        ruta = tmp_path / "potrero.kml"
        ruta.write_text(KML_FIXTURE, encoding="utf-8")
        puntos = normalizar_entrada(ruta, FormatoEntrada.KML)
        # el KML trae el anillo cerrado y con altitud; todo (lat, lng) 2D
        assert all(len(p) == 2 for p in puntos)
        assert {(round(lat, 6), round(lng, 6)) for lat, lng in puntos} == set(CUADRADO_CASANARE)
        _es_cuadrado_casanare(puntos)

    def test_dxf_epsg9377_reproyectado(self, tmp_path):
        ruta = tmp_path / "plano.dxf"
        _crear_dxf_epsg9377(ruta)
        puntos = normalizar_entrada(ruta, FormatoEntrada.DXF)
        # ida y vuelta 4326 → 9377 → 4326: milimétrica (1e-6° ≈ 0.11 m)
        assert {(round(lat, 6), round(lng, 6)) for lat, lng in puntos} == set(CUADRADO_CASANARE)
        _es_cuadrado_casanare(puntos)

    def test_dxf_sin_polilineas_lanza_valueerror(self, tmp_path):
        ruta = tmp_path / "vacio.dxf"
        ezdxf.new().saveas(str(ruta))
        with pytest.raises(ValueError, match="no contiene polilíneas"):
            normalizar_entrada(ruta, FormatoEntrada.DXF)


class TestDxfAGeojson:
    def test_extrae_polilinea_con_capa_y_cierra_el_anillo(self, tmp_path):
        ruta = tmp_path / "plano.dxf"
        vertices = _crear_dxf_epsg9377(ruta, cerrar=True)

        fc = dxf_a_geojson(ruta)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 1
        feature = fc["features"][0]
        assert feature["properties"]["nombre"] == "POTRERO_1"
        anillo = feature["geometry"]["coordinates"][0]
        assert anillo[0] == anillo[-1]  # anillo cerrado
        assert len(anillo) == len(vertices) + 1

    def test_reproyectar_geojson_a_wgs84(self, tmp_path):
        ruta = tmp_path / "plano.dxf"
        _crear_dxf_epsg9377(ruta)
        fc = dxf_a_geojson(ruta)

        fc_wgs84 = reproyectar_geojson(fc)
        anillo = fc_wgs84["features"][0]["geometry"]["coordinates"][0]
        # GeoJSON usa (lng, lat): longitudes ~-72.39, latitudes ~5.34
        for lng, lat in anillo:
            assert lng == pytest.approx(-72.394, abs=0.01)
            assert lat == pytest.approx(5.339, abs=0.01)
        # no muta la colección original (sigue en metros EPSG:9377)
        x0 = fc["features"][0]["geometry"]["coordinates"][0][0][0]
        assert abs(x0) > 1000
