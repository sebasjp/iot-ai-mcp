"""Lógica de las tools, separada de FastMCP para poder probarla sin servidor.

Todas las funciones reciben el repositorio y `ahora` (datetime con zona) para
que los tests sean deterministas.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from repositorio import Repositorio

ZONA = ZoneInfo("America/Bogota")

# Contrato 6.1 / 6.2 de la definición del proyecto
FUENTES = {
    "env": "rack01-env",
    "vibration": "rack01-vibration",
    "camera": "rack01-camera",
}
ETIQUETAS_ANOMALAS = {
    "env": {"falla_enfriamiento", "riesgo_condensacion"},
    "vibration": {"apagado", "desbalanceado"},
    "camera": {"puerta_abierta"},
}
# Si el último dato es más viejo que esto, se avisa que el dispositivo puede estar caído
# (publican cada 10 s).
SEGUNDOS_DATO_VIEJO = 120


# ---------- utilidades de tiempo ----------

def a_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def hora_local(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=ZONA).strftime("%Y-%m-%d %H:%M:%S")


def parsear_fecha(texto: str) -> datetime:
    """ISO 8601. Si no trae zona, se asume hora de Colombia."""
    dt = datetime.fromisoformat(texto.strip())
    return dt.replace(tzinfo=ZONA) if dt.tzinfo is None else dt


def _resolver_rango(desde: str, hasta: str | None, ahora: datetime) -> tuple[int, int]:
    d = parsear_fecha(desde)
    h = parsear_fecha(hasta) if hasta else ahora
    if d >= h:
        raise ValueError("'desde' debe ser anterior a 'hasta'")
    return a_ms(d), a_ms(h)


# ---------- formateo de registros ----------

def _registro(item: dict, ahora: datetime | None = None) -> dict:
    """Deja solo lo útil para el LLM y agrega la hora legible."""
    r = {"hora_local": hora_local(item["ts"]), "label": item.get("label"),
         "confidence": item.get("confidence")}
    for campo in ("temperature", "humidity", "accel_rms"):
        if campo in item:
            r[campo] = item[campo]
    if ahora is not None:
        edad = int((a_ms(ahora) - item["ts"]) / 1000)
        r["hace_segundos"] = edad
        if edad > SEGUNDOS_DATO_VIEJO:
            r["advertencia"] = (
                f"El último dato tiene {edad // 60} min: el dispositivo podría estar desconectado."
            )
    return r


def transiciones(items: list[dict]) -> list[dict]:
    """Cambios de etiqueta en orden cronológico (incluye el estado inicial)."""
    eventos, previa = [], None
    for it in sorted(items, key=lambda i: i["ts"]):
        if it.get("label") != previa:
            eventos.append({"hora_local": hora_local(it["ts"]), "ts": it["ts"],
                            "de": previa, "a": it.get("label")})
            previa = it.get("label")
    return eventos


def aperturas(items: list[dict], ahora: datetime) -> list[dict]:
    """Periodos de puerta abierta con su duración."""
    resultado, abierta_desde = [], None
    for ev in transiciones(items):
        if ev["a"] == "puerta_abierta":
            abierta_desde = ev["ts"]
        elif abierta_desde is not None:
            resultado.append({"abierta": hora_local(abierta_desde), "cerrada": ev["hora_local"],
                              "duracion_min": round((ev["ts"] - abierta_desde) / 60000, 1)})
            abierta_desde = None
    if abierta_desde is not None:
        resultado.append({"abierta": hora_local(abierta_desde), "cerrada": None,
                          "duracion_min": round((a_ms(ahora) - abierta_desde) / 60000, 1),
                          "nota": "sigue abierta"})
    return resultado


def _estadisticas(items: list[dict], fuente: str) -> dict:
    conteo: dict[str, int] = {}
    for it in items:
        conteo[it.get("label")] = conteo.get(it.get("label"), 0) + 1
    est: dict = {"mensajes": len(items), "conteo_por_etiqueta": conteo}
    campos = {"env": ("temperature", "humidity"), "vibration": ("accel_rms",)}.get(fuente, ())
    for campo in campos:
        valores = [it[campo] for it in items if campo in it]
        if valores:
            est[campo] = {"min": min(valores), "max": max(valores),
                          "promedio": round(sum(valores) / len(valores), 2)}
    return est


def _muestrear(items: list[dict], maximo: int) -> list[dict]:
    """Reduce la lista conservando primero, último y puntos repartidos."""
    if len(items) <= maximo:
        return items
    paso = (len(items) - 1) / (maximo - 1)
    return [items[round(i * paso)] for i in range(maximo)]


# ---------- tools ----------

def prediccion_imagenes(repo: Repositorio, ahora: datetime, horas: int = 24) -> dict:
    ultimo = repo.ultimo(FUENTES["camera"])
    if ultimo is None:
        return {"estado": "sin datos", "detalle": "No hay mensajes de la cámara en la base de datos."}
    items = repo.rango(FUENTES["camera"], a_ms(ahora) - horas * 3600_000, a_ms(ahora))
    lista = aperturas(items, ahora)
    return {
        "consultado_en": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "estado_actual": _registro(ultimo, ahora),
        f"aperturas_ultimas_{horas}h": lista,
        "total_aperturas": len(lista),
    }


def prediccion_sensores(repo: Repositorio, ahora: datetime) -> dict:
    respuesta: dict = {"consultado_en": ahora.strftime("%Y-%m-%d %H:%M:%S")}
    for fuente in ("env", "vibration"):
        ultimo = repo.ultimo(FUENTES[fuente])
        if ultimo is None:
            respuesta[fuente] = {"estado": "sin datos"}
            continue
        reg = _registro(ultimo, ahora)
        reg["anomalia"] = ultimo.get("label") in ETIQUETAS_ANOMALAS[fuente]
        respuesta[fuente] = reg
    return respuesta


def historico(repo: Repositorio, ahora: datetime, fuente: str, desde: str,
              hasta: str | None = None, max_registros: int = 60) -> dict:
    if fuente not in FUENTES:
        raise ValueError(f"fuente debe ser una de {list(FUENTES)}")
    d, h = _resolver_rango(desde, hasta, ahora)
    items = repo.rango(FUENTES[fuente], d, h)
    return {
        "fuente": fuente,
        "desde": hora_local(d),
        "hasta": hora_local(h),
        "estadisticas": _estadisticas(items, fuente),
        "cambios_de_etiqueta": [
            {k: v for k, v in ev.items() if k != "ts"} for ev in transiciones(items)
        ],
        "registros_muestreados": [_registro(i) for i in _muestrear(items, max_registros)],
    }


def resumen(repo: Repositorio, ahora: datetime, desde: str, hasta: str | None = None) -> dict:
    d, h = _resolver_rango(desde, hasta, ahora)
    resultado: dict = {"desde": hora_local(d), "hasta": hora_local(h), "eventos": []}
    for fuente, device in FUENTES.items():
        items = repo.rango(device, d, h)
        resultado[fuente] = _estadisticas(items, fuente)
        if not items:
            continue
        ordenados = sorted(items, key=lambda i: i["ts"])
        for ev in transiciones(items):
            if ev["de"] is None:  # el estado inicial no es un evento
                continue
            evento = {"hora_local": ev["hora_local"], "fuente": fuente,
                      "cambio": f"{ev['de']} -> {ev['a']}",
                      "anomalo": ev["a"] in ETIQUETAS_ANOMALAS[fuente]}
            if fuente == "env":  # contexto: temperatura 10 min antes y en el evento
                antes = [i for i in ordenados if ev["ts"] - 600_000 <= i["ts"] <= ev["ts"]]
                if antes and "temperature" in antes[0]:
                    evento["temperatura_10min_antes"] = antes[0]["temperature"]
                    evento["temperatura_en_evento"] = antes[-1]["temperature"]
            resultado["eventos"].append(evento)
    resultado["eventos"].sort(key=lambda e: e["hora_local"])
    resultado["hubo_anomalias"] = any(e["anomalo"] for e in resultado["eventos"])
    return resultado
