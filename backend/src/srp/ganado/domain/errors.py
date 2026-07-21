"""Errores del dominio de Gestión de Ganado."""

from __future__ import annotations


class DomainError(Exception):
    """Violación de una regla de negocio del contexto Gestión de Ganado."""
