"""Fuentes de imagen y preprocesamiento.

- FuenteCarpeta: recorre en orden las fotos de una carpeta (pruebas sin webcam).
- FuenteWebcam: toma una foto con fswebcam desde /dev/video0.
- preprocesar(): con ffmpeg decodifica la foto, escala el lado corto al tamaño del modelo y recorta el
  centro ("Fit shortest axis", igual que en el entrenamiento). Devuelve los píxeles RGB crudos.
  Se usa ffmpeg porque en la Pi (armv7, Python 3.12) no hay wheels de OpenCV ni de Pillow.
"""
import subprocess
from pathlib import Path

EXTENSIONES = {".jpg", ".jpeg", ".png"}


def preprocesar(ruta: Path, ancho: int, alto: int) -> bytes:
    filtro = (
        f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
        f"crop={ancho}:{alto}"
    )
    resultado = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-vf", filtro,
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True, timeout=30,
    )
    return resultado.stdout


class FuenteCarpeta:
    def __init__(self, carpeta: str | Path):
        self.fotos = sorted(p for p in Path(carpeta).iterdir() if p.suffix.lower() in EXTENSIONES)
        if not self.fotos:
            raise FileNotFoundError(f"No hay fotos en {carpeta}")
        self.indice = 0

    def capturar(self) -> Path:
        foto = self.fotos[self.indice % len(self.fotos)]
        self.indice += 1
        return foto


class FuenteWebcam:
    def __init__(self, dispositivo: str, destino: str | Path, saltar: int = 20):
        self.dispositivo = dispositivo
        self.destino = Path(destino)
        self.saltar = saltar

    def capturar(self) -> Path:
        self.destino.parent.mkdir(parents=True, exist_ok=True)
        self.destino.unlink(missing_ok=True)
        subprocess.run(
            ["fswebcam", "-q", "-d", self.dispositivo, "-r", "640x480",
             "-S", str(self.saltar), "--no-banner", "--jpeg", "90", str(self.destino)],
            check=True, timeout=30,
        )
        if not self.destino.exists():
            raise RuntimeError(f"fswebcam no generó la foto (¿está conectada {self.dispositivo}?)")
        return self.destino
