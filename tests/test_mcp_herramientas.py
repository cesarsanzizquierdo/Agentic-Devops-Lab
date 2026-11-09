"""Tests de lo que responde cada herramienta del servidor MCP (agentes/mcp_aula/servidor.py)."""
import json
import os
import subprocess
import sys

import pytest

from agentes.mcp_aula import servidor
from agentes.mcp_aula.servidor import manejar, resultado_tests


def llamar_herramienta(nombre, argumentos):
    """Simula un tools/call de un cliente MCP y devuelve la respuesta completa."""
    return manejar({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": nombre, "arguments": argumentos}})


def datos_de(respuesta):
    """Extrae el JSON que la herramienta devuelve dentro del bloque de texto."""
    return json.loads(respuesta["result"]["content"][0]["text"])


def pytest_simulado(monkeypatch, codigo, salida="", errores=""):
    """Sustituye la ejecucion real de pytest por un resultado inventado."""
    def ejecutar(comando, **opciones):
        return subprocess.CompletedProcess(comando, codigo, stdout=salida, stderr=errores)
    monkeypatch.setattr(servidor.subprocess, "run", ejecutar)


def test_obtener_spec_devuelve_sus_criterios():
    datos = datos_de(llamar_herramienta("obtener_spec", {"id": "SPEC-002"}))
    assert "CA-08" in datos["criterios"]


def test_obtener_spec_devuelve_las_rutas_de_su_alcance():
    datos = datos_de(llamar_herramienta("obtener_spec", {"id": "SPEC-001"}))
    assert datos["rutas"] == ["src/aula/reglas/motor.py", "src/aula/dominio/",
                              "tests/test_reglas_matricula.py", "specs/SPEC-001-matricula.md"]


def test_trazabilidad_pone_cada_criterio_en_cubiertos_o_en_sin_cubrir():
    datos = datos_de(llamar_herramienta("trazabilidad", {"spec_id": "SPEC-002"}))
    criterios = datos_de(llamar_herramienta("obtener_spec", {"id": "SPEC-002"}))["criterios"]

    # CA-01 tiene tests propios en tests/test_media_expediente.py.
    assert "CA-01" in datos["cubiertos"]
    assert sorted(list(datos["cubiertos"]) + datos["sin_cubrir"]) == criterios


def test_version_plan_devuelve_la_version_y_los_parametros_del_plan():
    datos = datos_de(llamar_herramienta("version_plan", {"codigo": "PLAN-2024"}))

    assert datos == {
        "codigo": "PLAN-2024",
        "version": "1.2.0",
        "creditos_titulo": 192,
        "limite_creditos_curso": 60,
        "max_convocatorias": 6,
        "umbral_final_carrera": 12,
        "asignaturas": 30,
    }


@pytest.mark.parametrize("codigo", ["../specs/SPEC-001", "PLAN-2024.json", "PLAN-24"])
def test_version_plan_rechaza_codigos_que_no_son_de_plan(codigo):
    respuesta = llamar_herramienta("version_plan", {"codigo": codigo})

    assert respuesta["result"]["isError"] is True
    assert "no valido" in datos_de(respuesta)["error"]


def test_version_plan_de_un_plan_que_no_existe():
    respuesta = llamar_herramienta("version_plan", {"codigo": "PLAN-1999"})

    assert respuesta["result"]["isError"] is True
    assert "no encontrado" in datos_de(respuesta)["error"]


@pytest.mark.parametrize("ruta", [
    "src/",                 # fuera de tests/
    "tests/../src",         # rodeo para salir de tests/
    "..\\src",              # rodeo con barras de Windows
    "C:/Windows",           # ruta absoluta de Windows
    "/etc",                 # ruta absoluta de Unix
    "-p malicioso",         # pytest lo tomaria como una opcion
])
def test_resultado_tests_rechaza_rutas_fuera_de_tests(ruta):
    assert "ruta no permitida" in resultado_tests({"ruta": ruta})["error"]


def crear_enlace_a_carpeta(enlace, destino):
    """Enlace simbolico; en Windows sin permisos, una junction (no los necesita)."""
    try:
        os.symlink(destino, enlace, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        import _winapi
        _winapi.CreateJunction(str(destino), str(enlace))


def test_resultado_tests_rechaza_un_enlace_que_sale_de_tests(monkeypatch, tmp_path):
    # El texto "tests/enlace" pasa la primera barrera; la ruta real en disco ya no esta en tests/.
    monkeypatch.setattr(servidor, "RAIZ", tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "fuera").mkdir()
    crear_enlace_a_carpeta(tmp_path / "tests" / "enlace", tmp_path / "fuera")

    assert servidor.ruta_de_tests_permitida("tests/enlace") is False
    assert servidor.ruta_de_tests_permitida("tests/test_x.py::test_a") is True


def test_resultado_tests_ejecuta_un_fichero_de_la_suite():
    # Un fichero pequeno y rapido: ejecutar la suite entera desde un test la repetiria.
    resultado = resultado_tests({"ruta": "tests/test_subagentes.py"})

    assert resultado["ok"] is True
    assert resultado["fallidos"] == []
    assert "passed" in resultado["resumen"]


def test_resultado_tests_explica_por_que_no_se_ejecuto_una_ruta_inexistente():
    resultado = resultado_tests({"ruta": "tests/no_existe.py"})

    assert "codigo 4" in resultado["error"]
    assert "no_existe.py" in resultado["error"]


def test_resultado_tests_avisa_si_este_python_no_tiene_pytest(monkeypatch):
    # Sale con codigo 1, como cuando falla un test, pero no ha ejecutado ninguno.
    pytest_simulado(monkeypatch, codigo=1, errores="No module named pytest")

    resultado = resultado_tests({"ruta": "tests/"})

    assert "No module named pytest" in resultado["error"]


def test_resultado_tests_no_comparte_la_entrada_del_servidor_con_pytest(monkeypatch):
    # Por stdin llegan los mensajes MCP: pytest no debe heredarlo.
    recibidas = {}

    def ejecutar(comando, **opciones):
        recibidas.update(opciones)
        return subprocess.CompletedProcess(comando, 0, stdout="1 passed in 0.01s", stderr="")
    monkeypatch.setattr(servidor.subprocess, "run", ejecutar)

    resultado_tests({"ruta": "tests/"})

    assert recibidas["stdin"] is subprocess.DEVNULL


def test_resultado_tests_lista_los_tests_que_fallan(monkeypatch):
    salida = ("F.\n"
              "FAILED tests/test_x.py::test_a - assert 1 == 2\n"
              "1 failed, 1 passed in 0.01s\n")
    pytest_simulado(monkeypatch, codigo=1, salida=salida)

    resultado = resultado_tests({"ruta": "tests/"})

    assert resultado["ok"] is False
    assert resultado["fallidos"] == ["FAILED tests/test_x.py::test_a - assert 1 == 2"]
    assert resultado["resumen"] == "1 failed, 1 passed in 0.01s"


def test_resultado_tests_corta_si_se_agota_el_tiempo(monkeypatch):
    def tarda_demasiado(comando, **opciones):
        raise subprocess.TimeoutExpired(comando, opciones["timeout"])
    monkeypatch.setattr(servidor.subprocess, "run", tarda_demasiado)

    assert "tiempo agotado" in resultado_tests({"ruta": "tests/"})["error"]
