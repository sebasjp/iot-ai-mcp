"""Reglas de alarma del Rack01 (sin AWS: se prueban en local con test_reglas.py).

La Lambda no tiene memoria entre ejecuciones: el historial sale de DynamoDB. Cada regla recibe el
mensaje actual y una función `historial(device_id, antes_de_ts, n)` que devuelve las últimas `n`
predicciones de ese dispositivo, de la más reciente a la más vieja.

Reglas (CLAUDE.md, sección Alarmas):
- Solo cuentan las predicciones con confianza >= UMBRAL; las inciertas se ignoran.
- env y vibration: alarma al llegar a 3 predicciones seguidas de la misma clase anómala.
  Suena una sola vez (en la 3.ª), no en la 4.ª, 5.ª...
- camera: alarma en cada transición de puerta_cerrada a puerta_abierta.
- Cruzadas, si la otra señal es anómala en los últimos VENTANA_CRUZADA_MS:
  vibración anómala + falla_enfriamiento -> falla de enfriamiento confirmada (alta);
  puerta_abierta + vibración anómala -> probable intervención de un técnico (info).
"""
from typing import Callable

UMBRAL = 0.6
SEGUIDAS = 3
VENTANA_CRUZADA_MS = 2 * 60 * 1000
HISTORIAL_N = 20  # cuántas predicciones previas se leen (incluye inciertas que se descartan)

ANOMALAS = {
    "rack01-env": {"falla_enfriamiento", "riesgo_condensacion"},
    "rack01-vibration": {"desbalanceado", "apagado"},
}

MODELO = {
    "rack01-env": "temperatura/humedad",
    "rack01-vibration": "vibración del ventilador",
    "rack01-camera": "imágenes (puerta)",
}

DESCRIPCION = {
    "falla_enfriamiento": "Posible falla de enfriamiento en el rack",
    "riesgo_condensacion": "Riesgo de condensación en el rack",
    "desbalanceado": "Ventilador desbalanceado, revisar",
    "apagado": "Ventilador apagado",
    "puerta_abierta": "Puerta del rack abierta",
}

Historial = Callable[[str, int, int], list[dict]]


def confiable(p: dict) -> bool:
    return float(p.get("confidence", 0)) >= UMBRAL


def _confiables(items: list[dict]) -> list[dict]:
    return [p for p in items if confiable(p)]


def _detalle(p: dict) -> str:
    return (f"Modelo: {MODELO.get(p['device_id'], p['device_id'])} ({p['device_id']})\n"
            f"Predicción: {p['label']} · confianza {float(p['confidence']) * 100:.0f} %")


def _alerta(p: dict, prioridad: str = "alta") -> dict:
    return {"texto": f"{DESCRIPCION.get(p['label'], p['label'])}\n{_detalle(p)}",
            "prioridad": prioridad, "ts": int(p["ts"])}


def ultima_confiable(device_id: str, ts: int, historial: Historial) -> dict | None:
    """Última predicción confiable de otro dispositivo dentro de la ventana cruzada."""
    for p in _confiables(historial(device_id, ts + 1, HISTORIAL_N)):
        return p if ts - int(p["ts"]) <= VENTANA_CRUZADA_MS else None
    return None


def entra_en_anomalia(actual: dict, historial: Historial) -> bool:
    """True si `actual` es la 3.ª predicción confiable seguida de la misma clase anómala."""
    etiqueta = actual["label"]
    if etiqueta not in ANOMALAS.get(actual["device_id"], set()) or not confiable(actual):
        return False
    previas = _confiables(historial(actual["device_id"], int(actual["ts"]), HISTORIAL_N))
    racha = [actual] + previas[:SEGUIDAS - 1]
    if len(racha) < SEGUIDAS or any(p["label"] != etiqueta for p in racha):
        return False
    # Suena solo al entrar: la anterior a la racha no puede ser de la misma clase
    siguiente = previas[SEGUIDAS - 1] if len(previas) >= SEGUIDAS else None
    return siguiente is None or siguiente["label"] != etiqueta


def puerta_se_abre(actual: dict, historial: Historial) -> bool:
    """True si la puerta pasa de cerrada a abierta (ambas predicciones confiables)."""
    if actual["label"] != "puerta_abierta" or not confiable(actual):
        return False
    previas = _confiables(historial(actual["device_id"], int(actual["ts"]), HISTORIAL_N))
    return bool(previas) and previas[0]["label"] == "puerta_cerrada"


def _vibracion_anomala(ts: int, historial: Historial) -> dict | None:
    p = ultima_confiable("rack01-vibration", ts, historial)
    return p if p and p["label"] in ANOMALAS["rack01-vibration"] else None


def evaluar(actual: dict, historial: Historial) -> list[dict]:
    """Devuelve las alertas que dispara el mensaje `actual` (puede ser una lista vacía)."""
    dispositivo, ts = actual["device_id"], int(actual["ts"])
    alertas = []

    if dispositivo == "rack01-camera" and puerta_se_abre(actual, historial):
        alertas.append(_alerta(actual))
        vib = _vibracion_anomala(ts, historial)
        if vib:
            alertas.append(_tecnico(actual, vib))

    elif dispositivo in ANOMALAS and entra_en_anomalia(actual, historial):
        alertas.append(_alerta(actual))
        if dispositivo == "rack01-env" and actual["label"] == "falla_enfriamiento":
            vib = _vibracion_anomala(ts, historial)
            if vib:
                alertas.append(_enfriamiento_confirmado(actual, vib))
        elif dispositivo == "rack01-vibration":
            env = ultima_confiable("rack01-env", ts, historial)
            if env and env["label"] == "falla_enfriamiento":
                alertas.append(_enfriamiento_confirmado(env, actual))
            cam = ultima_confiable("rack01-camera", ts, historial)
            if cam and cam["label"] == "puerta_abierta":
                alertas.append(_tecnico(cam, actual))

    return alertas


def _enfriamiento_confirmado(env: dict, vib: dict) -> dict:
    texto = ("Falla de enfriamiento CONFIRMADA: temperatura anómala y ventilador con problemas\n"
             f"{_detalle(env)}\n{_detalle(vib)}")
    return {"texto": texto, "prioridad": "alta", "ts": max(int(env["ts"]), int(vib["ts"]))}


def _tecnico(cam: dict, vib: dict) -> dict:
    texto = ("Puerta abierta y vibración anómala: probable intervención de un técnico\n"
             f"{_detalle(cam)}\n{_detalle(vib)}")
    return {"texto": texto, "prioridad": "info", "ts": max(int(cam["ts"]), int(vib["ts"]))}
