"""Acceso a los datos del rack.

El MCP solo LEE. Hay dos implementaciones con la misma interfaz:
- RepoDynamo: la tabla real de DynamoDB (partición device_id, ordenación ts en ms).
- RepoMemoria: lista en memoria, para desarrollar sin AWS (ver datos_simulados.py).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

MAX_ITEMS = 5000  # tope de seguridad por consulta de rango


def a_python(valor: Any) -> Any:
    """Convierte los Decimal que devuelve boto3 a int/float, recursivamente."""
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, dict):
        return {k: a_python(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [a_python(v) for v in valor]
    return valor


class Repositorio(Protocol):
    def ultimo(self, device_id: str) -> dict | None: ...

    def rango(self, device_id: str, desde_ms: int, hasta_ms: int) -> list[dict]: ...


class RepoDynamo:
    def __init__(self, tabla: str, region: str):
        import boto3  # import tardío: el modo simulado no necesita AWS

        self._tabla = boto3.resource("dynamodb", region_name=region).Table(tabla)

    def ultimo(self, device_id: str) -> dict | None:
        from boto3.dynamodb.conditions import Key

        resp = self._tabla.query(
            KeyConditionExpression=Key("device_id").eq(device_id),
            ScanIndexForward=False,  # del más reciente al más antiguo
            Limit=1,
        )
        items = resp.get("Items", [])
        return a_python(items[0]) if items else None

    def rango(self, device_id: str, desde_ms: int, hasta_ms: int) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("device_id").eq(device_id)
            & Key("ts").between(desde_ms, hasta_ms),
        }
        items: list[dict] = []
        while True:
            resp = self._tabla.query(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp or len(items) >= MAX_ITEMS:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return [a_python(i) for i in items[:MAX_ITEMS]]


class RepoMemoria:
    def __init__(self, items: list[dict]):
        self._items = sorted(items, key=lambda i: (i["device_id"], i["ts"]))

    def ultimo(self, device_id: str) -> dict | None:
        propios = [i for i in self._items if i["device_id"] == device_id]
        return propios[-1] if propios else None

    def rango(self, device_id: str, desde_ms: int, hasta_ms: int) -> list[dict]:
        return [
            i
            for i in self._items
            if i["device_id"] == device_id and desde_ms <= i["ts"] <= hasta_ms
        ][:MAX_ITEMS]
