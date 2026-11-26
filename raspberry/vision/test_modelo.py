"""Prueba aislada del modelo en la Pi (sin MQTT ni AWS).

Clasifica las fotos que se le pasen y mide latencia y RAM reales para el README.
Uso (en la Pi, desde raspberry/vision):
    uv run python test_modelo.py imagenes_prueba/*.jpg
"""
import statistics
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import os  # noqa: E402

from rack_vision.decision import ganadora  # noqa: E402
from rack_vision.imagen import preprocesar  # noqa: E402
from rack_vision.modelo import ModeloEIM  # noqa: E402


def main(rutas: list[str]) -> None:
    if not rutas:
        raise SystemExit("Uso: uv run python test_modelo.py foto1.jpg foto2.jpg ...")
    base = Path(__file__).parent
    modelo = ModeloEIM(base / os.getenv("MODELO_EIM", "modelo/modelo-puerta.eim"),
                       os.getenv("EIM_LIBS") or None)
    t0 = time.perf_counter()
    modelo.iniciar()
    print(f"Modelo listo en {time.perf_counter() - t0:.1f} s · {modelo.ancho}x{modelo.alto} · "
          f"etiquetas {modelo.etiquetas}")

    t_modelo, t_total = [], []
    try:
        for ruta in rutas:
            inicio = time.perf_counter()
            rgb = preprocesar(Path(ruta), modelo.ancho, modelo.alto)
            r = modelo.clasificar(rgb)
            t_total.append((time.perf_counter() - inicio) * 1000)
            ms = int(r["timing"].get("dsp", 0)) + int(r["timing"].get("classification", 0))
            t_modelo.append(ms)
            etiqueta, conf = ganadora(r["scores"])
            print(f"{Path(ruta).name:45s} {etiqueta:15s} {conf:.3f}  modelo {ms} ms  "
                  f"total {t_total[-1]:.0f} ms")
        print("\n--- Resumen (para el README) ---")
        print(f"Fotos: {len(rutas)}")
        print(f"Inferencia (dsp + clasificación, reportada por el .eim): "
              f"media {statistics.mean(t_modelo):.0f} ms · máx {max(t_modelo)} ms")
        print(f"Ciclo completo (ffmpeg + JSON + inferencia): media {statistics.mean(t_total):.0f} ms")
        print(f"RAM del proceso del modelo (VmRSS): {modelo.memoria_kb()} kB")
    finally:
        modelo.detener()


if __name__ == "__main__":
    main(sys.argv[1:])
