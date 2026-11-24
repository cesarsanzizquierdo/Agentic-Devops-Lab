"""Decisiones del coordinador al acabar un ciclo: las reglas del contrato, en funciones puras.

  revisar_resultado   la ejecucion de un agente cumple su contrato, o por que no
  conflictos          ficheros que proponen tocar dos agentes, y quien gana por prioridad
  handoffs            lo que llega al humano de cada agente, segun la condicion del contrato
  decidir_ciclo       todo junto: si un agente falla, el ciclo es incompleto y no se decide
                      ningun conflicto
"""
from __future__ import annotations

import json

from agentes.flotilla.contrato import buscar_agente, validar_salida

TRIAJE = "triaje-pipeline"


def revisar_resultado(contrato: dict, ejecucion: dict) -> dict:
    """El resultado de un agente: su salida si cumple el contrato y, si no, los errores."""
    ident = ejecucion["agente"]
    codigos = buscar_agente(contrato["agentes"], ident)["codigos_salida"]
    resultado = {"agente": ident, "carpeta": ejecucion["carpeta"], "inicio": ejecucion["inicio"],
                 "fin": ejecucion["fin"], "codigo": ejecucion["codigo"], "salida": None,
                 "errores": []}
    if ejecucion["codigo"] is None:
        resultado["errores"].append("%s no acabo a tiempo" % ident)
    elif str(ejecucion["codigo"]) not in codigos:
        resultado["errores"].append("%s salio con el codigo %s, que su contrato no declara"
                                    % (ident, ejecucion["codigo"]))
    try:
        salida = json.loads(ejecucion["stdout"])
        errores_de_la_salida = validar_salida(contrato, ident, salida)
    except json.JSONDecodeError:
        salida = None
        errores_de_la_salida = ["%s no devolvio JSON" % ident]
    resultado["errores"].extend(errores_de_la_salida)
    if not errores_de_la_salida:
        resultado["salida"] = salida
    if resultado["errores"]:
        resultado["stderr"] = ejecucion["stderr"][-2000:]     # la causa del fallo
    return resultado


def conflictos(resultados: list, prioridad: list) -> list:
    """Un fichero que proponen dos agentes: gana el de mas prioridad y el otro se pospone."""
    por_fichero = {}
    for resultado in resultados:
        for ruta in resultado["salida"].get("propone_tocar", []):
            agentes = por_fichero.setdefault(ruta, [])
            if resultado["agente"] not in agentes:
                agentes.append(resultado["agente"])

    decisiones = []
    for fichero in sorted(por_fichero):
        if len(por_fichero[fichero]) < 2:
            continue
        ordenados = []
        for ident in prioridad:
            if ident in por_fichero[fichero]:
                ordenados.append(ident)
        decisiones.append({"fichero": fichero, "gana": ordenados[0], "se_pospone": ordenados[1:]})
    return decisiones


def se_cumple(cuando, salida: dict) -> bool:
    if cuando == "siempre":
        return True
    return salida[cuando["campo"]] in cuando["valores"]


def handoffs(resultados: list, contrato: dict) -> list:
    """Cada handoff del contrato cuya condicion se cumple, con los campos que pasa."""
    entregas = []
    for paso in contrato["handoff"]:
        for resultado in resultados:
            if resultado["agente"] != paso["de"] or not se_cumple(paso["cuando"], resultado["salida"]):
                continue
            datos = {}
            for campo in paso["campos"]:
                datos[campo] = resultado["salida"][campo]
            entregas.append({"de": paso["de"], "a": paso["a"], "que_pasa": paso["que_pasa"],
                             "datos": datos})
    return entregas


def decidir_ciclo(resultados: list, contrato: dict) -> dict:
    """Estado del ciclo, conflictos y handoffs, como dice el contrato (si_falla_un_agente).

    Sin saber si el pipeline esta en verde no se decide quien va primero, asi que un ciclo
    incompleto no decide conflictos. Los handoffs de los agentes que no han fallado si llegan.
    """
    sin_fallo = []
    motivos = []
    for resultado in resultados:
        motivos.extend(resultado["errores"])
        if resultado["errores"]:
            continue
        sin_fallo.append(resultado)
        if resultado["agente"] == TRIAJE and resultado["salida"]["estado"] == "no_ejecutado":
            motivos.append("triaje no pudo ejecutar los tests: %s" % resultado["salida"]["resumen"])

    decididos = []
    estado = "incompleto"
    if not motivos:
        estado = "completo"
        decididos = conflictos(sin_fallo, contrato["conflicto"]["prioridad"])
    return {"estado": estado, "motivos": motivos, "conflictos": decididos,
            "handoffs": handoffs(sin_fallo, contrato)}
