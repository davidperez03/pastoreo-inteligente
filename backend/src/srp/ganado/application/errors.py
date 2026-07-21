"""Errores de la capa de aplicación del contexto Gestión de Ganado."""

from __future__ import annotations


class LoteNoEncontrado(Exception):
    """El lote referido no existe (o no es visible para la organización)."""
