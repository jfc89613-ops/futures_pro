# Auditoría de redundancias y riesgos

## Acciones implementadas
- Se eliminaron los artefactos `.bak` y `.save` duplicados dentro de `pro_bot` y `scripts`, dejando un único punto de entrada por módulo operativo y evitando rutas de ejecución divergentes.
- Se retiró el backend alternativo de WebSocket (`ws_multi_new`) para adoptar como estándar la implementación basada en `websocket.WebSocketApp`.
- Se centralizó el límite global de posiciones/órdenes activas dentro de `pro_bot.core.execution`, reutilizando el mismo control en los flujos `main_multi` y `multi`.

## Estado actual
### Klines
`pro_bot/core/binance_klines.py` mantiene la lógica extendida de paginación hacia atrás para peticiones con `limit` mayores a 1500 velas, garantizando una única implementación oficial para el histórico de velas.【F:pro_bot/core/binance_klines.py†L1-L86】

### Control de riesgo
`pro_bot/core/execution.py` expone `get_max_active_positions()` como única fuente del límite y `enter_position` delega en `_can_open_new_position`, evitando cálculos duplicados antes de enviar órdenes.【F:pro_bot/core/execution.py†L13-L40】【F:pro_bot/core/execution.py†L166-L211】

### Bots multi-símbolo
Los flujos multi-símbolo ahora confían exclusivamente en el control centralizado: `pro_bot/app/multi.py` reutiliza `_can_open_new_position` y elimina límites locales, mientras que `pro_bot/app/main_multi.py` sólo informa el límite obtenido de `get_max_active_positions()` en los logs.【F:pro_bot/app/multi.py†L12-L16】【F:pro_bot/app/multi.py†L78-L103】【F:pro_bot/app/main_multi.py†L10-L38】【F:pro_bot/app/main_multi.py†L176-L186】

### WebSocket multiplexado
`pro_bot/core/ws_multi.py` queda como backend oficial para multiplexar klines de Futuros usando `websocket.WebSocketApp`, con reconexión automática y wrapper simple para mantener compatibilidad con el resto del bot.【F:pro_bot/core/ws_multi.py†L1-L93】
