"""Cliente del modelo de Edge Impulse (.eim).

El .eim es un ejecutable que trae el modelo y su preprocesamiento. Se arranca con la ruta de un
socket Unix y responde mensajes JSON (protocolo del SDK de Edge Impulse para Linux):
  -> {"hello": 1, "id": 1}            <- parámetros del modelo (tamaño de imagen, etiquetas...)
  -> {"classify": [...], "id": 2}     <- probabilidades por clase y tiempos
Cada respuesta termina con un byte 0.

En la Pi (Raspbian Buster) el .eim pide glibc >= 2.34, así que se arranca con el cargador dinámico
de Bookworm y sus bibliotecas (carpeta EIM_LIBS). Ver docs/inconvenientes.md.
"""
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path


class ModeloEIM:
    def __init__(self, ruta_eim: str | Path, carpeta_libs: str | Path | None = None):
        self.ruta_eim = Path(ruta_eim).resolve()
        self.carpeta_libs = Path(carpeta_libs) if carpeta_libs else None
        self.ruta_socket = os.path.join(tempfile.gettempdir(), f"eim-{os.getpid()}.sock")
        self.proceso: subprocess.Popen | None = None
        self.conexion: socket.socket | None = None
        self.parametros: dict = {}
        self._id = 0

    # ---------- Ciclo de vida ----------
    def _comando(self) -> list[str]:
        if self.carpeta_libs is None:
            return [str(self.ruta_eim), self.ruta_socket]
        libs = self.carpeta_libs
        cargador = libs / "lib" / "ld-linux-armhf.so.3"
        rutas = f"{libs}/lib/arm-linux-gnueabihf:{libs}/usr/lib/arm-linux-gnueabihf"
        return [str(cargador), "--library-path", rutas, str(self.ruta_eim), self.ruta_socket]

    def iniciar(self, espera_max_s: float = 30) -> None:
        if not self.ruta_eim.exists():
            raise FileNotFoundError(f"No existe el modelo: {self.ruta_eim}")
        if os.path.exists(self.ruta_socket):
            os.unlink(self.ruta_socket)
        self.proceso = subprocess.Popen(self._comando(), stdout=subprocess.DEVNULL)
        self._esperar_socket(espera_max_s)
        self.conexion = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.conexion.connect(self.ruta_socket)
        self.parametros = self._enviar({"hello": 1})["model_parameters"]

    def _esperar_socket(self, espera_max_s: float) -> None:
        limite = time.monotonic() + espera_max_s
        while not os.path.exists(self.ruta_socket):
            if self.proceso.poll() is not None:
                raise RuntimeError(f"El .eim terminó al arrancar (código {self.proceso.returncode})")
            if time.monotonic() > limite:
                raise TimeoutError("El .eim no abrió su socket a tiempo")
            time.sleep(0.1)

    def detener(self) -> None:
        if self.conexion:
            self.conexion.close()
        if self.proceso and self.proceso.poll() is None:
            self.proceso.terminate()
            self.proceso.wait(timeout=5)
        if os.path.exists(self.ruta_socket):
            os.unlink(self.ruta_socket)

    def vivo(self) -> bool:
        return self.proceso is not None and self.proceso.poll() is None

    # ---------- Protocolo ----------
    def _enviar(self, mensaje: dict) -> dict:
        self._id += 1
        mensaje["id"] = self._id
        self.conexion.sendall(json.dumps(mensaje).encode("utf-8"))
        datos = b""
        while not datos.endswith(b"\x00"):
            trozo = self.conexion.recv(4096)
            if not trozo:
                raise ConnectionError("El .eim cerró la conexión")
            datos += trozo
        respuesta = json.loads(datos[:-1].decode("utf-8"))
        if not respuesta.get("success"):
            raise RuntimeError(f"Error del modelo: {respuesta.get('error')}")
        return respuesta

    # ---------- Datos del modelo ----------
    @property
    def ancho(self) -> int:
        return int(self.parametros["image_input_width"])

    @property
    def alto(self) -> int:
        return int(self.parametros["image_input_height"])

    @property
    def etiquetas(self) -> list[str]:
        return list(self.parametros["labels"])

    def memoria_kb(self) -> int | None:
        """RAM residente (VmRSS) del proceso del modelo, leída de /proc."""
        try:
            with open(f"/proc/{self.proceso.pid}/status") as f:
                for linea in f:
                    if linea.startswith("VmRSS:"):
                        return int(linea.split()[1])
        except (OSError, AttributeError):
            pass
        return None

    # ---------- Inferencia ----------
    def clasificar(self, rgb: bytes) -> dict:
        """Recibe los píxeles RGB (ancho x alto x 3 bytes) y devuelve scores y tiempos."""
        esperado = self.ancho * self.alto * 3
        if len(rgb) != esperado:
            raise ValueError(f"Se esperaban {esperado} bytes RGB y llegaron {len(rgb)}")
        # Edge Impulse espera cada píxel como un entero 0xRRGGBB
        pixeles = [int.from_bytes(rgb[i:i + 3], "big") for i in range(0, len(rgb), 3)]
        respuesta = self._enviar({"classify": pixeles})
        return {
            "scores": respuesta["result"]["classification"],
            "timing": respuesta.get("timing", {}),
        }
