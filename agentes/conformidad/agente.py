"""Agente de conformidad de spec (v1).

Recibe un PR (sus ficheros y los criterios que declara implementar) y la spec que dice
implementar, y emite un veredicto estructurado: conforme o no_conforme, con los motivos.

El veredicto es DETERMINISTA: lo deciden reglas fijas sobre la spec, los ficheros del PR
y sus tests. No interviene ningun modelo, asi que el mismo PR da siempre el mismo
veredicto y sirve como gate. Las reglas salen de la checklist del PR:

  cobertura (punto 1)     cada criterio declarado tiene un test del PR con `cubre: SPEC/CA`
  alcance   (punto 4)     el PR solo toca las rutas que declara la spec
  riesgo    (puntos 3, 6) tests omitidos o sin asercion real; coma flotante en el codigo

Solo usa lo que tiene un PR real ("ficheros" y "criterios_declarados"); la spec la pide
al servidor MCP del proyecto, igual que cualquier otro agente.
"""
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agentes.mcp_aula.servidor import etiquetas_cubre, manejar

CONFORME = "conforme"
NO_CONFORME = "no_conforme"


@dataclass
class Veredicto:
    pr: str
    spec: str
    veredicto: str
    criterios_declarados: list = field(default_factory=list)
    criterios_cubiertos: list = field(default_factory=list)
    criterios_sin_cubrir: list = field(default_factory=list)
    fuera_de_alcance: list = field(default_factory=list)
    hallazgos: list = field(default_factory=list)
    explicacion: str = ""

    def a_dict(self):
        return asdict(self)


# --- contexto: la spec, pedida al servidor MCP ----------------------------------

def consultar_spec(spec_id: str) -> dict:
    """Pide la spec al servidor MCP: criterios, rutas y texto. Trae "error" si no existe."""
    respuesta = manejar({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                         "params": {"name": "obtener_spec", "arguments": {"id": spec_id}}})
    return json.loads(respuesta["result"]["content"][0]["text"])


# --- cobertura (checklist, punto 1) ----------------------------------------------

def ficheros_de_tests(pr: dict) -> list:
    """Los tests/test_*.py del PR: los que pytest ejecuta y la trazabilidad cuenta.

    Un `cubre:` en tests/conftest.py o tests/utilidades.py no es evidencia: nunca se ejecuta.
    """
    tests = []
    for fichero in pr["ficheros"]:
        nombre = fichero["ruta"].split("/")[-1]
        es_de_tests = fichero["ruta"].startswith("tests/")
        if es_de_tests and nombre.startswith("test_") and nombre.endswith(".py"):
            tests.append(fichero)
    return tests


def criterios_cubiertos(tests: list, spec_id: str) -> set:
    """Criterios de esta spec que algun test del PR declara con `cubre:` en su docstring."""
    prefijo = spec_id + "/"
    cubiertos = set()
    for fichero in tests:
        for clave in etiquetas_cubre(fichero["contenido"]):
            if clave.startswith(prefijo):
                cubiertos.add(clave[len(prefijo):])
    return cubiertos


# --- alcance (checklist, punto 4) ------------------------------------------------

def esta_en_alcance(ruta: str, rutas_de_la_spec: list) -> bool:
    for permitida in rutas_de_la_spec:
        if ruta == permitida:
            return True
        if permitida.endswith("/") and ruta.startswith(permitida):
            return True     # la spec declara una carpeta entera, por ejemplo src/aula/dominio/
    return False


# --- riesgo (checklist, puntos 3 y 6) --------------------------------------------

def es_marca_de_omision(decorador) -> bool:
    texto = ast.unparse(decorador)
    return "skip" in texto or "xfail" in texto


def solo_constantes(nodo) -> bool:
    """True si la expresion no depende de nada del programa: 1 + 1, "a", 2 > 1."""
    for parte in ast.walk(nodo):
        if isinstance(parte, (ast.Name, ast.Call, ast.Attribute, ast.Subscript)):
            return False
    return True


def es_asercion_vacia(asercion: ast.Assert) -> bool:
    """Una asercion que se cumple siempre y no comprueba nada.

    `assert True`, `assert 1 + 1 == 2` (solo constantes) o `assert x == x` (la misma
    variable). No lo es `assert f(e) == f(e)`: llama dos veces al codigo, y asi se
    comprueba precisamente que es determinista.
    """
    condicion = asercion.test
    if solo_constantes(condicion):
        return True
    if isinstance(condicion, ast.Compare) and len(condicion.comparators) == 1:
        izquierda, derecha = condicion.left, condicion.comparators[0]
        misma_variable = (isinstance(izquierda, ast.Name) and isinstance(derecha, ast.Name)
                          and izquierda.id == derecha.id)
        return misma_variable
    return False


