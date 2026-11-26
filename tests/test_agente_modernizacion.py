"""Tests del agente de propuesta de modernizacion (agentes/modernizacion/agente.py)."""
import ast
import json

from agentes.flotilla.contrato import cargar, validar_salida
from agentes.modernizacion import agente
from agentes.modernizacion.agente import (coma_flotante, numeros_magicos, principal, proponer,
                                          redondeo_intermedio, sin_caracterizacion)

LEGADO = "src/aula/legado/calculadora_expediente_v1.py"

VIEJO = """\
MAX_CONV = 6
DEC = 2
DEBUG = False

def media(notas):
    total = 0
    for nota in notas:
        total = total + round(float(nota), DEC)
    return total / len(notas)
"""


def tipos(hallazgos: list) -> list:
    encontrados = []
    for encontrado in hallazgos:
        encontrados.append(encontrado["tipo"])
    return encontrados


def test_detecta_la_coma_flotante_y_el_redondeo_dentro_del_bucle():
    arbol = ast.parse(VIEJO)

    assert tipos(coma_flotante("viejo.py", arbol)) == ["coma_flotante"]
    redondeos = redondeo_intermedio("viejo.py", arbol)
    assert tipos(redondeos) == ["redondeo_intermedio"]
    assert redondeos[0]["linea"] == 8


def test_una_constante_que_repite_el_plan_lo_dice_y_un_booleano_no_cuenta():
    plan = {"codigo": "PLAN-2024", "max_convocatorias": 6}

    hallazgos = numeros_magicos("viejo.py", ast.parse(VIEJO), plan)

    assert len(hallazgos) == 2     # MAX_CONV y DEC; DEBUG = False no
    assert "repite max_convocatorias de PLAN-2024" in hallazgos[0]["detalle"]
    assert "constante fija" in hallazgos[1]["detalle"]


def test_el_legado_sin_un_test_que_lo_importe_esta_sin_caracterizar(tmp_path, monkeypatch):
    monkeypatch.setattr(agente, "RAIZ", tmp_path)
    (tmp_path / "tests").mkdir()
    ruta = "src/aula/legado/viejo.py"

    assert tipos(sin_caracterizacion(ruta)) == ["sin_caracterizacion"]

    # Nombrarlo en un texto no lo ejecuta; importarlo si.
    (tmp_path / "tests/test_nombra.py").write_text('RUTA = "viejo"\n', encoding="utf-8")
    assert tipos(sin_caracterizacion(ruta)) == ["sin_caracterizacion"]
    (tmp_path / "tests/test_viejo.py").write_text("from aula.legado import viejo\n", encoding="utf-8")
    assert sin_caracterizacion(ruta) == []


def test_un_fichero_que_no_es_python_no_se_analiza(tmp_path, monkeypatch):
    monkeypatch.setattr(agente, "RAIZ", tmp_path)
    monkeypatch.setattr(agente, "consultar", lambda agente_que_pide, herramienta, argumentos: {})
    (tmp_path / "roto.py").write_text("def f(:\n", encoding="utf-8")

    salida = proponer(["roto.py"], "PLAN-2024")

    assert tipos(salida["hallazgos"]) == ["no_analizable"]
    assert salida["propone_tocar"] == []


def test_sobre_un_legado_sin_tests_caracterizar_va_primero(tmp_path, monkeypatch):
    monkeypatch.setattr(agente, "RAIZ", tmp_path)
    plan = {"codigo": "PLAN-2024", "max_convocatorias": 6}
    monkeypatch.setattr(agente, "consultar", lambda agente_que_pide, herramienta, argumentos: plan)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/aula/legado").mkdir(parents=True)
    (tmp_path / "src/aula/legado/viejo.py").write_text(VIEJO, encoding="utf-8")
    ruta = "src/aula/legado/viejo.py"

    salida = proponer([ruta], "PLAN-2024")

    encontrados = tipos(salida["hallazgos"])
    for esperado in ["sin_caracterizacion", "coma_flotante", "redondeo_intermedio", "numero_magico"]:
        assert esperado in encontrados
    assert salida["pasos"][0].startswith("Caracterizar el modulo heredado")
    assert salida["propone_tocar"] == [ruta, "tests/test_caracterizacion_legado.py"]
    assert validar_salida(cargar(), "modernizacion-legado", salida) == []


def test_el_legado_real_ya_esta_caracterizado():
    """Desde S5, tests/test_caracterizacion_legado.py importa el legado real."""
    salida = proponer([LEGADO], "PLAN-2024")

    assert "sin_caracterizacion" not in tipos(salida["hallazgos"])
    assert validar_salida(cargar(), "modernizacion-legado", salida) == []


def test_la_linea_de_comandos_imprime_json_y_si_falla_sale_con_3(monkeypatch, capsys):
    assert principal([LEGADO]) == 0
    assert json.loads(capsys.readouterr().out)["modulos"] == [LEGADO]

    def servidor_caido(agente_que_pide, herramienta, argumentos):
        raise ConnectionError("servidor caido")
    monkeypatch.setattr(agente, "consultar", servidor_caido)
    assert principal([LEGADO]) == 3
