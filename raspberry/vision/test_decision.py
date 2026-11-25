"""Prueba aislada de las reglas de publicación y apertura (corre en cualquier PC).

Uso: uv run python test_decision.py
"""
from rack_vision.decision import Decisor, ganadora


def test_ganadora():
    assert ganadora({"puerta_abierta": 0.2, "puerta_cerrada": 0.8}) == ("puerta_cerrada", 0.8)


def test_publica_al_inicio_y_cada_10_s():
    d = Decisor(umbral=0.6, publicar_cada_s=10)
    assert d.evaluar("puerta_cerrada", 0.9, ahora=0) == (True, False)   # primer mensaje
    assert d.evaluar("puerta_cerrada", 0.9, ahora=5) == (False, False)  # sin cambio, no toca
    assert d.evaluar("puerta_cerrada", 0.9, ahora=10) == (True, False)  # toca por tiempo


def test_apertura_publica_de_inmediato():
    d = Decisor(umbral=0.6, publicar_cada_s=10)
    d.evaluar("puerta_cerrada", 0.9, ahora=0)
    assert d.evaluar("puerta_abierta", 0.95, ahora=5) == (True, True)
    assert d.evaluar("puerta_abierta", 0.95, ahora=6) == (False, False)  # sigue abierta: no repite


def test_prediccion_incierta_no_es_apertura():
    d = Decisor(umbral=0.6, publicar_cada_s=10)
    d.evaluar("puerta_cerrada", 0.9, ahora=0)
    assert d.evaluar("puerta_abierta", 0.55, ahora=5) == (False, False)
    assert d.estado == "puerta_cerrada"


def test_arranque_con_puerta_abierta_no_es_apertura():
    d = Decisor(umbral=0.6, publicar_cada_s=10)
    assert d.evaluar("puerta_abierta", 0.9, ahora=0) == (True, False)


def test_cierre_y_nueva_apertura():
    d = Decisor(umbral=0.6, publicar_cada_s=10)
    d.evaluar("puerta_cerrada", 0.9, ahora=0)
    d.evaluar("puerta_abierta", 0.9, ahora=5)
    assert d.evaluar("puerta_cerrada", 0.9, ahora=6) == (True, False)
    assert d.evaluar("puerta_abierta", 0.9, ahora=7) == (True, True)


if __name__ == "__main__":
    pruebas = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for prueba in pruebas:
        prueba()
        print(f"OK  {prueba.__name__}")
    print(f"\n{len(pruebas)} pruebas pasaron")
