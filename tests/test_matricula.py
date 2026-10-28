import pytest
from dataclasses import replace
from fastapi import HTTPException

from aula.api.app import crear_matricula, SolicitudEntrada
from aula.reglas.motor import (evaluar_solicitud, VentanaCerrada, VentanaMatricula, 
                               Grupo, ordenar_por_prioridad)
from aula.dominio.estados import transicionar, TransicionInvalida, PlanInmutable, EstadoMatricula
from tests.utilidades import plan, expediente, registro, solicitud


def test_ca01_ventana_cerrada():
    """cubre: SPEC-001/CA-01"""
    plan_estudios = plan()
    expediente_alumno = expediente()
    solicitud_matricula = solicitud(["MAT101"], momento="2026-10-01T00:00:00")
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    with pytest.raises(VentanaCerrada):
        evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, {})

def test_ca02_prerrequisito_no_superado():
    """cubre: SPEC-001/CA-02"""
    plan_estudios = plan()
    expediente_alumno = expediente()
    solicitud_matricula = solicitud(["EST101"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, {})
    assert not matricula_resultante.lineas[0].admitida
    assert "prerrequisitos pendientes: MAT101" in matricula_resultante.lineas[0].motivo_rechazo

def test_ca03_limite_creditos_superado():
    """cubre: SPEC-001/CA-03"""
    plan_base = plan()
    plan_estudios = replace(plan_base, limite_creditos_curso=10) # Forzamos un limite bajo de 10
    expediente_alumno = expediente()
    solicitud_matricula = solicitud(["MAT101", "FIS101"]) # 6 + 6 = 12 creditos
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, {})
    
    admitidas = [linea for linea in matricula_resultante.lineas if linea.admitida]
    rechazadas = [linea for linea in matricula_resultante.lineas if not linea.admitida]
    
    assert sum(linea.creditos for linea in admitidas) <= 10
    assert len(rechazadas) == 1
    assert "limite de creditos" in rechazadas[0].motivo_rechazo

