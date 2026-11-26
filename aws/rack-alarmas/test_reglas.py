"""Prueba aislada de las reglas de alarma (sin AWS). Uso: python test_reglas.py"""
from reglas import evaluar


def p(device, ts, label, conf=0.9):
    return {"device_id": f"rack01-{device}", "ts": ts, "label": label, "confidence": conf}


def con_historial(*items):
    """Simula DynamoDB: devuelve las previas de un dispositivo, de la más nueva a la más vieja."""
    def historial(device_id, antes_de_ts, n):
        previas = [i for i in items if i["device_id"] == device_id and i["ts"] < antes_de_ts]
        return sorted(previas, key=lambda i: i["ts"], reverse=True)[:n]
    return historial


def test_puerta_cerrada_a_abierta_alerta():
    h = con_historial(p("camera", 1, "puerta_cerrada"))
    alertas = evaluar(p("camera", 2, "puerta_abierta", 0.95), h)
    assert len(alertas) == 1 and alertas[0]["prioridad"] == "alta"
    assert "Puerta del rack abierta" in alertas[0]["texto"] and "95 %" in alertas[0]["texto"]


def test_puerta_sigue_abierta_no_repite():
    h = con_historial(p("camera", 1, "puerta_cerrada"), p("camera", 2, "puerta_abierta"))
    assert evaluar(p("camera", 3, "puerta_abierta"), h) == []


def test_puerta_incierta_no_alerta_ni_cuenta():
    h = con_historial(p("camera", 1, "puerta_cerrada"))
    assert evaluar(p("camera", 2, "puerta_abierta", 0.55), h) == []
    # la incierta no cuenta como estado: la siguiente confiable sí es apertura
    h = con_historial(p("camera", 1, "puerta_cerrada"), p("camera", 2, "puerta_abierta", 0.55))
    assert len(evaluar(p("camera", 3, "puerta_abierta"), h)) == 1


def test_puerta_sin_historial_no_alerta():
    assert evaluar(p("camera", 1, "puerta_abierta"), con_historial()) == []


def test_env_tres_seguidas_alerta_una_vez():
    h = con_historial(p("env", 1, "normal"), p("env", 2, "falla_enfriamiento"),
                      p("env", 3, "falla_enfriamiento"))
    assert len(evaluar(p("env", 4, "falla_enfriamiento"), h)) == 1
    h = con_historial(p("env", 2, "falla_enfriamiento"), p("env", 3, "falla_enfriamiento"),
                      p("env", 4, "falla_enfriamiento"))
    assert evaluar(p("env", 5, "falla_enfriamiento"), h) == []  # la 4.ª no repite


def test_env_dos_seguidas_no_alerta():
    h = con_historial(p("env", 1, "normal"), p("env", 2, "falla_enfriamiento"))
    assert evaluar(p("env", 3, "falla_enfriamiento"), h) == []


def test_env_inciertas_no_rompen_ni_suman():
    h = con_historial(p("env", 1, "falla_enfriamiento"), p("env", 2, "normal", 0.4),
                      p("env", 3, "falla_enfriamiento"))
    assert len(evaluar(p("env", 4, "falla_enfriamiento"), h)) == 1


def test_clases_mezcladas_no_alertan():
    h = con_historial(p("vibration", 1, "apagado"), p("vibration", 2, "desbalanceado"))
    assert evaluar(p("vibration", 3, "desbalanceado"), h) == []


def test_normal_no_alerta():
    h = con_historial(p("env", 1, "normal"), p("env", 2, "normal"))
    assert evaluar(p("env", 3, "normal"), h) == []


def test_cruzada_enfriamiento_confirmado():
    h = con_historial(p("vibration", 1000, "desbalanceado"),
                      p("env", 1, "falla_enfriamiento"), p("env", 2, "falla_enfriamiento"))
    alertas = evaluar(p("env", 3000, "falla_enfriamiento"), h)
    assert len(alertas) == 2 and "CONFIRMADA" in alertas[1]["texto"]


def test_cruzada_fuera_de_ventana_no_alerta():
    h = con_historial(p("vibration", 1, "desbalanceado"),
                      p("env", 2, "falla_enfriamiento"), p("env", 3, "falla_enfriamiento"))
    alertas = evaluar(p("env", 10 * 60 * 1000, "falla_enfriamiento"), h)
    assert len(alertas) == 1  # la vibración es de hace 10 min


def test_cruzada_tecnico_es_info():
    h = con_historial(p("camera", 1, "puerta_cerrada"), p("vibration", 500, "apagado"))
    alertas = evaluar(p("camera", 1000, "puerta_abierta"), h)
    assert [a["prioridad"] for a in alertas] == ["alta", "info"]


def test_cruzadas_desde_vibracion():
    h = con_historial(p("env", 100, "falla_enfriamiento"), p("camera", 200, "puerta_abierta"),
                      p("vibration", 1, "desbalanceado"), p("vibration", 2, "desbalanceado"))
    alertas = evaluar(p("vibration", 300, "desbalanceado"), h)
    assert [a["prioridad"] for a in alertas] == ["alta", "alta", "info"]


if __name__ == "__main__":
    pruebas = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for prueba in pruebas:
        prueba()
        print(f"OK  {prueba.__name__}")
    print(f"\n{len(pruebas)} pruebas pasaron")
