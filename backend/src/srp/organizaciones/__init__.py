"""Gestión de fincas dentro de una organización (§19.3).

No es un bounded context de dominio con reglas de negocio propias — es CRUD
de tenancy sobre `organizaciones`/`fincas`, cuyas únicas invariantes ya las
aplica el esquema (constraints, RLS). Se mantiene fuera de gestion_potreros y
ganado porque ambos dependen de finca_id sin ser dueños del concepto.
"""
