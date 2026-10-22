"""S1: completar las transiciones y proteger el plan confirmado."""
from __future__ import annotations

from dataclasses import replace
from .modelos import EstadoMatricula, Matricula

TRANSICIONES: dict[EstadoMatricula, set[EstadoMatricula]] = {
    EstadoMatricula.SOLICITADA: {EstadoMatricula.VALIDADA, EstadoMatricula.ANULADA},
    EstadoMatricula.VALIDADA: {EstadoMatricula.CONFIRMADA, EstadoMatricula.ANULADA},
    EstadoMatricula.CONFIRMADA: {EstadoMatricula.EN_CURSO, EstadoMatricula.ANULADA},
    EstadoMatricula.EN_CURSO: {EstadoMatricula.CALIFICADA, EstadoMatricula.ANULADA},
    EstadoMatricula.CALIFICADA: {EstadoMatricula.CERRADA},
    EstadoMatricula.CERRADA: set(),
    EstadoMatricula.ANULADA: set(),
}

ESTADOS_PLAN_BLOQUEADO = {
    EstadoMatricula.CONFIRMADA,
    EstadoMatricula.EN_CURSO,
    EstadoMatricula.CALIFICADA,
    EstadoMatricula.CERRADA,
}


class TransicionInvalida(Exception):
    pass


class PlanInmutable(Exception):
    pass


def transiciones_validas(estado: EstadoMatricula) -> set[EstadoMatricula]:
    return set(TRANSICIONES.get(estado, set()))


def transicionar(matricula: Matricula, destino: EstadoMatricula,
                 nuevo_plan: str = None) -> Matricula:
    if nuevo_plan is not None and nuevo_plan != matricula.plan_aplicado:
        if matricula.estado in ESTADOS_PLAN_BLOQUEADO or destino in ESTADOS_PLAN_BLOQUEADO:
            raise PlanInmutable(f"No se puede cambiar el plan en estado {matricula.estado}")
    if destino not in transiciones_validas(matricula.estado):
        raise TransicionInvalida(f"Transicion invalida: {matricula.estado} -> {destino}")
    plan_final = nuevo_plan if nuevo_plan is not None else matricula.plan_aplicado
    return replace(matricula, estado=destino, plan_aplicado=plan_final)