"""Acceso de los agentes de la flotilla al servidor MCP, con el contrato como filtro.

El servidor no distingue quien le llama: da sus cinco herramientas a cualquiera. Este modulo
es la puerta por la que triaje y modernizacion le piden herramientas, y solo deja pasar las
que el contrato (agentes/flotilla/contrato.json) declara para cada agente:

    consultar("triaje-pipeline", "listar_specs", {})            -> {"specs": [...]}
    consultar("modernizacion-legado", "resultado_tests", {})    -> HerramientaNoDeclarada

Es un control de diseno, no de seguridad: un agente que importe el servidor directamente se
lo salta. El control fuerte (manifiesto firmado y gate en el pipeline) es trabajo de S6.
"""
from __future__ import annotations

import json

from agentes.flotilla.contrato import buscar_agente, cargar
from agentes.mcp_aula.servidor import manejar


class HerramientaNoDeclarada(Exception):
    """El agente pide una herramienta que su contrato no declara."""


class ErrorDelServidor(Exception):
    """El servidor rechaza la llamada: herramienta desconocida o argumentos mal formados."""


def herramientas_declaradas(agente: str) -> list:
    contrato = cargar()
    datos = buscar_agente(contrato["agentes"], agente)
    if datos is None:
        raise HerramientaNoDeclarada("%s no esta declarado en el contrato" % agente)
    return datos["herramientas_mcp"]


def consultar(agente: str, herramienta: str, argumentos: dict) -> dict:
    """Pide `herramienta` al servidor MCP en nombre de `agente`.

    Devuelve lo que devuelve la herramienta. Si la herramienta falla por dentro (por ejemplo,
    una spec que no existe), el resultado trae la clave "error", igual que en el servidor:
    decidir que hacer con ese error es trabajo del agente.
    """
    if herramienta not in herramientas_declaradas(agente):
        raise HerramientaNoDeclarada("%s no declara %s en el contrato" % (agente, herramienta))

    respuesta = manejar({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                         "params": {"name": herramienta, "arguments": argumentos}})
    if "error" in respuesta:
        raise ErrorDelServidor(respuesta["error"]["message"])
    return json.loads(respuesta["result"]["content"][0]["text"])
