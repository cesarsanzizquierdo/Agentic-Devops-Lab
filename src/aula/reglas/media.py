"""S2: resolver SPEC-002 antes de implementar el calculo del expediente."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from ..dominio.modelos import Expediente, Plan, EstadoRegistro, RegistroAcademico

DOS_DECIMALES = Decimal("0.01")
CERO_DECIMAL = Decimal("0.00")


def convertir_a_decimal(valor: Decimal | int | float | str) -> Decimal:
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def obtener_codigos_ordenados(expediente: Expediente) -> list[str]:
    """Extrae los codigos de asignatura sin duplicados y ordenados alfabeticamente (INV-03)."""
    codigos_vistos = []
    for registro in expediente.registros:
        codigo = registro.codigo_asignatura
        if codigo not in codigos_vistos:
            codigos_vistos.append(codigo)
    codigos_vistos.sort()
    return codigos_vistos


def es_convalidada(registro: RegistroAcademico) -> bool:
    """Comprueba si un registro academico tiene estado convalidado (CA-03, CA-05)."""
    return registro.estado == EstadoRegistro.CONVALIDADA


def nota_media_ponderada(expediente: Expediente, plan: Plan) -> Decimal:
    """Calcula la nota media ponderada por creditos con redondeo unico al final."""
    suma_ponderada = Decimal("0")
    creditos_computables = Decimal("0")

    codigos_expediente = obtener_codigos_ordenados(expediente)

    for codigo in codigos_expediente:
        if codigo not in plan.asignaturas:
            continue

        # CA-03: Las asignaturas convalidadas no entran ni en numerador ni en denominador
        if expediente.convalidada(codigo):
            continue

        # CA-02: Solo computa la ultima convocatoria aprobada
        ultimo_aprobado = expediente.ultimo_intento_aprobado(codigo)
        if ultimo_aprobado is None or ultimo_aprobado.nota is None:
            continue

        asignatura_plan = plan.asignatura(codigo)
        creditos_asignatura = Decimal(asignatura_plan.creditos)
        nota_asignatura = convertir_a_decimal(ultimo_aprobado.nota)

        # INV-01: Acumulamos sin redondear valores intermedios
        puntos_asignatura = nota_asignatura * creditos_asignatura
        suma_ponderada += puntos_asignatura
        creditos_computables += creditos_asignatura

    # CA-07: Si no hay asignaturas computables, devolvemos 0.00
    if creditos_computables == Decimal("0"):
        return CERO_DECIMAL

    # CA-04: Aplicamos el redondeo half-up una sola vez sobre la division final
    media_sin_redondear = suma_ponderada / creditos_computables
    media_redondeada = media_sin_redondear.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
    return media_redondeada


def creditos_superados(expediente: Expediente, plan: Plan) -> int:
    """Suma los creditos de todas las asignaturas aprobadas o convalidadas (CA-05)."""
    total_creditos = 0
    codigos_expediente = obtener_codigos_ordenados(expediente)

    for codigo in codigos_expediente:
        if codigo in plan.asignaturas:
            if expediente.superada(codigo):
                asignatura_plan = plan.asignatura(codigo)
                total_creditos += asignatura_plan.creditos

    return total_creditos


def progreso(expediente: Expediente, plan: Plan) -> Decimal:
    """Calcula el porcentaje de creditos superados respecto al total del titulo (CA-06)."""
    if plan.creditos_titulo <= 0:
        return CERO_DECIMAL

    total_superados = Decimal(creditos_superados(expediente, plan))
    creditos_totales_titulo = Decimal(plan.creditos_titulo)

    porcentaje_bruto = (total_superados * Decimal("100")) / creditos_totales_titulo
    porcentaje_redondeado = porcentaje_bruto.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
    return porcentaje_redondeado


def convocatorias_por_asignatura(expediente: Expediente, plan: Plan) -> dict[str, int]:
    """Devuelve un diccionario con el numero de convocatorias consumidas por asignatura."""
    resumen_convocatorias = {}
    codigos_expediente = obtener_codigos_ordenados(expediente)

    for codigo in codigos_expediente:
        if codigo in plan.asignaturas:
            consumidas = expediente.convocatorias_consumidas(codigo)
            resumen_convocatorias[codigo] = consumidas

    return resumen_convocatorias


def resumen_expediente(expediente: Expediente, plan: Plan) -> dict:
    """Construye el diccionario completo con el estado academico del estudiante."""
    media_calculada = nota_media_ponderada(expediente, plan)
    creditos_calculados = creditos_superados(expediente, plan)
    progreso_calculado = progreso(expediente, plan)
    convocatorias_calculadas = convocatorias_por_asignatura(expediente, plan)

    return {
        "estudiante_id": expediente.estudiante_id,
        "plan": plan.codigo,
        "nota_media": media_calculada,
        "creditos_superados": creditos_calculados,
        "progreso": progreso_calculado,
        "progreso_pct": progreso_calculado,
        "convocatorias": convocatorias_calculadas,
    }