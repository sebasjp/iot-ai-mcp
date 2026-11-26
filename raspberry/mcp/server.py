"""Servidor MCP del Rack01 (FastMCP). Solo consulta DynamoDB.

Ejecutar:
    uv run server.py                 # HTTP en http://0.0.0.0:8000/mcp
    MCP_DATOS=simulado uv run server.py   # sin AWS, con datos de ensayo
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field

import logica
from repositorio import RepoDynamo, RepoMemoria, Repositorio

load_dotenv()

SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": False}


def crear_repo() -> Repositorio:
    if os.environ.get("MCP_DATOS", "dynamo").lower() == "simulado":
        import datos_simulados

        return RepoMemoria(datos_simulados.generar())
    return RepoDynamo(
        tabla=os.environ["DYNAMO_TABLE"],
        region=os.environ.get("AWS_REGION", "us-east-1"),
    )


repo = crear_repo()


def ahora() -> datetime:
    return datetime.now(tz=logica.ZONA)


mcp = FastMCP(
    name="rack01-monitor",
    instructions=(
        "Monitor inteligente del rack de TI 'rack01'. Tres fuentes con modelos de IA en el borde: "
        "env (temperatura/humedad: normal, falla_enfriamiento, riesgo_condensacion), "
        "vibration (ventilador: apagado, normal, desbalanceado) y "
        "camera (puerta: puerta_cerrada, puerta_abierta). "
        "Las horas están en hora de Colombia (America/Bogota). "
        "Para preguntas relativas como 'anoche' u 'hoy', llama primero a hora_actual. "
        "Para '¿qué pasó...?' usa resumen_rack; para el estado ahora usa las tools de predicción."
    ),
)


@mcp.tool(annotations=SOLO_LECTURA)
def hora_actual() -> dict:
    """Fecha y hora actual en Colombia. Úsala para convertir 'anoche', 'hoy' o
    'la última hora' en fechas ISO para las demás tools."""
    t = ahora()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return {"ahora": t.isoformat(timespec="seconds"), "dia_semana": dias[t.weekday()]}


@mcp.tool(annotations=SOLO_LECTURA)
def consultar_prediccion_imagenes(
    horas: Annotated[int, Field(ge=1, le=168, description="Ventana para listar aperturas")] = 24,
) -> dict:
    """Estado actual de la puerta del rack según la cámara (puerta_abierta o
    puerta_cerrada) y las aperturas de las últimas `horas`, con su duración."""
    return logica.prediccion_imagenes(repo, ahora(), horas)


@mcp.tool(annotations=SOLO_LECTURA)
def consultar_prediccion_sensores() -> dict:
    """Última lectura y predicción del ambiente (temperatura, humedad y su
    clasificación) y de la vibración del ventilador. Marca si hay anomalía y si
    el dato es viejo (posible dispositivo desconectado)."""
    return logica.prediccion_sensores(repo, ahora())


@mcp.tool(annotations=SOLO_LECTURA)
def consultar_historico(
    fuente: Literal["env", "vibration", "camera"],
    desde: Annotated[str, Field(description="Inicio ISO 8601, p. ej. 2026-11-24T22:00 (hora Colombia)")],
    hasta: Annotated[str | None, Field(description="Fin ISO 8601; por defecto, ahora")] = None,
    max_registros: Annotated[int, Field(ge=2, le=500)] = 60,
) -> dict:
    """Lecturas y predicciones de una fuente en un rango de tiempo: estadísticas
    (conteo por etiqueta, mín/máx/promedio), cambios de etiqueta y una muestra
    de registros repartida en el rango."""
    return logica.historico(repo, ahora(), fuente, desde, hasta, max_registros)


@mcp.tool(annotations=SOLO_LECTURA)
def resumen_rack(
    desde: Annotated[str, Field(description="Inicio ISO 8601 (hora Colombia)")],
    hasta: Annotated[str | None, Field(description="Fin ISO 8601; por defecto, ahora")] = None,
) -> dict:
    """Resumen cruzado de las tres fuentes en un periodo: eventos (cambios de
    etiqueta) en orden cronológico, si fueron anómalos, y estadísticas por
    fuente. Ideal para '¿qué pasó anoche en el rack?'."""
    return logica.resumen(repo, ahora(), desde, hasta)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8000")),
    )
