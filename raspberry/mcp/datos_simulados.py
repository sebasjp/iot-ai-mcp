"""Genera 24 h de mensajes falsos con el formato de la sección 6.3.

Sirve para desarrollar y ensayar la demo sin AWS. Reproduce el ejemplo del
documento: "anoche" a las 2:14 a. m. el ventilador se desbalanceó, la
temperatura subió ~3 °C en 10 minutos y la puerta siguió cerrada. Además hay
dos aperturas de puerta durante el día.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from logica import ZONA, a_ms

PASO_S = 60  # en la realidad publican cada 10 s; aquí cada minuto para no inflar la memoria


def _scores(etiquetas: list[str], ganadora: str, conf: float) -> dict:
    resto = (1 - conf) / (len(etiquetas) - 1)
    return {e: round(conf if e == ganadora else resto, 3) for e in etiquetas}


def generar(ahora: datetime | None = None, semilla: int = 7) -> list[dict]:
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(tz=ZONA)

    # el 2:14 a. m. más reciente que haya ocurrido hace más de 2 h
    incidente = ahora.replace(hour=2, minute=14, second=0, microsecond=0)
    if incidente > ahora - timedelta(hours=2):
        incidente -= timedelta(days=1)
    # aperturas recientes (la demo es de día): no caen en la noche del incidente
    aperturas = [(ahora - timedelta(hours=2), 6), (ahora - timedelta(minutes=50), 3)]

    items: list[dict] = []
    t = ahora - timedelta(hours=24)
    while t <= ahora:
        ts = a_ms(t)
        min_desde_incidente = (t - incidente).total_seconds() / 60

        # vibración: desbalanceada 25 min desde el incidente
        desbalance = 0 <= min_desde_incidente < 25
        label_v = "desbalanceado" if desbalance else "normal"
        conf_v = round(rnd.uniform(0.82, 0.95), 2)
        items.append({"device_id": "rack01-vibration", "ts": ts,
                      "accel_rms": round((0.45 if desbalance else 0.12) + rnd.uniform(-0.02, 0.02), 3),
                      "label": label_v, "confidence": conf_v,
                      "scores": _scores(["apagado", "normal", "desbalanceado"], label_v, conf_v)})

        # ambiente: ciclo diario suave + subida de 3 °C entre los min 4 y 14 del incidente
        temp = 23.0 + 0.8 * math.sin(2 * math.pi * t.hour / 24) + rnd.uniform(-0.1, 0.1)
        if 4 <= min_desde_incidente < 14:
            temp += 0.3 * (min_desde_incidente - 4)
        elif 14 <= min_desde_incidente < 40:
            temp += 3.0 * (1 - (min_desde_incidente - 14) / 26)
        falla = 6 <= min_desde_incidente < 30
        label_e = "falla_enfriamiento" if falla else "normal"
        conf_e = round(rnd.uniform(0.85, 0.96), 2)
        items.append({"device_id": "rack01-env", "ts": ts, "temperature": round(temp, 1),
                      "humidity": round(52 - (6 if falla else 0) + rnd.uniform(-1, 1), 1),
                      "label": label_e, "confidence": conf_e,
                      "scores": _scores(["normal", "falla_enfriamiento", "riesgo_condensacion"],
                                        label_e, conf_e)})

        # cámara
        abierta = any(ini <= t < ini + timedelta(minutes=dur) for ini, dur in aperturas)
        label_c = "puerta_abierta" if abierta else "puerta_cerrada"
        conf_c = round(rnd.uniform(0.9, 0.99), 2)
        items.append({"device_id": "rack01-camera", "ts": ts, "label": label_c,
                      "confidence": conf_c,
                      "scores": _scores(["puerta_cerrada", "puerta_abierta"], label_c, conf_c)})

        t += timedelta(seconds=PASO_S)
    return items
