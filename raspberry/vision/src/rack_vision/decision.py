"""Cuándo publicar y cuándo hubo una apertura de puerta.

Reglas (contrato de datos, CLAUDE.md):
- Se publica cada PUBLICAR_CADA_S segundos y de inmediato cuando cambia la etiqueta.
- Una predicción con confianza menor al umbral es "incierta": se publica en su turno, pero no cambia
  el estado (así una foto dudosa no dispara una apertura).
- Apertura = cambio confiable de puerta_cerrada a puerta_abierta.
"""


def ganadora(scores: dict[str, float]) -> tuple[str, float]:
    etiqueta = max(scores, key=scores.get)
    return etiqueta, float(scores[etiqueta])


class Decisor:
    def __init__(self, umbral: float, publicar_cada_s: float):
        self.umbral = umbral
        self.publicar_cada_s = publicar_cada_s
        self.estado: str | None = None  # última etiqueta confiable
        self.ultimo_envio: float | None = None

    def evaluar(self, etiqueta: str, confianza: float, ahora: float) -> tuple[bool, bool]:
        """Devuelve (publicar, hubo_apertura)."""
        cambio = confianza >= self.umbral and etiqueta != self.estado
        apertura = cambio and self.estado == "puerta_cerrada" and etiqueta == "puerta_abierta"
        if cambio:
            self.estado = etiqueta
        toca = self.ultimo_envio is None or ahora - self.ultimo_envio >= self.publicar_cada_s
        publicar = cambio or toca
        if publicar:
            self.ultimo_envio = ahora
        return publicar, apertura
