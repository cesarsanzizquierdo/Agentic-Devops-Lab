"""Contrato de contexto de la flotilla: carga y validacion.

El contrato (agentes/flotilla/contrato.json) dice que ve cada agente, que escribe, que se pasan
y que pasa cuando dos quieren tocar el mismo fichero. Este modulo comprueba dos cosas:

  validar_contrato(contrato)                 el contrato es coherente consigo mismo y con el
                                             servidor MCP
  validar_salida(contrato, agente, salida)   la salida real de un agente trae lo que promete

Las dos devuelven la lista de errores: vacia si todo esta bien.

    python -m agentes.flotilla.contrato      imprime OK o los errores (sale con 0 o con 1)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from agentes.mcp_aula.servidor import HERRAMIENTAS

RUTA_CONTRATO = Path(__file__).resolve().parent / "contrato.json"
HUMANO = "humano"
PROPONE = "propone_tocar"
CAMPOS_DEL_CONTRATO = ["version", "contexto_compartido", "agentes", "coordinador", "handoff",
                       "conflicto", "si_falla_un_agente"]
CAMPOS_DEL_AGENTE = ["id", "modulo", "proposito", "invocacion", "herramientas_mcp", "entradas",
                     "salida", "codigos_salida", "escribe"]
CAMPOS_DEL_HANDOFF = ["de", "a", "cuando", "campos", "que_pasa"]
CAMPOS_DEL_CONFLICTO = ["cuando", "deteccion", "prioridad", "regla", "escalado", "en_git"]


def cargar(ruta: Path = RUTA_CONTRATO) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def buscar_agente(agentes: list, ident: str):
    for agente in agentes:
        if agente.get("id") == ident:
            return agente
    return None


def nombres_de_herramientas() -> list:
    """Las herramientas que da el servidor MCP: las unicas que un agente puede declarar."""
    nombres = []
    for herramienta in HERRAMIENTAS:
        nombres.append(herramienta["name"])
    return nombres


def faltan(objeto: dict, campos: list, donde: str) -> list:
    errores = []
    for campo in campos:
        if campo not in objeto:
            errores.append("%s le falta %s" % (donde, campo))
    return errores


def errores_de_agentes(agentes: list) -> list:
    errores = []
    vistos = []
    disponibles = nombres_de_herramientas()
    for agente in agentes:
        ident = agente.get("id", "?")
        incompleto = faltan(agente, CAMPOS_DEL_AGENTE, "al agente %s" % ident)
        if incompleto:
            errores.extend(incompleto)
            continue
        if ident in vistos:
            errores.append("el agente %s esta repetido" % ident)
        vistos.append(ident)
        for herramienta in agente["herramientas_mcp"]:
            if herramienta not in disponibles:
                errores.append("%s declara %s, que el servidor MCP no tiene" % (ident, herramienta))
        if agente["escribe"]:
            errores.append("%s no puede escribir ficheros: solo devuelve su salida" % ident)
    return errores


def errores_de_handoff(contrato: dict) -> list:
    errores = []
    for paso in contrato["handoff"]:
        incompleto = faltan(paso, CAMPOS_DEL_HANDOFF, "a un handoff")
        if incompleto:
            errores.extend(incompleto)
            continue
        emisor = buscar_agente(contrato["agentes"], paso["de"])
        if emisor is None:
            errores.append("un handoff sale de %s, que no es un agente del contrato" % paso["de"])
            continue
        if paso["a"] != HUMANO and buscar_agente(contrato["agentes"], paso["a"]) is None:
            errores.append("el handoff de %s va a %s, que no es un agente ni el humano"
                           % (paso["de"], paso["a"]))
        for campo in paso["campos"]:
            if campo not in emisor["salida"]:
                errores.append("el handoff de %s pasa %s, que no esta en su salida" % (paso["de"], campo))
        cuando = paso["cuando"]
        if cuando != "siempre":
            if not isinstance(cuando, dict) or cuando.get("campo") not in emisor["salida"]:
                errores.append('el "cuando" del handoff de %s no es "siempre" ni un campo de su'
                               ' salida' % paso["de"])
    return errores


def errores_de_conflicto(contrato: dict) -> list:
    """La regla esta completa y la prioridad ordena a todos los que proponen tocar ficheros."""
    conflicto = contrato["conflicto"]
    errores = faltan(conflicto, CAMPOS_DEL_CONFLICTO, "al apartado conflicto")
    if errores:
        return errores
    proponen = []
    for agente in contrato["agentes"]:
        if PROPONE in agente["salida"]:
            proponen.append(agente["id"])
    prioridad = conflicto["prioridad"]
    if sorted(prioridad) != sorted(proponen):
        errores.append("la prioridad debe nombrar una vez a cada agente que propone tocar"
                       " ficheros: %s" % ", ".join(proponen))
    return errores


def validar_contrato(contrato: dict) -> list:
    errores = faltan(contrato, CAMPOS_DEL_CONTRATO, "al contrato")
    if errores:
        return errores
    errores = errores_de_agentes(contrato["agentes"])
    if errores:
        return errores     # sin los agentes bien declarados, el resto no se puede comprobar
    errores.extend(errores_de_handoff(contrato))
    errores.extend(errores_de_conflicto(contrato))
    return errores


def validar_salida(contrato: dict, ident: str, salida) -> list:
    """La salida de un agente es un objeto JSON con todos los campos que declara su contrato."""
    agente = buscar_agente(contrato["agentes"], ident)
    if agente is None:
        return ["%s no esta en el contrato" % ident]
    if not isinstance(salida, dict):
        return ["la salida de %s no es un objeto JSON" % ident]
    errores = []
    for campo in agente["salida"]:
        if campo not in salida:
            errores.append("a la salida de %s le falta %s" % (ident, campo))
    return errores


def principal() -> int:
    errores = validar_contrato(cargar())
    for error in errores:
        print("ERROR: %s" % error)
    if errores:
        return 1
    print("OK: contrato valido, %d agentes" % len(cargar()["agentes"]))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
