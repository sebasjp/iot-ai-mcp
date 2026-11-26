# Lambda `rack-alarmas` (Juan)

Regla IoT `rack_alarmas_to_lambda` → esta Lambda → Telegram (`telegram/telegram_notify.py`, de Julián).

- `reglas.py`: lógica de alarmas, sin AWS. Prueba: `python test_reglas.py` (13 pruebas).
- `lambda_function.py`: lee el historial de `RackTelemetry` (solo `Query`) y envía las alertas.

| Dispositivo | Dispara cuando | Prioridad |
|---|---|---|
| `rack01-camera` | `puerta_cerrada` → `puerta_abierta` | alta |
| `rack01-env` | 3 seguidas de `falla_enfriamiento` o `riesgo_condensacion` | alta |
| `rack01-vibration` | 3 seguidas de `desbalanceado` o `apagado` | alta |
| Cruzada | vibración anómala + `falla_enfriamiento` (≤ 2 min) | alta |
| Cruzada | `puerta_abierta` + vibración anómala (≤ 2 min) | info |

Solo cuentan las predicciones con confianza ≥ 0,6. Cada alarma suena una vez al entrar en el estado.

## Despliegue

Paquete: `lambda_function.py`, `reglas.py` y `telegram/telegram_notify.py` en la raíz de un zip.
Python 3.12 · 128 MB · timeout 30 s · rol `rack-alarmas-role` (logs + `dynamodb:Query` en `RackTelemetry`).

Variables de entorno: `TABLE_NAME`, `ALARMAS_MODO` (`log` | `telegram`), `TELEGRAM_CHAT_ID`,
`TELEGRAM_BOT_TOKEN` (solo en la consola de la Lambda; nunca en git).

Regla IoT:

```sql
SELECT * FROM 'datacenter/rack01/+' WHERE topic(3) = 'env' OR topic(3) = 'vibration' OR topic(3) = 'camera'
```