def motivo_de_sospecha(test: ast.FunctionDef) -> str:
    """Devuelve por que el test es sospechoso, o "" si no lo es."""
    for decorador in test.decorator_list:
        if es_marca_de_omision(decorador):
            return "esta marcado para no ejecutarse (%s)" % ast.unparse(decorador)

    aserciones_reales = 0
    for nodo in ast.walk(test):
        if isinstance(nodo, ast.Call) and ast.unparse(nodo.func) in ("pytest.skip", "pytest.xfail"):
            return "se omite a si mismo (%s)" % ast.unparse(nodo.func)
        if isinstance(nodo, ast.Assert) and not es_asercion_vacia(nodo):
            aserciones_reales += 1
        if isinstance(nodo, ast.Call) and ast.unparse(nodo.func) == "pytest.raises":
            aserciones_reales += 1

    if aserciones_reales == 0:
        return "no tiene ninguna asercion que compruebe algo"
    return ""


def tests_sospechosos(tests: list) -> list:
    hallazgos = []
    for fichero in tests:
        try:
            arbol = ast.parse(fichero["contenido"])
        except SyntaxError:
            hallazgos.append("%s: el fichero de tests no es Python valido" % fichero["ruta"])
            continue
        for nodo in ast.walk(arbol):
            es_funcion = isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
            if es_funcion and nodo.name.startswith("test_"):
                motivo = motivo_de_sospecha(nodo)
                if motivo:
                    hallazgos.append("%s::%s %s" % (fichero["ruta"], nodo.name, motivo))
    return hallazgos


def riesgos_en_el_codigo(pr: dict) -> list:
    """Invariante 2 de CLAUDE.md: los calculos de nota y dinero usan Decimal, nunca float."""
    hallazgos = []
    for fichero in pr["ficheros"]:
        es_codigo = fichero["ruta"].startswith("src/") and fichero["ruta"].endswith(".py")
        if es_codigo and "float(" in fichero["contenido"]:
            hallazgos.append("%s usa float(): el invariante 2 exige Decimal" % fichero["ruta"])
    return hallazgos


# --- veredicto -------------------------------------------------------------------

def evaluar(pr: dict, spec_id: str, juez=None) -> Veredicto:
    """Aplica las reglas y decide. `juez` se ignora: el veredicto no lo decide un modelo."""
    declarados = list(pr.get("criterios_declarados", []))
    veredicto = Veredicto(pr=pr.get("id", "sin-id"), spec=spec_id, veredicto=CONFORME,
                          criterios_declarados=declarados)

    spec = consultar_spec(spec_id)
    if "error" in spec:
        veredicto.veredicto = NO_CONFORME
        veredicto.hallazgos.append(spec["error"])
        veredicto.explicacion = "no se puede comprobar un PR contra una spec que no existe"
        return veredicto

    if not declarados:
        veredicto.hallazgos.append("el PR no declara ningun criterio de la spec")
    for criterio in declarados:
        if criterio not in spec["criterios"]:
            veredicto.hallazgos.append("%s no existe en %s" % (criterio, spec_id))

    tests = ficheros_de_tests(pr)
    # spec["id"] viene en mayusculas del servidor: "--spec spec-002" tambien casa con SPEC-002/...
    cubiertos = criterios_cubiertos(tests, spec["id"])
    for criterio in declarados:
        if criterio in cubiertos:
            veredicto.criterios_cubiertos.append(criterio)
        else:
            veredicto.criterios_sin_cubrir.append(criterio)

    for fichero in pr["ficheros"]:
        if not esta_en_alcance(fichero["ruta"], spec["rutas"]):
            veredicto.fuera_de_alcance.append(fichero["ruta"])

    veredicto.hallazgos.extend(tests_sospechosos(tests))
    veredicto.hallazgos.extend(riesgos_en_el_codigo(pr))

    hay_motivos = (veredicto.criterios_sin_cubrir or veredicto.fuera_de_alcance
                   or veredicto.hallazgos)
    if hay_motivos:
        veredicto.veredicto = NO_CONFORME
    veredicto.explicacion = explicar(veredicto)
    return veredicto


def explicar(veredicto: Veredicto) -> str:
    """Redacta el veredicto con una plantilla fija, para que tambien sea reproducible."""
    if veredicto.veredicto == CONFORME:
        return "todos los criterios declarados tienen test y el PR no sale del alcance de la spec"
    partes = []
    if veredicto.criterios_sin_cubrir:
        partes.append("criterios sin test: %s" % ", ".join(veredicto.criterios_sin_cubrir))
    if veredicto.fuera_de_alcance:
        partes.append("fuera del alcance de la spec: %s" % ", ".join(veredicto.fuera_de_alcance))
    if veredicto.hallazgos:
        partes.append("hallazgos: %s" % "; ".join(veredicto.hallazgos))
    return ". ".join(partes)


def principal(argv=None):
    parser = argparse.ArgumentParser(description="Agente de conformidad de spec (v1)")
    parser.add_argument("--pr", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    entrada = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    veredicto = evaluar(entrada, args.spec)
    if args.json:
        print(json.dumps(veredicto.a_dict(), ensure_ascii=False, indent=2))
    else:
        print(veredicto.veredicto + ": " + veredicto.explicacion)
    return 1 if veredicto.veredicto == NO_CONFORME else 0


if __name__ == "__main__":
    raise SystemExit(principal())
