"""Calculadora de expediente heredada: nota media, creditos superados y progreso.

La usa el proceso nocturno de secretaria a traves de calcular() y calcular_lote(), y de ella
depende la ordenacion de becas. Las reglas ya no viven aqui: son las de SPEC-002, en
src/aula/reglas/media.py, y este modulo solo adapta el formato del proceso nocturno (un
diccionario por expediente y la ruta del fichero del plan) al dominio.

Su comportamiento esta fijado en tests/test_caracterizacion_legado.py; cada diferencia con el
original (tests/oraculo/calculadora_expediente_v1_original.py) se declara en DESVIACIONES.md.

Historico (lo poco que se sabe):
  2019-03  version inicial
  2020-11  parche convalidaciones (jlm)
  2021-06  ajuste redondeo por peticion de secretaria
  2023-01  se anade progreso, sin tocar la media
  2026-11  S5: caracterizacion, equivalencia sobre 500 expedientes y refactor
"""
from decimal import Decimal
from pathlib import Path

from aula.dominio.modelos import EstadoRegistro, Expediente, RegistroAcademico
from aula.reglas import media as reglas
from aula.reglas.planes import cargar_plan


# --- del formato del proceso nocturno al dominio ---------------------------------

def a_expediente(datos):
    """El expediente del proceso nocturno (un diccionario) como Expediente del dominio.

    Un estado que no existe lanza ValueError (D-06): antes se ignoraba sin avisar.
    """
    registros = []
    for registro in datos["registros"]:
        nota = registro.get("nota")
        if nota is not None:
            nota = Decimal(str(nota))
        registros.append(RegistroAcademico(
            codigo_asignatura=registro["codigo_asignatura"],
            curso_academico=registro.get("curso_academico", ""),
            convocatoria=registro["convocatoria"],
            estado=EstadoRegistro(registro["estado"]),
            nota=nota,
        ))
    return Expediente(datos["estudiante_id"], datos.get("plan", ""), registros)


def plan_de(ruta_plan):
    """El plan del fichero ruta_plan, por ejemplo datos/planes/PLAN-2024.json."""
    ruta = Path(ruta_plan)
    return cargar_plan(ruta.stem, ruta.parent)


# --- convocatorias ---------------------------------------------------------------

def convocatorias(expediente):
    """{codigo: convocatorias consumidas}. Una convalidacion no consume convocatoria."""
    consumidas = {}
    for registro in expediente["registros"]:
        if registro["estado"] == "convalidada":
            continue
        codigo = registro["codigo_asignatura"]
        consumidas[codigo] = consumidas.get(codigo, 0) + 1
    return consumidas


def puede_matricular(expediente, codigo):
    """False si ya se han consumido las convocatorias maximas del plan del estudiante (D-07).

    Es la misma regla que aplica la matricula en src/aula/reglas/motor.py (SPEC-001).
    """
    plan = cargar_plan(expediente["plan"])
    return convocatorias(expediente).get(codigo, 0) < plan.max_convocatorias


# --- puntos de entrada del proceso nocturno --------------------------------------

def calcular(expediente, ruta_plan):
    """Resultado de un estudiante con las reglas de SPEC-002, siempre con su expediente actual."""
    plan = plan_de(ruta_plan)
    datos = a_expediente(expediente)
    return {
        "estudiante_id": expediente["estudiante_id"],
        "nota_media": reglas.nota_media_ponderada(datos, plan),
        "creditos_superados": reglas.creditos_superados(datos, plan),
        "progreso_pct": reglas.progreso(datos, plan),
    }


def calcular_lote(expedientes, ruta_plan):
    resultados = []
    for expediente in expedientes:
        resultados.append(calcular(expediente, ruta_plan))
    return resultados
