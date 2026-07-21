"""Excepciones del dominio de Gestión de Potreros."""

from __future__ import annotations


class DomainError(Exception):
    """Violación de una regla de negocio del dominio (§17.2)."""
