"""Caso de uso: registrar la salida de un lote de su potrero actual.

Cierra el evento abierto en `eventos_pastoreo` con `biomasa_final`, pone
`potrero_actual_id = NULL` en el lote y publica `LoteSalioDePotrero`. La
transición del potrero a 'descanso' y la actualización del factor de fatiga
ocurren en otros contextos, reaccionando al evento.
"""

from __future__ import annotations

from datetime import date

from srp.ganado.application.dto import EventoPastoreoDTO
from srp.ganado.application.errors import LoteNoEncontrado
from srp.ganado.domain.errors import DomainError
from srp.ganado.domain.ports.eventos_pastoreo_repository import EventosPastoreoRepository
from srp.ganado.domain.ports.lote_repository import LoteRepository
from srp.shared.ports import PublicadorEventos
from srp.shared.types import LoteId


class RegistrarSalida:
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
        fecha: date | None = None,
        biomasa_final: float | None = None,
    ) -> EventoPastoreoDTO:
        lote = await self._lotes.obtener(lote_id)
        if lote is None:
            raise LoteNoEncontrado(f"Lote {lote_id} no encontrado")
        fecha = fecha or date.today()

        # El agregado valida la invariante (estar en un potrero) y emite el
        # evento de dominio con la biomasa inicial del ciclo en curso.
        lote.salir_de_potrero(fecha, biomasa_final)

        evento_abierto = await self._eventos_pastoreo.evento_abierto_de_lote(lote_id)
        if evento_abierto is None:
            # potrero_actual_id sin evento abierto: inconsistencia de datos.
            raise DomainError(
                f"El lote {lote_id} figura en un potrero pero no tiene "
                "evento de pastoreo abierto"
            )
        evento = await self._eventos_pastoreo.cerrar_evento(
            evento_abierto.id, fecha_salida=fecha, biomasa_final=biomasa_final
        )
        await self._lotes.guardar(lote)

        await self._publicador.publicar(lote.eventos_pendientes())
        lote.limpiar_eventos()
        return EventoPastoreoDTO.desde_entidad(evento)
