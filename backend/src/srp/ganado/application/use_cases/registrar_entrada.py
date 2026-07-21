"""Caso de uso: registrar la entrada de un lote a un potrero.

Abre la fila en `eventos_pastoreo`, actualiza `potrero_actual_id` del lote y
publica `LoteEntroAPotrero` por el bus. El estado del potrero (→ 'ocupado')
lo actualiza el contexto de Gestión de Potreros al consumir el evento; este
contexto no toca la tabla `potreros`.
"""

from __future__ import annotations

from datetime import date

from srp.ganado.application.dto import EventoPastoreoDTO
from srp.ganado.application.errors import LoteNoEncontrado
from srp.ganado.domain.ports.eventos_pastoreo_repository import EventosPastoreoRepository
from srp.ganado.domain.ports.lote_repository import LoteRepository
from srp.shared.ports import PublicadorEventos
from srp.shared.types import LoteId, PotreroId


class RegistrarEntrada:
    def __init__(
        self,
        lotes: LoteRepository,
        eventos_pastoreo: EventosPastoreoRepository,
        publicador: PublicadorEventos,
    ) -> None:
        self._lotes = lotes
        self._eventos_pastoreo = eventos_pastoreo
        self._publicador = publicador

    async def ejecutar(
        self,
        lote_id: LoteId,
        potrero_id: PotreroId,
        fecha: date | None = None,
        biomasa_inicial: float | None = None,
    ) -> EventoPastoreoDTO:
        lote = await self._lotes.obtener(lote_id)
        if lote is None:
            raise LoteNoEncontrado(f"Lote {lote_id} no encontrado")
        fecha = fecha or date.today()

        # El agregado valida la invariante (no estar ya en un potrero) y
        # emite el evento de dominio.
        lote.entrar_a_potrero(potrero_id, fecha, biomasa_inicial)

        evento = await self._eventos_pastoreo.abrir_evento(
            lote_id=lote.id,
            potrero_id=potrero_id,
            fecha_entrada=fecha,
            biomasa_inicial=biomasa_inicial,
        )
        await self._lotes.guardar(lote)

        await self._publicador.publicar(lote.eventos_pendientes())
        lote.limpiar_eventos()
        return EventoPastoreoDTO.desde_entidad(evento)
