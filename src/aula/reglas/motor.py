"""S1: implementar las reglas de matricula descritas en SPEC-001."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ..auditoria import registrar_decision
from ..dominio.modelos import Expediente, Matricula, Plan, SolicitudMatricula, EstadoMatricula, LineaMatricula


class VentanaCerrada(Exception):
    pass


def instante_utc(momento: str) -> datetime:
    """SPEC-001 A-04: un instante sin zona horaria se interpreta como UTC."""
    t = datetime.fromisoformat(momento)
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


@dataclass(frozen=True)
class VentanaMatricula:
    inicio: str
    fin: str

    def contiene(self, momento: str) -> bool:
        return instante_utc(self.inicio) <= instante_utc(momento) <= instante_utc(self.fin)
        #raise NotImplementedError("S1: comprobar la ventana de matricula")


@dataclass(frozen=True)
class Grupo:
    codigo_asignatura: str
    capacidad: int
    ocupadas: int

    @property
    def libre(self) -> bool:
        return self.ocupadas < self.capacidad
        #raise NotImplementedError("S1: comprobar la capacidad del grupo")


def creditos_superados(expediente: Expediente, plan: Plan) -> int:
    total_creditos = 0
    for cod_asignatura, asignatura in plan.asignaturas.items():
        if expediente.superada(cod_asignatura):
            total_creditos += asignatura.creditos
    return total_creditos
   # raise NotImplementedError("S1: calcular creditos superados segun SPEC-001")


def creditos_pendientes(expediente: Expediente, plan: Plan) -> int:
    superados = creditos_superados(expediente, plan)
    restantes = plan.creditos_titulo - superados
    
    if restantes < 0:
        return 0
    return restantes
   # raise NotImplementedError("S1: calcular creditos pendientes")


def prioridad(expediente: Expediente, plan: Plan) -> int:
    return creditos_superados(expediente, plan)
   # raise NotImplementedError("S1: calcular prioridad de matricula")


def evaluar_solicitud(solicitud: SolicitudMatricula, expediente: Expediente,
                      plan: Plan, ventana: VentanaMatricula,
                      grupos: dict) -> Matricula:
    if not solicitud.codigos or len(solicitud.codigos) != len(set(solicitud.codigos)):
        registrar_decision(solicitud.estudiante_id, solicitud.curso_academico,
                           plan.codigo, plan.version, solicitud.momento,
                           {"estado": "rechazada", "motivo": "solicitud_invalida"})
        raise ValueError("La solicitud no puede estar vacia ni tener codigos duplicados")

    if not ventana.contiene(solicitud.momento):
        registrar_decision(solicitud.estudiante_id, solicitud.curso_academico,
                           plan.codigo, plan.version, solicitud.momento,
                           {"estado": "rechazada", "motivo": "ventana_cerrada"})
        raise VentanaCerrada("Solicitud fuera de la ventana de matricula")

    pendientes = creditos_pendientes(expediente, plan)
    limite = pendientes if pendientes <= plan.umbral_final_carrera else plan.limite_creditos_curso
    grupos = grupos or {}
    lineas: list[LineaMatricula] = []
    creditos_acumulados = 0

    for codigo in solicitud.codigos:
        if codigo not in plan.asignaturas:
            # SPEC-001 A-03: se rechaza solo esta linea, sin afectar al resto
            lineas.append(LineaMatricula(codigo, 0, False, False, "asignatura no pertenece al plan"))
            continue
        asig = plan.asignatura(codigo)
        faltan = []
        
        for p in asig.prerrequisitos:
            if not expediente.superada(p):
                faltan.append(p)

        if expediente.superada(codigo):
            lineas.append(LineaMatricula(codigo, asig.creditos, False, False, "asignatura ya superada"))
        elif expediente.convocatorias_consumidas(codigo) >= plan.max_convocatorias:
            lineas.append(LineaMatricula(codigo, asig.creditos, False, False, "convocatorias agotadas"))
        elif faltan:
            lineas.append(LineaMatricula(codigo, asig.creditos, False, False,
                                         f"prerrequisitos pendientes: {', '.join(faltan)}"))
        elif codigo in grupos and not grupos[codigo].libre:
            lineas.append(LineaMatricula(codigo, asig.creditos, False, True, None))
        elif creditos_acumulados + asig.creditos > limite:
            lineas.append(LineaMatricula(codigo, asig.creditos, False, False, "limite de creditos superado"))
        else:
            creditos_acumulados += asig.creditos
            lineas.append(LineaMatricula(codigo, asig.creditos, True, False, None))

    matricula = Matricula(
        estudiante_id=solicitud.estudiante_id,
        curso_academico=solicitud.curso_academico,
        plan_aplicado=plan.codigo,
        version_plan_aplicada=plan.version,
        estado=EstadoMatricula.VALIDADA,
        lineas=lineas,
    )
    registrar_decision(
        solicitud.estudiante_id, solicitud.curso_academico,
        plan.codigo, plan.version, solicitud.momento,
        {"estado": matricula.estado.value, "creditos_admitidos": matricula.creditos_admitidos},
    )
    return matricula
   # raise NotImplementedError("S1: evaluar solicitud y registrar auditoria")


def ordenar_por_prioridad(solicitudes: list[SolicitudMatricula],
                          expedientes: dict[str, Expediente], plan: Plan) -> list[SolicitudMatricula]:
    return sorted(
        solicitudes,
        key=lambda s: (
            -prioridad(expedientes.get(s.estudiante_id, Expediente(s.estudiante_id, plan.codigo)), plan),
            instante_utc(s.momento),
        ),
    )
    #raise NotImplementedError("S1: ordenar solicitudes segun SPEC-001")