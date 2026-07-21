"""Proyecciones de lectura cross-contexto (CQRS ligero, §19.1).

Este paquete NO es un bounded context: es el lado de consulta. Puede leer las
tablas/eventos de cualquier contexto (solo lectura) y componer vistas para la
UI. Las escrituras siguen pasando exclusivamente por los casos de uso de cada
contexto.
"""
