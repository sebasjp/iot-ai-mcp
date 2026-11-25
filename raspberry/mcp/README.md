# Servidor MCP del Rack01 — Julián

Servidor [FastMCP](https://gofastmcp.com) que permite consultar en lenguaje natural el estado del rack. **Solo lee DynamoDB**: no habla con los dispositivos.

## Tools

| Tool | Qué responde |
|---|---|
| `hora_actual` | Fecha y hora en Colombia, para que el LLM resuelva "anoche", "hoy", etc. |
| `consultar_prediccion_imagenes` | Estado actual de la puerta y las aperturas recientes, con su duración |
| `consultar_prediccion_sensores` | Última lectura y predicción de temperatura/humedad y de vibración. Avisa si el dato es viejo |
| `consultar_historico` | Una fuente (`env`, `vibration` o `camera`) en un rango de tiempo: estadísticas, cambios de etiqueta y una muestra de registros |
| `resumen_rack` | Eventos de las tres fuentes en orden cronológico. Pensada para *"¿qué pasó anoche en el rack?"* |

## Estructura

| Archivo | Contenido |
|---|---|
| `server.py` | Definición de las tools con FastMCP y arranque por HTTP |
| `logica.py` | Lógica de las consultas: transiciones, aperturas, resúmenes |
| `repositorio.py` | Acceso a DynamoDB (`RepoDynamo`) o a datos en memoria (`RepoMemoria`) |
| `datos_simulados.py` | 24 h de datos de ensayo con el formato del payload acordado |
| `tests/` | Tests con pytest. La tabla de DynamoDB se simula con `moto` |

## Desarrollo en el portátil

```powershell
cd raspberry\mcp
Copy-Item .env.example .env   # MCP_DATOS=simulado para trabajar sin AWS
uv sync
uv run pytest                 # tests
uv run server.py              # http://localhost:8000/mcp
```

Para usar la tabla real, cambia `MCP_DATOS=dynamo` y completa en `.env` las credenciales IAM de solo lectura que entrega Juan.

## Conectar un cliente (VS Code)

Crea el archivo `.vscode/mcp.json`:

```json
{
  "servers": {
    "rack01": { "type": "http", "url": "http://<ip-de-la-pi>:8000/mcp" }
  }
}
```

## Despliegue en la Raspberry Pi

```bash
git clone <repo> ~/iot-ai-mcp && cd ~/iot-ai-mcp/raspberry/mcp
cp .env.example .env && nano .env      # MCP_DATOS=dynamo + credenciales
uv sync --frozen
sudo cp rack-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now rack-mcp
```

Para actualizar: `git pull && uv sync --frozen && sudo systemctl restart rack-mcp`.
