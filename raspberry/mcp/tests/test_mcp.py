import asyncio
import importlib
import json
from datetime import datetime, timedelta
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

import datos_simulados
import logica
from repositorio import RepoDynamo, RepoMemoria

AHORA = datetime(2026, 11, 25, 10, 0, tzinfo=logica.ZONA)


@pytest.fixture
def repo():
    return RepoMemoria(datos_simulados.generar(AHORA))


def test_resumen_anoche_reproduce_ejemplo_demo(repo):
    r = logica.resumen(repo, AHORA, "2026-11-24T22:00", "2026-11-25T06:00")
    cambios = {(e["fuente"], e["cambio"]) for e in r["eventos"]}
    assert ("vibration", "normal -> desbalanceado") in cambios
    assert ("env", "normal -> falla_enfriamiento") in cambios
    assert r["camera"]["conteo_por_etiqueta"] == {"puerta_cerrada": r["camera"]["mensajes"]}
    assert r["hubo_anomalias"]
    vib = next(e for e in r["eventos"] if e["cambio"] == "normal -> desbalanceado")
    assert vib["hora_local"].endswith("02:14:00")
    env = next(e for e in r["eventos"] if e["cambio"] == "normal -> falla_enfriamiento")
    assert env["temperatura_en_evento"] > env["temperatura_10min_antes"]


def test_aperturas_con_duracion(repo):
    r = logica.prediccion_imagenes(repo, AHORA, horas=24)
    assert r["total_aperturas"] == 2
    assert [a["duracion_min"] for a in r["aperturas_ultimas_24h"]] == [6.0, 3.0]
    assert r["estado_actual"]["label"] == "puerta_cerrada"


def test_apertura_en_curso():
    t0 = logica.a_ms(AHORA - timedelta(minutes=5))
    items = [{"device_id": "rack01-camera", "ts": t0, "label": "puerta_cerrada"},
             {"device_id": "rack01-camera", "ts": t0 + 60_000, "label": "puerta_abierta"}]
    r = logica.prediccion_imagenes(RepoMemoria(items), AHORA)
    assert r["aperturas_ultimas_24h"][0]["nota"] == "sigue abierta"


def test_sensores_avisa_dato_viejo():
    viejo = logica.a_ms(AHORA - timedelta(minutes=30))
    items = [{"device_id": "rack01-env", "ts": viejo, "label": "normal",
              "temperature": 24.0, "humidity": 50.0, "confidence": 0.9}]
    r = logica.prediccion_sensores(RepoMemoria(items), AHORA)
    assert "advertencia" in r["env"]
    assert r["vibration"] == {"estado": "sin datos"}


def test_historico_muestrea_y_valida(repo):
    r = logica.historico(repo, AHORA, "env", "2026-11-24T10:00", max_registros=10)
    assert len(r["registros_muestreados"]) == 10
    assert r["estadisticas"]["mensajes"] > 1000
    with pytest.raises(ValueError):
        logica.historico(repo, AHORA, "env", "2026-11-25T10:00", "2026-11-25T09:00")
    with pytest.raises(ValueError):
        logica.historico(repo, AHORA, "otra", "2026-11-24T10:00")


@mock_aws
def test_repo_dynamo_ultimo_y_rango_convierte_decimal():
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    tabla = ddb.create_table(
        TableName="rack",
        KeySchema=[{"AttributeName": "device_id", "KeyType": "HASH"},
                   {"AttributeName": "ts", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "device_id", "AttributeType": "S"},
                              {"AttributeName": "ts", "AttributeType": "N"}],
        BillingMode="PAY_PER_REQUEST",
    )
    for i in range(5):
        tabla.put_item(Item={"device_id": "rack01-env", "ts": 1000 + i,
                             "temperature": Decimal("24.5"), "label": "normal",
                             "scores": {"normal": Decimal("0.9")}})
    tabla.put_item(Item={"device_id": "rack01-camera", "ts": 9999, "label": "puerta_abierta"})

    repo = RepoDynamo("rack", "us-east-1")
    ultimo = repo.ultimo("rack01-env")
    assert ultimo["ts"] == 1004 and isinstance(ultimo["ts"], int)
    assert ultimo["temperature"] == 24.5 and isinstance(ultimo["scores"]["normal"], float)
    assert [i["ts"] for i in repo.rango("rack01-env", 1001, 1003)] == [1001, 1002, 1003]
    assert repo.ultimo("rack01-vibration") is None


def test_servidor_expone_tools(monkeypatch):
    monkeypatch.setenv("MCP_DATOS", "simulado")
    import server

    importlib.reload(server)
    from fastmcp import Client

    async def run():
        async with Client(server.mcp) as c:
            nombres = {t.name for t in await c.list_tools()}
            res = await c.call_tool("consultar_prediccion_sensores", {})
            return nombres, res

    nombres, res = asyncio.run(run())
    assert nombres == {"hora_actual", "consultar_prediccion_imagenes",
                       "consultar_prediccion_sensores", "consultar_historico", "resumen_rack"}
    datos = res.data if res.data is not None else json.loads(res.content[0].text)
    assert datos["vibration"]["label"] in {"normal", "desbalanceado"}
