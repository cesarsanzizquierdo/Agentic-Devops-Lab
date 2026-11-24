"""Tests del agente de triaje de pipeline (agentes/triaje/agente.py)."""
import json

import pytest

from agentes.flotilla.contrato import buscar_agente, cargar, validar_salida
from agentes.triaje import agente
from agentes.triaje.agente import categoria, clave_de_trazabilidad, leer_linea, principal, triar

TEST_CA04 = "tests/test_media_expediente.py::test_spec002_ca04_punto_medio_half_up"
FALLO_CA04 = "FAILED %s - AssertionError: assert Decimal('7.00') == Decimal('7.01')" % TEST_CA04
FALLO_SIN_CUBRE = "FAILED tests/test_hooks.py::test_algo - AssertionError: assert 1 == 2"
FALLO_DE_ENTORNO = "ERROR tests/test_api_expediente.py - ModuleNotFoundError: No module named 'httpx'"


class ServidorFalso:
    """Respuestas fijas del servidor MCP. Apunta que herramientas pide el agente."""

    def __init__(self, resultado_tests):
        self.resultado_tests = resultado_tests
        self.pedidas = []

    def __call__(self, agente_que_pide, herramienta, argumentos):
        self.pedidas.append(herramienta)
        if herramienta == "resultado_tests":
            return self.resultado_tests
        if herramienta == "listar_specs":
            return {"specs": [{"id": "SPEC-002"}]}
        if herramienta == "trazabilidad":
            return {"cubiertos": {"CA-04": ["test_media_expediente.py::test_spec002_ca04_punto_medio_half_up"]}}
        if herramienta == "obtener_spec":
            return {"id": "SPEC-002", "rutas": ["src/aula/reglas/media.py", "src/aula/api/app.py",
                                                "tests/test_media_expediente.py"]}
        raise AssertionError("herramienta inesperada: %s" % herramienta)


def en_rojo(*lineas):
    return {"ok": False, "resumen": "%d failed" % len(lineas), "fallidos": list(lineas)}


def triar_con(monkeypatch, resultado_tests, cambiados):
    servidor = ServidorFalso(resultado_tests)
    monkeypatch.setattr(agente, "consultar", servidor)
    return triar("tests/", cambiados), servidor


def test_lee_las_lineas_de_resumen_de_pytest():
    assert leer_linea(FALLO_CA04) == {"tipo": "FAILED", "test": TEST_CA04,
                                      "mensaje": "AssertionError: assert Decimal('7.00') == Decimal('7.01')"}
    assert leer_linea(FALLO_DE_ENTORNO)["tipo"] == "ERROR"


@pytest.mark.parametrize("test, clave", [
    ("tests/test_media_expediente.py::test_a", "test_media_expediente.py::test_a"),
    ("tests/sub/test_x.py::Clase::test_b[caso-1]", "test_x.py::test_b"),
    ("tests\\test_x.py::test_c", "test_x.py::test_c"),
    ("tests/test_x.py", ""),    # error al recoger el fichero entero: no nombra ningun test
])
def test_normaliza_el_nombre_del_test_como_lo_da_trazabilidad(test, clave):
    assert clave_de_trazabilidad(test) == clave


@pytest.mark.parametrize("linea, criterios, esperada", [
    (FALLO_CA04, ["SPEC-002/CA-04"], "regresion"),
    ("FAILED " + TEST_CA04, ["SPEC-002/CA-04"], "regresion"),     # sin motivo: pytest lo recorto
    ("FAILED %s - FileNotFoundError: datos/planes" % TEST_CA04, ["SPEC-002/CA-04"], "error_de_entorno"),
    (FALLO_SIN_CUBRE, [], "sin_trazabilidad"),
    (FALLO_DE_ENTORNO, [], "error_de_entorno"),
    ("ERROR tests/test_x.py - SyntaxError: invalid syntax", [], "error_de_coleccion"),
])
def test_clasifica_cada_fallo(linea, criterios, esperada):
    assert categoria(leer_linea(linea), criterios) == esperada


