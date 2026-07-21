"""Router HTTP del contexto Rotación (§9): sugerencia de calendario.

Router standalone: no conoce a la app; se registra en `srp.app` en la etapa
de integración. Espera `request.app.state.pool` (asyncpg) creado por el
lifespan de la aplicación.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request

from srp.rotacion.application.sugerir_rotacion import SugerirRotacion
from srp.rotacion.domain.motor import MotorGreedy, ResultadoRotacion
from srp.rotacion.infrastructure.proyeccion_postgres import ProyeccionRotacionPostgres
from srp.shared.auth import UsuarioActual, get_current_user
from srp.shared.types import FincaId

router = APIRouter(tags=["rotacion"])


def _serializar(resultado: ResultadoRotacion) -> dict:
    cal = resultado.calendario
    return {
        "finca_id": str(cal.finca_id),
        "horizonte_dias": cal.horizonte_dias,
        "movimientos": [
            {
                "lote_id": str(m.lote_id),
                "potrero_id": str(m.potrero_id),
                "fecha": m.fecha.isoformat(),
            }
            for m in cal.movimientos
        ],
        "advertencias": list(resultado.advertencias),
    }


@router.get("/fincas/{finca_id}/rotacion/sugerir")
async def sugerir_rotacion(
    finca_id: uuid.UUID,
    request: Request,
    horizonte_dias: int = Query(default=30, ge=1, le=180),
    user: UsuarioActual = Depends(get_current_user),
) -> dict:
    proyeccion = ProyeccionRotacionPostgres(request.app.state.pool, user.organizacion_id)
    caso_uso = SugerirRotacion(proyeccion=proyeccion, optimizador=MotorGreedy())
    resultado = await caso_uso.ejecutar(FincaId(finca_id), horizonte_dias)
    return _serializar(resultado)
