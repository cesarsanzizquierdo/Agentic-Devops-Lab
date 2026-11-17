"""Tests del contrato de contexto de la flotilla (agentes/flotilla/contrato.json y contrato.py)."""
import copy

import pytest

from agentes.flotilla.contrato import buscar_agente, cargar, principal, validar_contrato, validar_salida

CONTRATO = cargar()


def con_cambio(cambiar) -> dict:
    """Una copia del contrato real con un cambio: asi cada test rompe una sola cosa."""
    contrato = copy.deepcopy(CONTRATO)
    cambiar(contrato)
    return contrato


def agente(contrato: dict, ident: str) -> dict:
    return buscar_agente(contrato["agentes"], ident)


def test_el_contrato_real_es_valido():
    assert validar_contrato(CONTRATO) == []


def test_declara_los_tres_agentes_y_ninguno_escribe():
    identificadores = []
    for declarado in CONTRATO["agentes"]:
        identificadores.append(declarado["id"])
        assert declarado["escribe"] == []
    assert identificadores == ["conformidad-spec", "triaje-pipeline", "modernizacion-legado"]


def quitar_el_conflicto(contrato):
    del contrato["conflicto"]


def herramienta_que_no_existe(contrato):
    agente(contrato, "triaje-pipeline")["herramientas_mcp"].append("borrar_repositorio")


def agente_repetido(contrato):
    contrato["agentes"].append(copy.deepcopy(agente(contrato, "triaje-pipeline")))


def agente_que_escribe(contrato):
    agente(contrato, "modernizacion-legado")["escribe"] = ["src/aula/legado/"]


def handoff_de_un_desconocido(contrato):
    contrato["handoff"][0]["de"] = "agente-fantasma"


def handoff_con_un_campo_que_no_da(contrato):
    contrato["handoff"][0]["campos"].append("nota_media")


def handoff_con_una_condicion_imposible(contrato):
    contrato["handoff"][1]["cuando"] = {"campo": "color", "valores": ["rojo"]}


def prioridad_sin_modernizacion(contrato):
    contrato["conflicto"]["prioridad"] = ["triaje-pipeline"]


def regla_de_conflicto_incompleta(contrato):
    del contrato["conflicto"]["regla"]


@pytest.mark.parametrize("romper, error_esperado", [
    (quitar_el_conflicto, "al contrato le falta conflicto"),
    (herramienta_que_no_existe, "borrar_repositorio, que el servidor MCP no tiene"),
    (agente_repetido, "triaje-pipeline esta repetido"),
    (agente_que_escribe, "modernizacion-legado no puede escribir ficheros"),
    (handoff_de_un_desconocido, "agente-fantasma, que no es un agente del contrato"),
    (handoff_con_un_campo_que_no_da, "pasa nota_media, que no esta en su salida"),
    (handoff_con_una_condicion_imposible, 'el "cuando" del handoff de triaje-pipeline'),
    (prioridad_sin_modernizacion, "la prioridad debe nombrar una vez a cada agente"),
    (regla_de_conflicto_incompleta, "al apartado conflicto le falta regla"),
])
def test_el_validador_detecta_cada_forma_de_romper_el_contrato(romper, error_esperado):
    errores = validar_contrato(con_cambio(romper))

    assert len(errores) == 1
    assert error_esperado in errores[0]


def test_una_salida_con_todos_sus_campos_pasa():
    salida = {"agente": "triaje-pipeline", "raiz": "/tmp/x", "estado": "verde", "resumen": "1 passed",
              "fallos": [], "propone_tocar": []}

    assert validar_salida(CONTRATO, "triaje-pipeline", salida) == []


@pytest.mark.parametrize("salida, error_esperado", [
    ({"estado": "verde"}, "a la salida de triaje-pipeline le falta agente"),
    (["verde"], "no es un objeto JSON"),
])
def test_una_salida_incompleta_se_rechaza(salida, error_esperado):
    assert error_esperado in validar_salida(CONTRATO, "triaje-pipeline", salida)[0]


def test_la_linea_de_comandos_valida_el_contrato_real(capsys):
    assert principal() == 0
    assert "OK: contrato valido, 3 agentes" in capsys.readouterr().out
