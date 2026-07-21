"""Contexto delimitado: Gestión de Ganado (§17.1).

Lenguaje ubicuo: Lote, UA equivalente, Consumo diario, Evento de pastoreo.
Dueño de las tablas `lotes_ganado` y `eventos_pastoreo`. El estado del potrero
(ocupado/descanso) pertenece al contexto de Gestión de Potreros y se actualiza
allí reaccionando a los eventos `LoteEntroAPotrero` / `LoteSalioDePotrero`;
este contexto NUNCA escribe sobre la tabla `potreros`.
"""
