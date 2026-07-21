"""Tests del adaptador del puerto GeometriaValidator (§18.4)."""

from __future__ import annotations

import pytest

from srp.planimetria.validator import PlanimetriaGeometriaValidator
from srp.shared.ports import GeometriaValidator
from tests.planimetria.conftest import AREA_ESPERADA_HA


class TestPlanimetriaGeometriaValidator:
    def test_implementa_el_puerto_del_shared_kernel(self):
        assert issubclass(PlanimetriaGeometriaValidator, GeometriaValidator)

    def test_devuelve_contrato_del_puerto(self, cuadrado_casanare):
        validador: GeometriaValidator = PlanimetriaGeometriaValidator()
        resultado = validador.construir_y_validar(cuadrado_casanare)

        assert set(resultado) == {"geojson", "area_ha", "n_puntos", "advertencia"}
        assert resultado["geojson"]["type"] == "Polygon"
        assert resultado["area_ha"] == pytest.approx(AREA_ESPERADA_HA, rel=0.05)
        assert resultado["n_puntos"] == 5
        assert resultado["advertencia"] is None

    def test_propaga_valueerror_con_pocos_puntos(self):
        with pytest.raises(ValueError):
            PlanimetriaGeometriaValidator().construir_y_validar([(5.3, -72.4)])
