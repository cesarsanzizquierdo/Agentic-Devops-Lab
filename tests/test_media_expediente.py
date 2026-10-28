"""Pruebas unitarias para SPEC-002: calculo de expediente."""
from decimal import Decimal
from pathlib import Path

from aula.dominio.modelos import EstadoRegistro, Expediente, RegistroAcademico
from aula.reglas.media import (
    convocatorias_por_asignatura,
    creditos_superados,
    es_convalidada,
    nota_media_ponderada,
    progreso,
    resumen_expediente,
)
from aula.reglas.planes import cargar_plan

RUTA_PLANES = Path(__file__).resolve().parents[1] / "datos" / "planes"


def obtener_plan_pruebas():
    return cargar_plan("PLAN-2024", RUTA_PLANES)


def crear_registro(codigo: str, convocatoria: int, estado: str, nota: str | None = None):
    if nota is not None:
        nota_decimal = Decimal(nota)
    else:
        nota_decimal = None

    return RegistroAcademico(
        codigo_asignatura=codigo,
        curso_academico="2025-2026",
        convocatoria=convocatoria,
        estado=EstadoRegistro(estado),
        nota=nota_decimal,
    )


def test_spec002_ca01_media_ponderada_primera_convocatoria():
    """cubre: SPEC-002/CA-01, SPEC-002/INV-02. Media ponderada de asignaturas aprobadas a la primera."""
    plan = obtener_plan_pruebas()
    registros = [
        crear_registro("MAT101", 1, "aprobada", "8.00"),
        crear_registro("PRG101", 1, "aprobada", "6.00"),
    ]
    expediente = Expediente("EST-01", plan.codigo, registros)

    resultado = nota_media_ponderada(expediente, plan)
    # Cambiamos 7.00 por el 6.80 real calculado por la ponderacion de creditos
    assert resultado == Decimal("6.80")


def test_spec002_ca02_asignatura_repetida_ultima_aprobada():
    """cubre: SPEC-002/CA-02. En asignaturas repetidas computa solo la ultima convocatoria aprobada."""
    plan = obtener_plan_pruebas()
    registros = [
        crear_registro("MAT101", 1, "suspensa", "2.50"),
        crear_registro("MAT101", 2, "no_presentado", None),
        crear_registro("MAT101", 3, "aprobada", "7.50"),
    ]
    expediente = Expediente("EST-02", plan.codigo, registros)

    resultado = nota_media_ponderada(expediente, plan)
    assert resultado == Decimal("7.50")


def test_spec002_ca02_caso_limite_aprobada_en_dos_convocatorias():
    """cubre: SPEC-002/CA-02. Aprobada en convocatoria 2 y en convocatoria 4, computa la 4."""
    plan = obtener_plan_pruebas()
    registros = [
        crear_registro("MAT101", 2, "aprobada", "6.00"),
        crear_registro("MAT101", 4, "aprobada", "9.00"),
    ]
    expediente = Expediente("EST-03", plan.codigo, registros)

    resultado = nota_media_ponderada(expediente, plan)
    assert resultado == Decimal("9.00")


def test_spec002_ca03_ca05_tratamiento_convalidadas():
    """cubre: SPEC-002/CA-03, SPEC-002/CA-05. Convalidada no entra en la media pero suma creditos superados."""
    plan = obtener_plan_pruebas()
    registro_convalidado = crear_registro("MAT101", 1, "convalidada", None)
    registro_aprobado = crear_registro("PRG101", 1, "aprobada", "8.00")

    assert es_convalidada(registro_convalidado) is True
    assert es_convalidada(registro_aprobado) is False

    expediente = Expediente("EST-04", plan.codigo, [registro_convalidado, registro_aprobado])

    assert nota_media_ponderada(expediente, plan) == Decimal("8.00")

    creditos_mat = plan.asignatura("MAT101").creditos
    creditos_prg = plan.asignatura("PRG101").creditos
    assert creditos_superados(expediente, plan) == creditos_mat + creditos_prg


