"""Lambda de alarmas del Rack01: regla IoT -> esta Lambda -> Telegram.

La invoca la regla IoT `rack_alarmas_to_lambda` con cada mensaje de
datacenter/rack01/{env,vibration,camera}. Lee el historial de RackTelemetry (solo Query) y aplica
las reglas de reglas.py. El envío usa telegram_notify.py de Julián (telegram/).

Variables de entorno:
  TABLE_NAME          RackTelemetry
  ALARMAS_MODO        "log" (solo CloudWatch, para pruebas) o "telegram" (envía de verdad)
  TELEGRAM_BOT_TOKEN  lo pone Juan en la consola; nunca en git
  TELEGRAM_CHAT_ID    id del grupo de alertas

Cada alarma se guarda también en RackTelemetry con device_id "rack01-alarmas" (permiso PutItem
limitado a esa clave en el rol) para que el dashboard muestre el historial.
"""
import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from reglas import evaluar
from telegram_notify import enviar_alerta

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
DISPOSITIVOS = {"rack01-env", "rack01-vibration", "rack01-camera"}
ALARMAS_ID = "rack01-alarmas"  # filas de alarmas en RackTelemetry (las lee el dashboard)


def historial(device_id: str, antes_de_ts: int, n: int) -> list[dict]:
    """Últimas `n` predicciones de `device_id` con ts < antes_de_ts, de la más nueva a la más vieja."""
    resp = table.query(
        KeyConditionExpression=Key("device_id").eq(device_id) & Key("ts").lt(antes_de_ts),
        ScanIndexForward=False,
        Limit=n,
    )
    return resp["Items"]


def lambda_handler(event, context):
    if event.get("device_id") not in DISPOSITIVOS or "label" not in event or "ts" not in event:
        print(f"[IGNORADO] {json.dumps(event, default=str)}")
        return {"alertas": 0}

    alertas = evaluar(event, historial)
    modo = os.environ.get("ALARMAS_MODO", "log")
    for i, a in enumerate(alertas):
        print(f"[ALERTA {a['prioridad']}] {a['texto']!r}")
        enviado = None
        if modo == "telegram":
            enviado = enviar_alerta(a["texto"], prioridad=a["prioridad"], ts_ms=a["ts"])
            print(f"[TELEGRAM] {'enviado' if enviado else 'FALLÓ'}")
        guardar(a, event, enviado, i)
    return {"alertas": len(alertas), "modo": modo}


def guardar(alerta: dict, origen: dict, enviado: bool | None, indice: int) -> None:
    """Guarda la alarma en RackTelemetry (device_id rack01-alarmas) para el dashboard.

    Si falla (p. ej. falta el permiso), solo se registra: la alarma ya salió por Telegram.
    """
    item = {
        "device_id": ALARMAS_ID,
        # ts en ms (como el resto de la tabla); + índice para que una alarma cruzada del mismo
        # mensaje no pise a la individual
        "ts": int(alerta["ts"]) + indice,
        "evento_ts": int(alerta["ts"]),
        "prioridad": alerta["prioridad"],
        "texto": alerta["texto"],
        "origen": origen["device_id"],
        "label": origen["label"],
        "confidence": Decimal(str(origen["confidence"])),
        "telegram": "enviado" if enviado else ("fallo" if enviado is False else "no_enviado"),
    }
    try:
        table.put_item(Item=item)
    except Exception as e:  # noqa: BLE001
        print(f"[DYNAMODB] No se pudo guardar la alarma: {e!r}")
