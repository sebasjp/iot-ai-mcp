# Inventario de AWS (fase 0b) — 2026-11-25

Cuenta `041118530115`, región `us-east-1`. Revisión de solo lectura (usuario `claude-lectura`,
política `ReadOnlyAccess`), comparada con el repo de la Práctica 3
(`Juanxo17/humidity-and-temperature-monitor-serverless`).

## Lo que hay

| Recurso | Nombre | Detalle |
|---|---|---|
| Thing | `rack01` | 1 certificado activo (`ddeeced2…`) |
| Política IoT | `rack-01-policy` | Connect `client/rack01` · Publish `datacenter/rack01/telemetry` · Subscribe/Receive `datacenter/rack01/commands` |
| Endpoint IoT | `a1om6z0mkt0pcq-ats.iot.us-east-1.amazonaws.com` | ATS |
| Regla IoT | `rack_telemetry_to_dynamodb` | `SELECT *, timestamp() AS received_at FROM 'datacenter/+/telemetry'` → DynamoDB `RackTelemetry` (putItem, rol `iot-dynamodb-rack-role`) |
| Rol | `iot-dynamodb-rack-role` | `dynamodb:PutItem` sobre `RackTelemetry` |
| Tabla | `RackTelemetry` | PK `device_id` (S), SK `ts` (N), bajo demanda, 1066 ítems, sin Streams |
| Lambda | `rack-api` | Python 3.12, 128 MB, 15 s · env `TABLE_NAME`, `IOT_ENDPOINT` |
| Rol | `rack-api-role` | `dynamodb:Query` en `RackTelemetry` · `iot:Publish` en `datacenter/*/commands` · logs básicos |
| API | `rack-api` (`i3plegeuv9`) | HTTP API · `GET /readings`, `POST /command` · CORS `*` (GET, POST) |
| Bucket | `rack-monitor-dashboard-041118530115` | Sitio web estático (index.html / 404.html) |

## Comparación con la arquitectura de la Actividad 4

| Recurso | Estado | Qué se hace |
|---|---|---|
| Thing `rack01`, política y regla de `telemetry` | Se queda | Legado intacto |
| Tabla `RackTelemetry` y rol `iot-dynamodb-rack-role` | Se reutiliza | La regla nueva usa el mismo rol, porque ya permite PutItem en la tabla |
| Things `rack01-env`, `rack01-vibration`, `rack01-camera` | **Falta** | Crear con un certificado y una política cada uno |
| Regla para `datacenter/rack01/{env,vibration,camera}` | **Falta** | La regla actual solo escucha `+/telemetry`; los tópicos nuevos no le llegan |
| Lambda `rack-api` | **Se adapta** | Su validación `^rack\d{2}$` rechaza `rack01-env` y los demás `device_id` nuevos; hay que ampliarla |
| Lambda de alarmas + Telegram | **Falta** | Regla IoT → Lambda → API de Telegram |
| Bucket de fotos y permiso de subida para la Pi | **Falta** | Por decidir el mecanismo |
| Usuario IAM de solo lectura para el MCP | **Falta** | `dynamodb:Query`/`GetItem` sobre `RackTelemetry` |
| Dashboard | **Se adapta** | Consume `GET /readings` con `device_id=rack01`; agregar los tres dispositivos y las alarmas |