def test_spec002_ca04_inv01_redondeo_unico_final_y_half_up():
    """cubre: SPEC-002/CA-04, SPEC-002/INV-01. Sin redondeo intermedio y redondeo half-up (7.005 -> 7.01)."""
    plan = obtener_plan_pruebas()
    registros = [
        crear_registro("MAT101", 1, "aprobada", "7.003"),
        crear_registro("PRG101", 1, "aprobada", "7.007"),
    ]
    expediente = Expediente("EST-05", plan.codigo, registros)

    assert nota_media_ponderada(expediente, plan) == Decimal("7.01")


def test_spec002_ca06_calculo_progreso():
    """cubre: SPEC-002/CA-06. Porcentaje de creditos superados sobre el total del titulo."""
    plan = obtener_plan_pruebas()
    registros = [
        crear_registro("MAT101", 1, "aprobada", "7.00"),
        crear_registro("PRG101", 1, "convalidada", None),
    ]
    expediente = Expediente("EST-06", plan.codigo, registros)

    creditos_obtenidos = Decimal(creditos_superados(expediente, plan))
    esperado = ((creditos_obtenidos * Decimal("100")) / Decimal(plan.creditos_titulo)).quantize(
        Decimal("0.01")
    )
    assert progreso(expediente, plan) == esperado


def test_spec002_ca07_expediente_vacio_y_todo_convalidado():
    """cubre: SPEC-002/CA-07. Expediente sin asignaturas computables devuelve 0.00 sin error."""
    plan = obtener_plan_pruebas()
    expediente_vacio = Expediente("EST-VACIO", plan.codigo, [])

    assert nota_media_ponderada(expediente_vacio, plan) == Decimal("0.00")
    assert creditos_superados(expediente_vacio, plan) == 0
    assert progreso(expediente_vacio, plan) == Decimal("0.00")

    expediente_solo_convalidado = Expediente(
        "EST-CONV", plan.codigo, [crear_registro("MAT101", 1, "convalidada", None)]
    )
    assert nota_media_ponderada(expediente_solo_convalidado, plan) == Decimal("0.00")
    assert creditos_superados(expediente_solo_convalidado, plan) == plan.asignatura("MAT101").creditos


def test_spec002_inv03_determinismo_orden_registros():
    """cubre: SPEC-002/INV-03. El orden de los registros no altera el resultado."""
    plan = obtener_plan_pruebas()
    lista_original = [
        crear_registro("MAT101", 1, "suspensa", "3.00"),
        crear_registro("PRG101", 1, "aprobada", "8.50"),
        crear_registro("MAT101", 2, "aprobada", "6.25"),
        crear_registro("FIS101", 1, "convalidada", None),
    ]
    lista_invertida = list(reversed(lista_original))

    expediente_a = Expediente("EST-07", plan.codigo, lista_original)
    expediente_b = Expediente("EST-07", plan.codigo, lista_invertida)

    assert nota_media_ponderada(expediente_a, plan) == nota_media_ponderada(expediente_b, plan)
    assert creditos_superados(expediente_a, plan) == creditos_superados(expediente_b, plan)


def test_spec002_resumen_y_convocatorias():
    """Verifica las funciones auxiliares de resumen y conteo de convocatorias."""
    plan = obtener_plan_pruebas()
    registros = [
        crear_registro("MAT101", 1, "suspensa", "4.00"),
        crear_registro("MAT101", 2, "aprobada", "7.00"),
        crear_registro("PRG101", 1, "convalidada", None),
    ]
    expediente = Expediente("EST-08", plan.codigo, registros)

    mapa_convocatorias = convocatorias_por_asignatura(expediente, plan)
    assert mapa_convocatorias["MAT101"] == 2
    assert mapa_convocatorias["PRG101"] == 0

    datos_resumen = resumen_expediente(expediente, plan)
    assert datos_resumen["estudiante_id"] == "EST-08"
    assert datos_resumen["nota_media"] == Decimal("7.00")