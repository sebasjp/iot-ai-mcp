"""Envío de alarmas del Rack01 por Telegram (solo texto).

Módulo sin dependencias externas (solo librería estándar), pensado para
copiarse tal cual dentro de la Lambda de alarmas del backend.

Configuración por variables de entorno (nunca en el código ni en el repo):
    TELEGRAM_BOT_TOKEN  token del bot entregado por @BotFather
    TELEGRAM_CHAT_ID    id del chat o grupo que recibe las alarmas

Uso desde la Lambda:
    from telegram_notify import enviar_alerta
    enviar_alerta("Ventilador desbalanceado, revisar", prioridad="alta")
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/{metodo}"
TIMEOUT_S = 10
ZONA_COLOMBIA = timezone(timedelta(hours=-5))

PRIORIDADES = {
    "alta": "🔴 ALERTA",
    "media": "🟠 AVISO",
    "info": "🔵 INFO",
}


def _llamar_api(token: str, metodo: str, datos: dict) -> dict:
    """Hace un POST a la API de Bot de Telegram y devuelve el JSON de respuesta."""
    req = urllib.request.Request(
        API_URL.format(token=token, metodo=metodo),
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Telegram responde con JSON también en los errores (401, 400, 429...).
        try:
            return json.loads(e.read().decode("utf-8"))
        except ValueError:
            return {"ok": False, "error_code": e.code, "description": str(e)}


def formatear_alerta(texto: str, prioridad: str = "alta", ts_ms: int | None = None) -> str:
    """Arma el mensaje final: encabezado de prioridad, rack, hora local y texto."""
    encabezado = PRIORIDADES.get(prioridad, PRIORIDADES["alta"])
    momento = (
        datetime.fromtimestamp(ts_ms / 1000, tz=ZONA_COLOMBIA)
        if ts_ms is not None
        else datetime.now(tz=ZONA_COLOMBIA)
    )
    return f"{encabezado} · Rack01\n🕒 {momento:%Y-%m-%d %H:%M:%S}\n\n{texto}"


def enviar_alerta(
    texto: str,
    prioridad: str = "alta",
    ts_ms: int | None = None,
    token: str | None = None,
    chat_id: str | None = None,
    reintentos: int = 2,
) -> bool:
    """Envía una alarma de texto al chat configurado.

    Args:
        texto: cuerpo del mensaje, p. ej. "Puerta del rack abierta".
        prioridad: "alta", "media" o "info" (ver alarmas cruzadas en la definición).
        ts_ms: epoch en milisegundos del evento (campo `ts` del payload). Si no
            se da, se usa la hora actual.
        token, chat_id: opcionales; por defecto se leen de las variables de entorno.
        reintentos: reintentos ante errores de red o límite de tasa (429).

    Returns:
        True si Telegram confirmó el envío. Nunca lanza excepción, para que una
        falla de Telegram no tumbe la Lambda: los errores quedan en el log.
    """
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.error("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return False

    datos = {"chat_id": chat_id, "text": formatear_alerta(texto, prioridad, ts_ms)}

    for intento in range(reintentos + 1):
        try:
            resp = _llamar_api(token, "sendMessage", datos)
        except (urllib.error.URLError, TimeoutError) as e:
            log.warning("Error de red enviando a Telegram (intento %d): %s", intento + 1, e)
            time.sleep(2**intento)
            continue

        if resp.get("ok"):
            return True

        codigo = resp.get("error_code")
        if codigo == 429:  # límite de tasa: Telegram dice cuánto esperar
            espera = resp.get("parameters", {}).get("retry_after", 1)
            log.warning("Telegram pidió esperar %s s (429)", espera)
            time.sleep(min(espera, 30))
            continue

        # 400/401/403: chat_id o token incorrectos, o el bot fue sacado del grupo.
        # Reintentar no lo arregla.
        log.error("Telegram rechazó el mensaje: %s %s", codigo, resp.get("description"))
        return False

    log.error("No se pudo enviar la alerta tras %d intentos", reintentos + 1)
    return False
