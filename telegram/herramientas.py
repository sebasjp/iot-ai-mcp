"""Herramientas de configuración y prueba del bot (se ejecutan en el portátil).

Lee el token y el chat_id de telegram/.env (no versionado).

    python herramientas.py verificar    # comprueba el token y muestra el bot
    python herramientas.py chat_id      # lista los chats que le escribieron al bot
    python herramientas.py prueba       # envía una alerta de prueba al TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from telegram_notify import _llamar_api, enviar_alerta


def cargar_env(ruta: Path = Path(__file__).with_name(".env")) -> None:
    """Carga KEY=VALUE de un .env simple sin depender de python-dotenv."""
    if not ruta.exists():
        sys.exit(f"No existe {ruta}. Copia .env.example a .env y pon el token.")
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def token() -> str:
    t = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not t:
        sys.exit("Falta TELEGRAM_BOT_TOKEN en .env")
    return t


def verificar() -> None:
    resp = _llamar_api(token(), "getMe", {})
    if not resp.get("ok"):
        sys.exit(f"Token inválido: {resp.get('description')}")
    bot = resp["result"]
    print(f"OK -> @{bot['username']} (id {bot['id']}, nombre '{bot['first_name']}')")

    hook = _llamar_api(token(), "getWebhookInfo", {}).get("result", {})
    if hook.get("url"):
        print(
            "AVISO: el bot tiene un webhook activo del proyecto anterior:\n"
            f"  {hook['url']}\n"
            "  Mientras exista, 'chat_id' no funciona. Si ese proyecto ya no se usa,\n"
            "  bórralo con: python herramientas.py borrar_webhook"
        )


def chat_id() -> None:
    resp = _llamar_api(token(), "getUpdates", {})
    if not resp.get("ok"):
        sys.exit(f"Error: {resp.get('description')}")
    chats = {}
    for upd in resp["result"]:
        msg = upd.get("message") or upd.get("my_chat_member") or upd.get("channel_post") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name")
    if not chats:
        print(
            "No hay mensajes recientes. Agrega el bot al grupo, escribe algo en el\n"
            "grupo (p. ej. /start@Monitoreo_Rack_Ti_bot) y vuelve a ejecutar esto."
        )
        return
    for cid, nombre in chats.items():
        tipo = "grupo" if cid < 0 else "privado"
        print(f"{cid}\t{tipo}\t{nombre}")


def borrar_webhook() -> None:
    resp = _llamar_api(token(), "deleteWebhook", {})
    print("Webhook borrado" if resp.get("ok") else f"Error: {resp.get('description')}")


def prueba() -> None:
    ok = enviar_alerta(
        "Mensaje de prueba del sistema de monitoreo. Si lo ves, el bot quedó listo ✅",
        prioridad="info",
    )
    print("Enviado" if ok else "Falló el envío (revisa el log y TELEGRAM_CHAT_ID)")


COMANDOS = {"verificar": verificar, "chat_id": chat_id, "prueba": prueba, "borrar_webhook": borrar_webhook}

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 2 or sys.argv[1] not in COMANDOS:
        sys.exit(__doc__)
    cargar_env()
    COMANDOS[sys.argv[1]]()
