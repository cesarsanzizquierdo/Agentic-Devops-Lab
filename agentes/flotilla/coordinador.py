"""Coordinador de la flotilla: lanza un ciclo completo de los tres agentes y lo graba.

  1. Valida el contrato y fija la revision: el mismo commit para los tres agentes.
  2. Prepara un worktree por agente en ~/aula-flotilla/<agente>, fuera de OneDrive, y aplica en
     cada uno el escenario: un parche, sin commit.
  3. Lanza los tres agentes a la vez, cada uno en su worktree y en su proceso. Ninguno espera a
     otro, porque ninguno usa la salida de otro.
  4. Revisa cada salida con el contrato y decide los conflictos y los handoffs (decisiones.py).
  5. Graba el ciclo en labs/S4b-flotilla/ciclo/ (grabacion.py). Es lo unico que escribe.

Los worktrees se quedan para el siguiente ciclo; --limpiar los elimina.

    python -m agentes.flotilla.coordinador --escenario labs/S4b-flotilla/escenario/redondeo_por_asignatura.json
    python -m agentes.flotilla.coordinador --limpiar

Sale con 0 si el ciclo es completo, 1 si es incompleto y 3 si no se ha podido lanzar.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from agentes.flotilla import decisiones, grabacion, worktrees
from agentes.flotilla.contrato import buscar_agente, cargar, validar_contrato

RAIZ = Path(__file__).resolve().parents[2]
CARPETA_DE_LA_FLOTILLA = Path.home() / "aula-flotilla"
SALIDA_DEL_CICLO = RAIZ / "labs" / "S4b-flotilla" / "ciclo"
TIEMPO_MAXIMO = 600     # segundos por agente: holgura de sobra para triaje, que ejecuta la suite
CONFORMIDAD = "conformidad-spec"
TRIAJE = "triaje-pipeline"
MODERNIZACION = "modernizacion-legado"
CAMPOS_DEL_ESCENARIO = ["id", "descripcion", "parche", "spec", "criterios"]


class ErrorDelCiclo(Exception):
    """El ciclo no se puede lanzar: contrato invalido, escenario incompleto, revision sin agentes."""


def cargar_escenario(ruta: Path) -> dict:
    escenario = json.loads(ruta.read_text(encoding="utf-8"))
    for campo in CAMPOS_DEL_ESCENARIO:
        if campo not in escenario:
            raise ErrorDelCiclo("al escenario %s le falta el campo %s" % (ruta, campo))
    return escenario


def preparar_worktrees(contrato: dict, sha: str, parche: str, carpeta_base: Path) -> dict:
    """Un worktree por agente, en `sha` y con el parche aplicado. {agente: carpeta}."""
    carpetas = {}
    for agente in contrato["agentes"]:
        carpeta = carpeta_base / agente["id"]
        worktrees.preparar(carpeta, sha)
        worktrees.aplicar_escenario(carpeta, parche)
        if not (carpeta / agente["modulo"]).is_file():
            raise ErrorDelCiclo("la revision %s no contiene %s: haz commit antes de lanzar el ciclo"
                                % (sha[:12], agente["modulo"]))
        carpetas[agente["id"]] = carpeta
    return carpetas


def entrada_de_conformidad(carpeta: Path, cambiados: list, escenario: dict) -> dict:
    """El cambio del escenario como lo recibe conformidad: los ficheros y los criterios."""
    ficheros = []
    for ruta in cambiados:
        fichero = carpeta / ruta
        contenido = ""
        if fichero.suffix in (".py", ".md") and fichero.is_file():
            contenido = fichero.read_text(encoding="utf-8")
        ficheros.append({"ruta": ruta, "contenido": contenido})
    return {"id": escenario["id"], "ficheros": ficheros, "criterios_declarados": escenario["criterios"]}


def modulos_que_analizar(carpeta: Path, cambiados: list) -> list:
    """Para modernizacion: el legado entero y el codigo de src/ que cambia el escenario."""
    modulos = []
    for fichero in sorted((carpeta / "src/aula/legado").glob("*.py")):
        if fichero.name != "__init__.py":
            modulos.append(fichero.relative_to(carpeta).as_posix())
    for ruta in cambiados:
        es_codigo = ruta.startswith("src/") and ruta.endswith(".py")
        if es_codigo and (carpeta / ruta).is_file() and ruta not in modulos:
            modulos.append(ruta)
    return modulos


def trabajos(contrato: dict, carpetas: dict, escenario: dict, cambiados: list,
             carpeta_base: Path) -> list:
    """Que se lanza: cada agente con su worktree y su linea de comandos."""
    entrada = carpeta_base / "entrada-conformidad.json"
    datos = entrada_de_conformidad(carpetas[CONFORMIDAD], cambiados, escenario)
    entrada.write_text(json.dumps(datos), encoding="utf-8")
    argumentos = {
        CONFORMIDAD: ["--pr", str(entrada), "--spec", escenario["spec"], "--json"],
        TRIAJE: ["--cambiados"] + cambiados,
        MODERNIZACION: modulos_que_analizar(carpetas[MODERNIZACION], cambiados),
    }
    lista = []
    for ident in (CONFORMIDAD, TRIAJE, MODERNIZACION):
        ruta_del_modulo = buscar_agente(contrato["agentes"], ident)["modulo"]
        modulo = ruta_del_modulo[:-len(".py")].replace("/", ".")     # para python -m
        comando = [sys.executable, "-m", modulo] + argumentos[ident]
        lista.append({"agente": ident, "carpeta": carpetas[ident], "comando": comando})
    return lista


def ejecutar(trabajo: dict, comienzo: float) -> dict:
    """Ejecuta un agente en su worktree. inicio y fin son segundos desde el comienzo del ciclo."""
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    inicio = time.perf_counter()
    try:
        proceso = subprocess.run(trabajo["comando"], cwd=trabajo["carpeta"], env=entorno,
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=TIEMPO_MAXIMO)
        codigo = proceso.returncode
        stdout = proceso.stdout
        stderr = proceso.stderr
    except subprocess.TimeoutExpired:
        codigo = None
        stdout = ""
        stderr = "tiempo agotado: mas de %d segundos" % TIEMPO_MAXIMO
    fin = time.perf_counter()
    return {"agente": trabajo["agente"], "carpeta": str(trabajo["carpeta"]), "codigo": codigo,
            "stdout": stdout, "stderr": stderr, "inicio": round(inicio - comienzo, 2),
            "fin": round(fin - comienzo, 2)}


def lanzar_en_paralelo(lista: list) -> list:
    """Todos los trabajos a la vez, cada uno en su hilo y su proceso. Devuelve en el mismo orden."""
    comienzo = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(lista)) as grupo:
        futuros = []
        for trabajo in lista:
            futuros.append(grupo.submit(ejecutar, trabajo, comienzo))
        ejecuciones = []
        for futuro in futuros:
            ejecuciones.append(futuro.result())
    return ejecuciones


def lanzar_ciclo(referencia: str, ruta_escenario: Path, carpeta_base: Path, salida: Path) -> int:
    contrato = cargar()
    errores = validar_contrato(contrato)
    if errores:
        raise ErrorDelCiclo("el contrato no es valido: %s" % "; ".join(errores))
    escenario = cargar_escenario(ruta_escenario)
    parche = (ruta_escenario.parent / escenario["parche"]).read_text(encoding="utf-8")
    sha = worktrees.revision(referencia)

    carpeta_base.mkdir(parents=True, exist_ok=True)
    carpetas = preparar_worktrees(contrato, sha, parche, carpeta_base)
    cambiados = worktrees.cambiados(carpetas[TRIAJE])
    empieza = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ejecuciones = lanzar_en_paralelo(trabajos(contrato, carpetas, escenario, cambiados, carpeta_base))

    resultados = []
    for ejecucion in ejecuciones:
        resultados.append(decisiones.revisar_resultado(contrato, ejecucion))
    ciclo = {"revision": sha, "escenario": escenario, "contrato": contrato["version"],
             "empieza": empieza, "cambiados": cambiados, "resultados": resultados,
             "worktrees": worktrees.git(["worktree", "list"]).splitlines()}
    ciclo.update(decisiones.decidir_ciclo(resultados, contrato))
    grabacion.grabar(ciclo, salida)
    print(grabacion.resumen(ciclo))
    if ciclo["estado"] == "completo":
        return 0
    return 1


def limpiar(carpeta_base: Path) -> int:
    """Elimina los worktrees de la flotilla. 0 si no queda ninguno.

    Con el repositorio en OneDrive, git puede quitar el worktree y no poder borrar sus restos en
    .git/worktrees/ (Permission denied): el worktree ya no existe y los restos son inofensivos.
    """
    quedan = 0
    for agente in cargar()["agentes"]:
        carpeta = carpeta_base / agente["id"]
        try:
            if worktrees.eliminar(carpeta):
                print("eliminado el worktree de %s" % agente["id"])
        except worktrees.ErrorDeGit as fallo:
            if carpeta.resolve() in worktrees.registrados():
                quedan += 1
                print("NO se ha podido eliminar el worktree de %s: %s" % (agente["id"], fallo))
    if quedan:
        return 1
    return 0


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Coordinador de la flotilla de S4b")
    parser.add_argument("--escenario", help="escenario JSON con el parche que se aplica")
    parser.add_argument("--revision", default="HEAD", help="commit que leen los tres agentes")
    parser.add_argument("--carpeta", default=str(CARPETA_DE_LA_FLOTILLA), help="donde van los worktrees")
    parser.add_argument("--salida", default=str(SALIDA_DEL_CICLO), help="donde se graba el ciclo")
    parser.add_argument("--limpiar", action="store_true", help="elimina los worktrees y termina")
    args = parser.parse_args(argv)
    try:
        if args.limpiar:
            return limpiar(Path(args.carpeta))
        if not args.escenario:
            raise ErrorDelCiclo("falta --escenario")
        return lanzar_ciclo(args.revision, Path(args.escenario), Path(args.carpeta), Path(args.salida))
    except Exception as fallo:     # cualquier fallo sale con 3: con 1 pareceria un ciclo incompleto
        print("ERROR: %s: %s" % (type(fallo).__name__, fallo), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(principal())
