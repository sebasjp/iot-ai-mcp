"""Fotos guardadas en la Pi: la última de cada ciclo y una por cada apertura de puerta."""
import shutil
from datetime import datetime
from pathlib import Path


def guardar_ultima(origen: Path, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origen, carpeta / "ultima.jpg")


def guardar_apertura(origen: Path, carpeta: Path, ts_ms: int, maximo: int) -> Path:
    destino_dir = carpeta / "aperturas"
    destino_dir.mkdir(parents=True, exist_ok=True)
    nombre = datetime.fromtimestamp(ts_ms / 1000).strftime("%Y%m%d-%H%M%S") + origen.suffix.lower()
    destino = destino_dir / nombre
    shutil.copyfile(origen, destino)
    _podar(destino_dir, maximo)
    return destino


def _podar(carpeta: Path, maximo: int) -> None:
    """Borra las fotos más viejas si hay más de `maximo` (la SD es pequeña)."""
    fotos = sorted(carpeta.iterdir())
    for vieja in fotos[:-maximo] if len(fotos) > maximo else []:
        vieja.unlink()