def test_en_verde_no_propone_nada_ni_consulta_mas(monkeypatch):
    salida, servidor = triar_con(monkeypatch, {"ok": True, "resumen": "170 passed", "fallidos": []}, [])

    assert (salida["estado"], salida["propone_tocar"]) == ("verde", [])
    assert servidor.pedidas == ["resultado_tests"]


def test_si_pytest_no_llega_a_ejecutar_el_estado_es_no_ejecutado(monkeypatch):
    error = {"error": "pytest no ejecuto los tests (codigo 4): no se encuentra la ruta"}
    salida, _ = triar_con(monkeypatch, error, [])

    assert salida["estado"] == "no_ejecutado"
    assert salida["resumen"] == error["error"]


@pytest.mark.parametrize("cambiados, propone", [
    # El PR toca media.py y el test: se propone el codigo, nunca el test.
    (["src/aula/reglas/media.py", "tests/test_media_expediente.py"], ["src/aula/reglas/media.py"]),
    # Sin lista de cambiados: el codigo de src/ que declara la spec.
    ([], ["src/aula/api/app.py", "src/aula/reglas/media.py"]),
    # La causa esta fuera de las rutas de la spec: se propone lo que cambio, salvo tests y .md.
    (["datos/planes/PLAN-2024.json", "tests/test_media_expediente.py", "README.md"],
     ["datos/planes/PLAN-2024.json"]),
])
def test_una_regresion_senala_el_criterio_y_los_ficheros_que_mirar(monkeypatch, cambiados, propone):
    salida, _ = triar_con(monkeypatch, en_rojo(FALLO_CA04), cambiados)

    assert salida["estado"] == "rojo"
    assert salida["fallos"][0]["categoria"] == "regresion"
    assert salida["fallos"][0]["criterios"] == ["SPEC-002/CA-04"]
    assert salida["propone_tocar"] == propone


def test_sin_criterio_o_por_el_entorno_no_propone_tocar_nada(monkeypatch):
    salida, _ = triar_con(monkeypatch, en_rojo(FALLO_SIN_CUBRE, FALLO_DE_ENTORNO),
                          ["src/aula/reglas/media.py"])

    categorias = []
    for fallo in salida["fallos"]:
        categorias.append(fallo["categoria"])
    assert categorias == ["sin_trazabilidad", "error_de_entorno"]
    assert salida["propone_tocar"] == []


def test_la_salida_cumple_el_contrato_y_solo_usa_sus_herramientas(monkeypatch):
    contrato = cargar()
    salida, servidor = triar_con(monkeypatch, en_rojo(FALLO_CA04), [])

    assert validar_salida(contrato, "triaje-pipeline", salida) == []
    declaradas = buscar_agente(contrato["agentes"], "triaje-pipeline")["herramientas_mcp"]
    for herramienta in servidor.pedidas:
        assert herramienta in declaradas


def test_con_el_servidor_de_verdad_un_fichero_en_verde_da_verde():
    salida = triar("tests/test_subagentes.py", [])

    assert salida["estado"] == "verde"
    assert "passed" in salida["resumen"]


def test_la_linea_de_comandos_imprime_json_y_sale_con_el_codigo_del_estado(monkeypatch, capsys):
    rojo = en_rojo(FALLO_CA04)
    monkeypatch.setattr(agente, "consultar", ServidorFalso(rojo))

    codigo = principal(["--cambiados", "src/aula/reglas/media.py"])

    assert codigo == 1
    assert json.loads(capsys.readouterr().out)["propone_tocar"] == ["src/aula/reglas/media.py"]


def test_si_el_agente_falla_sale_con_un_codigo_que_el_contrato_no_declara(monkeypatch, capsys):
    def servidor_caido(agente_que_pide, herramienta, argumentos):
        raise ConnectionError("servidor caido")
    monkeypatch.setattr(agente, "consultar", servidor_caido)

    assert principal([]) == 3
    assert "FALLO del agente de triaje" in capsys.readouterr().err
