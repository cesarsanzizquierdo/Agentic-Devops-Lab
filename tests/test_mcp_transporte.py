"""Tests del protocolo del servidor MCP (agentes/mcp_aula/servidor.py): manejar y principal.

Casi todos llaman a manejar() con el mismo JSON que enviaria un cliente MCP.
El ultimo lanza el servidor como proceso aparte, igual que Claude Code.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentes.mcp_aula.servidor import manejar

RAIZ = Path(__file__).resolve().parents[1]
SERVIDOR = RAIZ / "agentes" / "mcp_aula" / "servidor.py"


def peticion(metodo, parametros=None):
    """Mensaje JSON-RPC como lo enviaria un cliente MCP."""
    return {"jsonrpc": "2.0", "id": 1, "method": metodo, "params": parametros or {}}


def llamar_herramienta(nombre, argumentos):
    return manejar(peticion("tools/call", {"name": nombre, "arguments": argumentos}))


def test_initialize_anuncia_que_el_servidor_tiene_herramientas():
    respuesta = manejar(peticion("initialize"))

    assert respuesta["result"]["capabilities"] == {"tools": {}}
    assert respuesta["result"]["serverInfo"]["name"] == "aula-contexto"


def test_una_notificacion_no_tiene_respuesta():
    assert manejar({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_una_respuesta_del_cliente_no_se_contesta():
    assert manejar({"jsonrpc": "2.0", "id": 7, "result": {}}) is None


def test_ping_devuelve_un_resultado_vacio():
    assert manejar(peticion("ping"))["result"] == {}


def test_tools_list_devuelve_las_cinco_herramientas_del_enunciado():
    respuesta = manejar(peticion("tools/list"))

    nombres = set()
    for herramienta in respuesta["result"]["tools"]:
        nombres.add(herramienta["name"])
    assert nombres == {"listar_specs", "obtener_spec", "trazabilidad",
                       "resultado_tests", "version_plan"}


def test_metodo_desconocido_da_error_32601():
    assert manejar(peticion("borrar_todo"))["error"]["code"] == -32601


@pytest.mark.parametrize("mensaje", [
    {"id": 1, "method": "ping"},                     # falta "jsonrpc": "2.0"
    {"jsonrpc": "2.0", "id": 1, "method": 42},       # method no es texto
])
def test_peticion_mal_formada_da_error_32600(mensaje):
    assert manejar(mensaje)["error"]["code"] == -32600


def test_herramienta_desconocida_da_error_32602():
    assert llamar_herramienta("borrar_todo", {})["error"]["code"] == -32602


def test_falta_un_argumento_obligatorio_da_error_32602_y_lo_nombra():
    respuesta = llamar_herramienta("obtener_spec", {})

    assert respuesta["error"]["code"] == -32602
    assert respuesta["error"]["message"] == "faltan argumentos para obtener_spec: id"


@pytest.mark.parametrize("parametros", [
    ["obtener_spec"],                                # params no es un objeto
    {"name": ["obtener_spec"], "arguments": {}},     # name no es texto
    {"name": "obtener_spec", "arguments": 5},        # arguments no es un objeto
])
def test_parametros_con_tipos_erroneos_dan_error_32602(parametros):
    assert manejar(peticion("tools/call", parametros))["error"]["code"] == -32602


def test_si_la_herramienta_falla_se_devuelve_is_error_con_el_motivo():
    # obtener_spec hace id.upper(): con un numero lanza AttributeError dentro de la herramienta.
    respuesta = llamar_herramienta("obtener_spec", {"id": 5})

    assert respuesta["result"]["isError"] is True
    assert "AttributeError" in respuesta["result"]["content"][0]["text"]


def test_si_la_herramienta_devuelve_error_se_marca_is_error():
    respuesta = llamar_herramienta("obtener_spec", {"id": "SPEC-999"})

    assert respuesta["result"]["isError"] is True
    assert "no encontrada" in respuesta["result"]["content"][0]["text"]


def test_proceso_stdio_contesta_cada_peticion_y_sobrevive_a_entradas_rotas(tmp_path):
    lineas = [
        json.dumps(peticion("initialize")),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        "esto no es json",
        "[1, 2]",
        json.dumps(peticion("tools/call", {"name": "obtener_spec", "arguments": 5})),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    ]

    # cwd=tmp_path: el servidor no debe depender de arrancar en la raiz del proyecto.
    proceso = subprocess.run([sys.executable, str(SERVIDOR)], input="\n".join(lineas) + "\n",
                             capture_output=True, text=True, cwd=tmp_path, timeout=60)

    respuestas = []
    for linea in proceso.stdout.splitlines():
        respuestas.append(json.loads(linea))
    # 6 lineas y 5 respuestas: la notificacion no se contesta.
    assert len(respuestas) == 5
    assert respuestas[0]["id"] == 1
    assert respuestas[1]["error"]["code"] == -32700
    assert respuestas[2]["error"]["code"] == -32600
    assert respuestas[3]["error"]["code"] == -32602
    # Tras las entradas rotas el servidor sigue vivo y contesta.
    assert len(respuestas[4]["result"]["tools"]) == 5
