"""Servicio de visión: clasifica la puerta del rack cada CICLO_S segundos y publica en AWS IoT.

Ciclo: capturar foto -> preprocesar (ffmpeg) -> clasificar (.eim) -> decidir -> publicar o encolar
-> subir la foto a S3 (la última al publicar y la de cada apertura).
Tópico y payload: contrato de datos (datacenter/rack01/camera).
"""
import json
import os
import ssl
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from rack_vision.cola import ColaPendientes
from rack_vision.decision import Decisor, ganadora
from rack_vision.fotos import guardar_apertura, guardar_ultima
from rack_vision.imagen import FuenteCarpeta, FuenteWebcam, preprocesar
from rack_vision.modelo import ModeloEIM
from rack_vision.nube import SubidorFotos

# ---------- Configuración ----------
BASE = Path(__file__).resolve().parents[2]  # .../raspberry/vision
load_dotenv(BASE / ".env")

ENDPOINT = os.environ["AWS_IOT_ENDPOINT"]
CLIENT_ID = os.getenv("CLIENT_ID", "rack01-camera")
TOPIC = os.getenv("TOPIC", "datacenter/rack01/camera")
MODELO_EIM = BASE / os.getenv("MODELO_EIM", "modelo/modelo-puerta.eim")
EIM_LIBS = os.getenv("EIM_LIBS") or None
UMBRAL = float(os.getenv("UMBRAL_CONFIANZA", "0.6"))
FUENTE = os.getenv("FUENTE_IMAGEN", "carpeta")
CARPETA_IMAGENES = BASE / os.getenv("CARPETA_IMAGENES", "imagenes_prueba")
WEBCAM = os.getenv("WEBCAM", "/dev/video0")
WEBCAM_SALTAR = int(os.getenv("WEBCAM_SALTAR", "20"))
CICLO_S = float(os.getenv("CICLO_S", "5"))
PUBLICAR_CADA_S = float(os.getenv("PUBLICAR_CADA_S", "10"))
CARPETA_FOTOS = BASE / os.getenv("CARPETA_FOTOS", "fotos")
MAX_FOTOS = int(os.getenv("MAX_FOTOS_APERTURA", "200"))
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIJO = os.getenv("S3_PREFIJO", "rack01")

CERTS = BASE / "certs"
ETIQUETAS_CONTRATO = {"puerta_abierta", "puerta_cerrada"}

conectado = threading.Event()


# ---------- MQTT ----------
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[MQTT] Falló la conexión: {reason_code}")
        return
    print("[MQTT] Conectado a AWS IoT")
    conectado.set()


def on_disconnect(client, userdata, flags, reason_code, properties):
    conectado.clear()
    print(f"[MQTT] Desconectado ({reason_code}); paho reintenta solo")


