"""Agente de triaje de pipeline.

Ejecuta los tests y, si fallan, dice que ha fallado, de que criterio es cada fallo y que ficheros
hay que mirar. Es determinista, sin modelo: reglas fijas sobre la salida de pytest y la
trazabilidad de las specs. Todo lo pide al servidor MCP a traves de consultar(), que solo le deja
usar las herramientas que su contrato declara.

Categorias de un fallo:
  regresion            falla un test que cubre un criterio (`cubre:`): se ha roto lo que pide la spec
  sin_trazabilidad     falla un test que no cubre ningun criterio: lo decide el humano
  error_de_entorno     falta un modulo, un fichero o un permiso: el fallo no es del codigo
  error_de_coleccion   pytest no pudo recoger un fichero de tests o preparar un test

Solo propone tocar ficheros en las regresiones, que es cuando sabe a que spec pertenece el fallo.
Y nunca propone tocar un test: cambiar el test para que pase es justo lo que no hay que hacer.

    python -m agentes.triaje.agente [--ruta tests/] [--cambiados RUTA ...]

Imprime su salida en JSON. Sale con 0 en verde, 1 en rojo y 2 si pytest no llego a ejecutar los
tests. Si falla el propio agente sale con 3, un codigo que el contrato no declara.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentes.flotilla.mcp import consultar

AGENTE = "triaje-pipeline"
RAIZ = Path(__file__).resolve().parents[2]
CODIGOS_DE_SALIDA = {"verde": 0, "rojo": 1, "no_ejecutado": 2}
FALLO_DEL_AGENTE = 3

# Si el mensaje del fallo nombra uno de estos errores, la causa es el entorno, no el codigo.
ERRORES_DE_ENTORNO = ["ModuleNotFoundError", "ImportError", "FileNotFoundError", "PermissionError"]


def leer_linea(linea: str) -> dict:
    """De "FAILED tests/x.py::test_a - AssertionError: ..." saca el tipo, el test y el mensaje."""
    tipo, _, resto = linea.partition(" ")
    test, _, mensaje = resto.partition(" - ")
    return {"tipo": tipo, "test": test.strip(), "mensaje": mensaje.strip()}


def clave_de_trazabilidad(test: str) -> str:
    """Nombre del test como lo da `trazabilidad`: "tests/x.py::Clase::test_a[p]" -> "x.py::test_a".

    Devuelve "" si la linea no nombra un test, como en un error al recoger un fichero entero.
    """
    partes = test.split("::")
    if len(partes) < 2:
        return ""
    fichero = partes[0].replace("\\", "/").split("/")[-1]
    nombre = partes[-1].split("[")[0]
    return "%s::%s" % (fichero, nombre)


def categoria(fallo: dict, criterios: list) -> str:
    for error in ERRORES_DE_ENTORNO:
        if error in fallo["mensaje"]:
            return "error_de_entorno"
    if fallo["tipo"] == "ERROR":
        return "error_de_coleccion"
    if criterios:
        return "regresion"
    return "sin_trazabilidad"


def criterios_por_test() -> dict:
    """{"x.py::test_a": ["SPEC-002/CA-04"]}: la trazabilidad de todas las specs, al reves."""
    mapa = {}
    for spec in consultar(AGENTE, "listar_specs", {})["specs"]:
        trazabilidad = consultar(AGENTE, "trazabilidad", {"spec_id": spec["id"]})
        if "error" in trazabilidad:
            continue
        for criterio, tests in trazabilidad["cubiertos"].items():
            for test in tests:
                mapa.setdefault(test, []).append("%s/%s" % (spec["id"], criterio))
    return mapa


def rutas_de_codigo(spec_id: str) -> list:
    """Las rutas de src/ que declara la spec: el codigo que implementa sus criterios."""
    spec = consultar(AGENTE, "obtener_spec", {"id": spec_id})
    rutas = []
    for ruta in spec.get("rutas", []):
        if ruta.startswith("src/"):
            rutas.append(ruta)
    return rutas


def pertenece(ruta: str, rutas_de_la_spec: list) -> bool:
    for permitida in rutas_de_la_spec:
        if ruta == permitida:
            return True
        if permitida.endswith("/") and ruta.startswith(permitida):
            return True     # la spec declara una carpeta entera, como src/aula/dominio/
    return False


def sospechosos(criterios: list, cambiados: list) -> list:
    """Ficheros que mirar para una regresion de estos criterios.

    Sin la lista de cambiados: el codigo de src/ que declaran sus specs. Con ella: los cambiados
    que estan en esas rutas y, si no hay ninguno, todos los cambiados, porque la causa puede
    estar fuera de las rutas (por ejemplo, en un plan de datos). Nunca un test ni un .md.
    """
    rutas_de_las_specs = []
    for criterio in criterios:
        spec_id = criterio.split("/")[0]
        for ruta in rutas_de_codigo(spec_id):
            if ruta not in rutas_de_las_specs:
                rutas_de_las_specs.append(ruta)
    if not cambiados:
        return rutas_de_las_specs

    codigo_cambiado = []
    for ruta in cambiados:
        if not ruta.startswith("tests/") and not ruta.endswith(".md"):
            codigo_cambiado.append(ruta)
    en_las_rutas = []
    for ruta in codigo_cambiado:
        if pertenece(ruta, rutas_de_las_specs):
            en_las_rutas.append(ruta)
    if en_las_rutas:
        return en_las_rutas
    return codigo_cambiado


def triar(ruta_de_tests: str, cambiados: list) -> dict:
    salida = {"agente": AGENTE, "raiz": str(RAIZ), "estado": "", "resumen": "", "fallos": [],
              "propone_tocar": []}
    resultado = consultar(AGENTE, "resultado_tests", {"ruta": ruta_de_tests})
    if "error" in resultado:
        salida["estado"] = "no_ejecutado"
        salida["resumen"] = resultado["error"]
        return salida

    salida["resumen"] = resultado["resumen"]
    if resultado["ok"]:
        salida["estado"] = "verde"
        return salida

    salida["estado"] = "rojo"
    mapa = criterios_por_test()
    for linea in resultado["fallidos"]:
        fallo = leer_linea(linea)
        criterios = mapa.get(clave_de_trazabilidad(fallo["test"]), [])
        fallo["categoria"] = categoria(fallo, criterios)
        fallo["criterios"] = criterios
        fallo["sospechosos"] = []
        if fallo["categoria"] == "regresion":
            fallo["sospechosos"] = sospechosos(criterios, cambiados)
        for ruta in fallo["sospechosos"]:
            if ruta not in salida["propone_tocar"]:
                salida["propone_tocar"].append(ruta)
        salida["fallos"].append(fallo)
    salida["propone_tocar"].sort()
    return salida


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Agente de triaje de pipeline")
    parser.add_argument("--ruta", default="tests/", help="tests que ejecutar, dentro de tests/")
    parser.add_argument("--cambiados", nargs="*", default=[], help="ficheros que cambia el escenario")
    args = parser.parse_args(argv)
    try:
        salida = triar(args.ruta, args.cambiados)
    except Exception as fallo:
        print("FALLO del agente de triaje: %s: %s" % (type(fallo).__name__, fallo), file=sys.stderr)
        return FALLO_DEL_AGENTE

    # En ASCII: la consola de Windows no siempre escribe UTF-8 y el JSON sigue siendo valido.
    print(json.dumps(salida, ensure_ascii=True, indent=2))
    return CODIGOS_DE_SALIDA[salida["estado"]]


if __name__ == "__main__":
    raise SystemExit(principal())