def test_ca04_convocatorias_agotadas():
    """cubre: SPEC-001/CA-04"""
    plan_estudios = plan()
    expediente_alumno = expediente(
        registro("MAT101", "suspensa", convocatoria=1), registro("MAT101", "suspensa", convocatoria=2),
        registro("MAT101", "suspensa", convocatoria=3), registro("MAT101", "suspensa", convocatoria=4),
        registro("MAT101", "suspensa", convocatoria=5), registro("MAT101", "suspensa", convocatoria=6)
    )
    solicitud_matricula = solicitud(["MAT101"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, {})
    assert not matricula_resultante.lineas[0].admitida
    assert "convocatorias agotadas" in matricula_resultante.lineas[0].motivo_rechazo

def test_ca05_grupo_completo():
    """cubre: SPEC-001/CA-05"""
    plan_estudios = plan()
    expediente_alumno = expediente()
    solicitud_matricula = solicitud(["MAT101", "FIS101"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    grupos = {"MAT101": Grupo("MAT101", 50, 50)}
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, grupos)
    assert matricula_resultante.lineas[0].codigo_asignatura == "MAT101"
    assert matricula_resultante.lineas[0].en_espera is True
    assert matricula_resultante.lineas[1].codigo_asignatura == "FIS101"
    assert matricula_resultante.lineas[1].admitida is True

def test_ca06_convalidacion_cuenta_superada():
    """cubre: SPEC-001/CA-06"""
    plan_estudios = plan()
    expediente_alumno = expediente(registro("MAT101", "convalidada"))
    solicitud_matricula = solicitud(["EST101"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, {})
    assert matricula_resultante.lineas[0].admitida is True

def test_ca07_orden_prioridad():
    """cubre: SPEC-001/CA-07"""
    plan_estudios = plan()
    expediente_a = expediente(registro("MAT101", "aprobada"), estudiante="A")
    expediente_b = expediente(registro("MAT101", "aprobada"), registro("FIS101", "aprobada"), estudiante="B")
    solicitud_a = solicitud(["EST101"], estudiante="A", momento="2026-09-01T10:00:00")
    solicitud_b = solicitud(["EST101"], estudiante="B", momento="2026-09-01T10:05:00")
    ordenadas = ordenar_por_prioridad([solicitud_a, solicitud_b], {"A": expediente_a, "B": expediente_b}, plan_estudios)
    assert ordenadas[0].estudiante_id == "B"

def test_ca08_ya_superada():
    """cubre: SPEC-001/CA-08"""
    plan_estudios = plan()
    expediente_alumno = expediente(registro("MAT101", "aprobada"))
    solicitud_matricula = solicitud(["MAT101"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, {})
    assert not matricula_resultante.lineas[0].admitida
    assert "asignatura ya superada" in matricula_resultante.lineas[0].motivo_rechazo

def test_limite_inclusivo_ventana():
    plan_estudios = plan()
    solicitud_matricula = solicitud(["MAT101"], momento="2026-09-01T00:00:00")
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente(), plan_estudios, ventana_matricula, {})
    assert matricula_resultante.lineas[0].admitida is True

def test_nuevo_ingreso_expediente_vacio():
    plan_estudios = plan()
    solicitud_matricula = solicitud(["MAT101", "PRG102"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente(), plan_estudios, ventana_matricula, {})
    assert matricula_resultante.lineas[0].admitida is True
    assert not matricula_resultante.lineas[1].admitida

def test_grupo_completo_vs_prerrequisito():
    plan_estudios = plan()
    solicitud_matricula = solicitud(["EST101"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente(), plan_estudios, ventana_matricula, {"EST101": Grupo("EST101", 50, 50)})
    assert not matricula_resultante.lineas[0].en_espera
    assert not matricula_resultante.lineas[0].admitida

def test_plan_sin_grupos():
    plan_estudios = plan()
    solicitud_matricula = solicitud(["MAT101"])
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente(), plan_estudios, ventana_matricula, {})
    assert matricula_resultante.lineas[0].admitida is True
    assert matricula_resultante.lineas[0].en_espera is False

def test_solicitud_invalida_vacia():
    plan_estudios = plan()
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    with pytest.raises(ValueError):
        evaluar_solicitud(solicitud([]), expediente(), plan_estudios, ventana_matricula, {})

def test_solicitud_invalida_duplicados():
    plan_estudios = plan()
    ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
    with pytest.raises(ValueError):
        evaluar_solicitud(solicitud(["MAT101", "MAT101"]), expediente(), plan_estudios, ventana_matricula, {})

def test_transicion_estado_valida():
    matricula_inicial = evaluar_solicitud(solicitud(["MAT101"]), expediente(), plan(), VentanaMatricula("2020-01-01T00:00:00", "2030-01-01T00:00:00"), {})
    matricula_actualizada = transicionar(matricula_inicial, EstadoMatricula.CONFIRMADA)
    assert matricula_actualizada.estado == EstadoMatricula.CONFIRMADA

def test_transicion_estado_invalida():
    matricula_inicial = evaluar_solicitud(solicitud(["MAT101"]), expediente(), plan(), VentanaMatricula("2020-01-01T00:00:00", "2030-01-01T00:00:00"), {})
    with pytest.raises(TransicionInvalida):
        transicionar(matricula_inicial, EstadoMatricula.CERRADA)

def test_plan_inmutable_bloqueo():
    """cubre: SPEC-001/INV-03"""
    matricula_inicial = evaluar_solicitud(solicitud(["MAT101"]), expediente(), plan(), VentanaMatricula("2020-01-01T00:00:00", "2030-01-01T00:00:00"), {})
    matricula_confirmada = transicionar(matricula_inicial, EstadoMatricula.CONFIRMADA)
    with pytest.raises(PlanInmutable):
        transicionar(matricula_confirmada, EstadoMatricula.EN_CURSO, nuevo_plan="OTRO-PLAN")

def test_api_crear_matricula():
    """cubre: SPEC-001/INV-01, SPEC-001/INV-02"""
    entrada = SolicitudEntrada(
        estudiante_id="EST-0001",
        curso_academico="2026-2027",
        codigos=["MAT101", "FIS101"],
        momento="2026-09-15T10:00:00"
    )
    matricula_resultante = crear_matricula(entrada)
    assert matricula_resultante.estado == EstadoMatricula.VALIDADA
    assert len(matricula_resultante.lineas) == 2

def test_api_solicitud_invalida_vacia():
    entrada = SolicitudEntrada(
        estudiante_id="EST-0001",
        curso_academico="2026-2027",
        codigos=[]
    )
    with pytest.raises(HTTPException) as exc_info:
        crear_matricula(entrada)
    assert exc_info.value.status_code == 400

def test_limite_umbral_fin_carrera():
        plan_base = plan()
        # Simulamos un plan de 18 creditos totales donde el umbral de fin de carrera es 12
        # y el limite normal de curso es 6 (para notar que la excepcion amplía el limite a 12)
        plan_estudios = replace(
            plan_base,
            creditos_titulo=18,
            limite_creditos_curso=6,
            umbral_final_carrera=12
        )
        # Alumno con 6 creditos superados -> le quedan 12 pendientes (igual al umbral)
        expediente_alumno = expediente(registro("MAT101", "aprobada"))
        
        # Pide 2 asignaturas (12 creditos). Con el limite normal (6) le rechazarian la segunda,
        # pero al activarse el umbral de fin de carrera su limite efectivo pasa a ser 12.
        solicitud_matricula = solicitud(["FIS101", "ALG101"])
        ventana_matricula = VentanaMatricula("2026-09-01T00:00:00", "2026-09-30T23:59:59")
        
        matricula_resultante = evaluar_solicitud(solicitud_matricula, expediente_alumno, plan_estudios, ventana_matricula, {})
        assert matricula_resultante.lineas[0].admitida is True
        assert matricula_resultante.lineas[1].admitida is True