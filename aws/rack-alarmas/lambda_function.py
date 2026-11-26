"""Lambda de alarmas del Rack01: regla IoT -> esta Lambda -> Telegram.

La invoca la regla IoT `rack_alarmas_to_lambda` con cada mensaje de
datacenter/rack01/{env,vibration,camera}. Lee el historial de RackTelemetry (solo Query) y aplica
las reglas de reglas.py. El envío usa telegram_notify.py de Julián (telegram/).

Variables de entorno:
  TABLE_NAME          RackTelemetry
  ALARMAS_MODO        "log" (solo CloudWatch, para pruebas) o "telegram" (envía de verdad)
  TELEGRAM_BOT_TOKEN  lo pone Juan en la consola; nunca en git
  TELEGRAM_CHAT_ID    id del grupo de alertas
"""
import json
import os

import boto3
from boto3.dynamodb.conditions import Key

from reglas import evaluar
from telegram_notify import enviar_alerta

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
DISPOSITIVOS = {"rack01-env", "rack01-vibration", "rack01-camera"}


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
    for a in alertas:
        print(f"[ALERTA {a['prioridad']}] {a['texto']!r}")
        if modo == "telegram":
            enviado = enviar_alerta(a["texto"], prioridad=a["prioridad"], ts_ms=a["ts"])
            print(f"[TELEGRAM] {'enviado' if enviado else 'FALLÓ'}")
    return {"alertas": len(alertas), "modo": modo}