def crear_cliente() -> mqtt.Client:
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
    cliente.tls_set(
        ca_certs=str(CERTS / "AmazonRootCA1.pem"),
        certfile=str(CERTS / "device.pem.crt"),
        keyfile=str(CERTS / "private.pem.key"),
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect
    cliente.reconnect_delay_set(min_delay=1, max_delay=60)
    return cliente


def publicar(cliente: mqtt.Client, cola: ColaPendientes, payload: str) -> None:
    """Publica si hay conexión; si no (o si falla), guarda en la cola local."""
    if conectado.is_set():
        info = cliente.publish(TOPIC, payload, qos=1)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            return
    cola.agregar(payload)
    print(f"[COLA] Sin conexión: mensaje guardado ({len(cola)} pendientes)")


def vaciar_cola(cliente: mqtt.Client, cola: ColaPendientes, maximo: int = 20) -> None:
    """Reenvía hasta `maximo` pendientes por ciclo, en orden."""
    for id_, payload in cola.primeros(maximo):
        if not conectado.is_set():
            return
        if cliente.publish(TOPIC, payload, qos=1).rc != mqtt.MQTT_ERR_SUCCESS:
            return
        cola.borrar(id_)
        print(f"[COLA] Reenviado pendiente {id_}")


# ---------- Ciclo de visión ----------
def crear_fuente():
    if FUENTE == "webcam":
        return FuenteWebcam(WEBCAM, CARPETA_FOTOS / "captura.jpg", WEBCAM_SALTAR)
    return FuenteCarpeta(CARPETA_IMAGENES)


def construir_payload(ts: int, scores: dict, timing: dict) -> dict:
    etiqueta, confianza = ganadora(scores)
    return {
        "device_id": CLIENT_ID,
        "ts": ts,
        "label": etiqueta,
        "confidence": round(confianza, 4),
        "scores": {k: round(float(v), 4) for k, v in scores.items()},
        "inference_ms": int(timing.get("dsp", 0)) + int(timing.get("classification", 0)),
    }


def ciclo(modelo, fuente, decisor, cliente, cola, nube) -> None:
    ts = int(time.time() * 1000)  # hora de la captura
    foto = fuente.capturar()
    rgb = preprocesar(foto, modelo.ancho, modelo.alto)
    resultado = modelo.clasificar(rgb)
    payload = construir_payload(ts, resultado["scores"], resultado["timing"])

    guardar_ultima(foto, CARPETA_FOTOS)
    hay_que_publicar, apertura = decisor.evaluar(payload["label"], payload["confidence"], time.monotonic())
    if apertura:
        destino = guardar_apertura(foto, CARPETA_FOTOS, ts, MAX_FOTOS)
        print(f"[APERTURA] Puerta abierta, foto en {destino}")
        clave = nube.subir_apertura(destino)
        if clave:
            payload["foto"] = clave  # campo opcional: el dashboard muestra la foto de la apertura

    print(f"[VISION] {foto.name}: {payload['label']} ({payload['confidence']:.2f}) "
          f"en {payload['inference_ms']} ms")
    if hay_que_publicar:
        publicar(cliente, cola, json.dumps(payload))
        nube.subir_ultima(foto)
    vaciar_cola(cliente, cola)


def iniciar_modelo() -> ModeloEIM:
    modelo = ModeloEIM(MODELO_EIM, EIM_LIBS)
    modelo.iniciar()
    etiquetas = set(modelo.etiquetas)
    if etiquetas != ETIQUETAS_CONTRATO:
        modelo.detener()
        raise SystemExit(f"Etiquetas del modelo {etiquetas} != contrato {ETIQUETAS_CONTRATO}")
    print(f"[MODELO] {MODELO_EIM.name}: {modelo.ancho}x{modelo.alto}, etiquetas {sorted(etiquetas)}")
    return modelo


def main() -> None:
    modelo = iniciar_modelo()
    fuente = crear_fuente()
    cola = ColaPendientes(BASE / "pendientes.db")
    decisor = Decisor(UMBRAL, PUBLICAR_CADA_S)
    nube = SubidorFotos(S3_BUCKET, S3_PREFIJO)
    cliente = crear_cliente()
    cliente.connect_async(ENDPOINT, 8883, keepalive=60)
    cliente.loop_start()  # hilo aparte: red, pings y reconexiones
    print(f"[VISION] Fuente: {FUENTE} · ciclo {CICLO_S} s · {len(cola)} pendientes en cola · "
          f"fotos a S3: {S3_BUCKET + '/' + S3_PREFIJO if nube.activo else 'desactivado'}")

    try:
        while True:
            inicio = time.monotonic()
            if not modelo.vivo():
                raise SystemExit("El proceso del modelo murió; systemd reinicia el servicio")
            try:
                ciclo(modelo, fuente, decisor, cliente, cola, nube)
            except Exception as e:  # una foto fallida no tumba el servicio
                print(f"[ERROR] Ciclo fallido: {e!r}")
            time.sleep(max(0.0, CICLO_S - (time.monotonic() - inicio)))
    except KeyboardInterrupt:
        print("Saliendo...")
    finally:
        cliente.loop_stop()
        cliente.disconnect()
        nube.cerrar()
        modelo.detener()


if __name__ == "__main__":
    main()
