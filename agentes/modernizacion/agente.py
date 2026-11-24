"""Agente de propuesta de modernizacion.

Lee modulos de Python y propone como modernizarlos sin romperlos. Solo lee: nunca ejecuta ni
modifica el codigo que analiza. Es determinista, sin modelo: cada hallazgo sale de una regla fija.

  sin_caracterizacion   modulo heredado (src/aula/legado/) que ningun test importa
  coma_flotante         float() o numeros con decimales dentro de una funcion (invariante 2)
  redondeo_intermedio   round() o quantize() dentro de un bucle: redondea antes de acumular
                        (invariante 1)
  numero_magico         constante numerica del modulo; si repite un parametro del plan vigente,
                        que pide al servidor MCP (version_plan), lo dice

Los pasos van en un orden fijo: si hay legado sin caracterizar, caracterizarlo va primero, antes
que cualquier cambio de codigo (regla dura de S5).

    python -m agentes.modernizacion.agente [--plan PLAN-2024] RUTA [RUTA ...]

Imprime su salida en JSON. Sale con 0 si emite la propuesta y con 3 si falla.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

from agentes.flotilla.mcp import consultar

AGENTE = "modernizacion-legado"
RAIZ = Path(__file__).resolve().parents[2]
FALLO_DEL_AGENTE = 3
CARPETA_LEGADO = "src/aula/legado/"
BATERIA_DE_CARACTERIZACION = "tests/test_caracterizacion_legado.py"
PARAMETROS_DEL_PLAN = ["creditos_titulo", "limite_creditos_curso", "max_convocatorias",
                       "umbral_final_carrera"]
BUCLES = (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

# Pasos en el orden en que se proponen, con el tipo de hallazgo que los activa.
PASOS = [
    ("no_analizable", "Revisar los ficheros que no se han podido analizar."),
    ("sin_caracterizacion", "Caracterizar el modulo heredado: escribir " + BATERIA_DE_CARACTERIZACION
     + " con su comportamiento actual y commitearla antes de tocar el codigo (regla dura de S5)."),
    ("coma_flotante", "Cambiar la coma flotante por Decimal (invariante 2)."),
    ("redondeo_intermedio", "Redondear una sola vez y al final (invariante 1)."),
    ("numero_magico", "Leer del plan las constantes que repiten sus parametros."),
]
# Hallazgos que piden cambiar el propio fichero.
CAMBIAN_EL_FICHERO = ["coma_flotante", "redondeo_intermedio", "numero_magico"]


def hallazgo(fichero: str, linea: int, tipo: str, detalle: str) -> dict:
    return {"fichero": fichero, "linea": linea, "tipo": tipo, "detalle": detalle}


def funciones_del_modulo(arbol: ast.Module) -> list:
    funciones = []
    for nodo in arbol.body:
        if isinstance(nodo, ast.FunctionDef):
            funciones.append(nodo)
    return funciones


def coma_flotante(ruta: str, arbol: ast.Module) -> list:
    hallazgos = []
    for funcion in funciones_del_modulo(arbol):
        lineas = []
        for nodo in ast.walk(funcion):
            es_llamada = (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
                          and nodo.func.id == "float")
            es_decimal = isinstance(nodo, ast.Constant) and type(nodo.value) is float
            if (es_llamada or es_decimal) and nodo.lineno not in lineas:
                lineas.append(nodo.lineno)
        if lineas:
            lineas.sort()
            hallazgos.append(hallazgo(ruta, lineas[0], "coma_flotante",
                                      "%s calcula con coma flotante" % funcion.name))
    return hallazgos


def redondeo_intermedio(ruta: str, arbol: ast.Module) -> list:
    hallazgos = []
    vistas = []
    for funcion in funciones_del_modulo(arbol):
        for bucle in ast.walk(funcion):
            if not isinstance(bucle, BUCLES):
                continue
            for nodo in ast.walk(bucle):
                if not isinstance(nodo, ast.Call):
                    continue
                es_round = isinstance(nodo.func, ast.Name) and nodo.func.id == "round"
                es_quantize = isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "quantize"
                if (es_round or es_quantize) and nodo.lineno not in vistas:
                    vistas.append(nodo.lineno)
                    hallazgos.append(hallazgo(ruta, nodo.lineno, "redondeo_intermedio",
                                              "%s redondea cada elemento dentro de un bucle"
                                              % funcion.name))
    return hallazgos


def numeros_magicos(ruta: str, arbol: ast.Module, plan: dict) -> list:
    hallazgos = []
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign) or len(nodo.targets) != 1:
            continue
        if not isinstance(nodo.targets[0], ast.Name) or not isinstance(nodo.value, ast.Constant):
            continue
        valor = nodo.value.value
        if type(valor) not in (int, float):
            continue     # bool tambien es int, pero DEBUG = False no es un numero magico
        nombre = nodo.targets[0].id
        detalle = "%s = %s es una constante fija en el codigo" % (nombre, valor)
        for parametro in PARAMETROS_DEL_PLAN:
            if plan.get(parametro) == valor:
                detalle = ("%s = %s repite %s de %s: si el plan cambia, el codigo no se entera"
                           % (nombre, valor, parametro, plan["codigo"]))
        hallazgos.append(hallazgo(ruta, nodo.lineno, "numero_magico", detalle))
    return hallazgos


def importa(fichero: Path, modulo: str) -> bool:
    """El fichero importa el modulo con una sentencia import (no basta con nombrarlo en un texto)."""
    try:
        arbol = ast.parse(fichero.read_bytes())
    except SyntaxError:
        return False
    for nodo in ast.walk(arbol):
        nombres = []
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            for alias in nodo.names:
                nombres.append(alias.name)
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.append(nodo.module)
        for nombre in nombres:
            if modulo in nombre.split("."):
                return True
    return False


def sin_caracterizacion(ruta: str) -> list:
    if not ruta.startswith(CARPETA_LEGADO):
        return []
    modulo = Path(ruta).stem
    for fichero in sorted((RAIZ / "tests").rglob("test_*.py")):
        if importa(fichero, modulo):
            return []
    return [hallazgo(ruta, 1, "sin_caracterizacion", "ningun test ejecuta este modulo heredado")]


def analizar(ruta: str, plan: dict) -> list:
    fichero = RAIZ / ruta
    if not fichero.is_file():
        return [hallazgo(ruta, 0, "no_analizable", "el fichero no existe")]
    try:
        # En bytes, Python respeta la cabecera de codificacion del legado, si la tiene.
        arbol = ast.parse(fichero.read_bytes())
    except SyntaxError as error:
        return [hallazgo(ruta, error.lineno or 0, "no_analizable", "no es Python valido: %s" % error)]

    hallazgos = []
    hallazgos.extend(sin_caracterizacion(ruta))
    hallazgos.extend(coma_flotante(ruta, arbol))
    hallazgos.extend(redondeo_intermedio(ruta, arbol))
    hallazgos.extend(numeros_magicos(ruta, arbol, plan))
    return hallazgos


def proponer(rutas_recibidas: list, codigo_de_plan: str) -> dict:
    rutas = []
    for ruta in rutas_recibidas:
        rutas.append(ruta.replace("\\", "/"))
    plan = consultar(AGENTE, "version_plan", {"codigo": codigo_de_plan})
    if "error" in plan:
        plan = {}     # sin plan, los numeros magicos se senalan sin compararlos

    hallazgos = []
    for ruta in rutas:
        hallazgos.extend(analizar(ruta, plan))

    tipos = []
    propone_tocar = []
    for encontrado in hallazgos:
        tipos.append(encontrado["tipo"])
        if encontrado["tipo"] in CAMBIAN_EL_FICHERO and encontrado["fichero"] not in propone_tocar:
            propone_tocar.append(encontrado["fichero"])
    if "sin_caracterizacion" in tipos:
        propone_tocar.append(BATERIA_DE_CARACTERIZACION)

    pasos = []
    for tipo, paso in PASOS:
        if tipo in tipos:
            pasos.append(paso)
    return {"agente": AGENTE, "raiz": str(RAIZ), "modulos": rutas, "hallazgos": hallazgos,
            "pasos": pasos, "propone_tocar": sorted(propone_tocar)}


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Agente de propuesta de modernizacion")
    parser.add_argument("rutas", nargs="+", help="modulos .py que analizar, relativos a la raiz")
    parser.add_argument("--plan", default="PLAN-2024", help="plan vigente con el que comparar")
    args = parser.parse_args(argv)
    try:
        salida = proponer(args.rutas, args.plan)
    except Exception as fallo:
        print("FALLO del agente de modernizacion: %s: %s" % (type(fallo).__name__, fallo),
              file=sys.stderr)
        return FALLO_DEL_AGENTE

    # En ASCII: la consola de Windows no siempre escribe UTF-8 y el JSON sigue siendo valido.
    print(json.dumps(salida, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
