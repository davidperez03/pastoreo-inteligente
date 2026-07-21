"""Contexto delimitado: Calibración (§17.1).

Lenguaje ubicuo: Factor de fatiga, Prior, Observación. Aprende, por potrero,
un factor de fatiga bayesiano a partir de las salidas reales de lote.

La actualización de `potreros.factor_fatiga` y `potreros.n_ciclos_observados`
es responsabilidad EXCLUSIVA de este contexto (§17.1), aunque esas columnas
vivan físicamente en la tabla `potreros` (propiedad del contexto Gestión de
Potreros). Ningún otro contexto escribe esas dos columnas.
"""
