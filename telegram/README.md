# Notificaciones por Telegram — Julián

Bot: **@Monitoreo_Rack_Ti_bot**. Envía las alarmas del Rack01 **solo como texto**.

## Interfaz con el backend (propuesta a Juan)

La Lambda de alarmas de Juan decide **cuándo** alertar. Para enviar, importa este módulo:

```python
from telegram_notify import enviar_alerta

enviar_alerta("Puerta del rack abierta", prioridad="alta", ts_ms=payload["ts"])
```

- Se copia `telegram_notify.py` dentro del paquete de la Lambda. **No tiene dependencias externas** (solo usa `urllib`).
- En la configuración de la Lambda se definen las variables de entorno `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. Julián se las pasa a Juan **por un canal privado**.
- La Lambda necesita salida a Internet. Por defecto la tiene, siempre que no esté dentro de una VPC.
- `enviar_alerta` devuelve `True` o `False` y **nunca lanza excepción**: si Telegram falla, la Lambda sigue funcionando. Reintenta ante errores de red y ante el límite de tasa (429).

| `prioridad` | Encabezado | Cuándo se usa |
|---|---|---|
| `alta` | 🔴 ALERTA | Alarmas individuales y la cruzada de falla de enfriamiento confirmada |
| `media` | 🟠 AVISO | Disponible si se necesita un nivel intermedio |
| `info` | 🔵 INFO | Alarma cruzada de puerta abierta + vibración (probable intervención de un técnico) |

Ejemplo del mensaje que llega:

```
🔴 ALERTA · Rack01
🕒 2026-11-25 02:14:07

Ventilador desbalanceado, revisar
```

## Configuración inicial (en el portátil)

```bash
cd telegram
cp .env.example .env              # poner el token real
python herramientas.py verificar  # valida el token y avisa si hay un webhook viejo
# agregar el bot al grupo de alertas y escribir algo en el grupo
python herramientas.py chat_id    # copiar el id del grupo (negativo) a .env
python herramientas.py prueba     # debe llegar un mensaje al grupo
```
