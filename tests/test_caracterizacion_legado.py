"""Caracterizacion del modulo heredado src/aula/legado/calculadora_expediente_v1.py.

Fija lo que el modulo hace HOY, aunque este mal: es la red para refactorizarlo. Cada valor
esperado esta calculado a mano a partir del codigo, con los creditos de PLAN-2024 (MAT101, FIS101
y ALG101 tienen 6; PRG101, 9; ING101, 3; el titulo, 192).

Se prueba a traves de lo que usa el proceso nocturno de secretaria (calcular, calcular_lote,
convocatorias y puede_matricular), no de sus funciones internas, que el refactor va a cambiar.
Los numeros se comparan con Decimal(str(valor)): asi el test vale tanto si el modulo devuelve
float como si devuelve Decimal.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from aula.legado import calculadora_expediente_v1 as legado

RUTA_PLAN = str(Path(__file__).resolve().parents[1] / "datos" / "planes" / "PLAN-2024.json")


@pytest.fixture(autouse=True)
def sin_cache():
    """Cada test empieza con la cache del modulo vacia, si la tiene."""
    cache = getattr(legado, "_CACHE", None)
    if cache is not None:
        cache.clear()


def registro(codigo, estado, nota=None, convocatoria=1, curso="2024-2025"):
    return {"codigo_asignatura": codigo, "curso_academico": curso,
            "convocatoria": convocatoria, "estado": estado, "nota": nota}


def expediente(*registros, estudiante="EST-T"):
    return {"estudiante_id": estudiante, "plan": "PLAN-2024", "registros": list(registros)}


def como_decimal(valor) -> Decimal:
    return Decimal(str(valor))


def calcular(*registros):
    return legado.calcular(expediente(*registros), RUTA_PLAN)


# --- los dos comportamientos que el propio fichero marca como no documentados ---

def test_no_documentado_1_la_convalidada_no_entra_en_la_media():
    """Antes del refactor la convalidada sumaba 5,0 x creditos en el numerador y nada en el
    denominador: (6,0 x 6 + 5,0 x 6) / 6 = 11,0, por encima del maximo de 10.

    Cambiado por D-02 (SPEC-002 CA-03): no entra ni arriba ni abajo, y la media es 6,0. Sus
    creditos siguen contando como superados (CA-05)."""
    resultado = calcular(registro("MAT101", "aprobada", 6.0), registro("FIS101", "convalidada"))

    assert como_decimal(resultado["nota_media"]) == Decimal("6.0")
    assert resultado["creditos_superados"] == 12


def test_no_documentado_2_redondea_cada_asignatura_antes_de_sumar():
    """6,004, 6,004 y 6,009 (6 creditos cada una) se redondean a 6,00, 6,00 y 6,01 antes de
    sumar: la media es 6,0033, que da 6,00. Redondeando una sola vez al final daria 6,01."""
    resultado = calcular(registro("MAT101", "aprobada", 6.004), registro("FIS101", "aprobada", 6.004),
                         registro("ALG101", "aprobada", 6.009))

    assert como_decimal(resultado["nota_media"]) == Decimal("6.00")


def test_la_nota_se_redondea_en_coma_flotante():
    """round(6.675, 2) da 6,67 porque 6,675 no se puede guardar exacto en coma flotante."""
    resultado = calcular(registro("MAT101", "aprobada", 6.675))

    assert como_decimal(resultado["nota_media"]) == Decimal("6.67")


# --- la nota media ---

def test_solo_convalidadas_da_media_0_aunque_haya_creditos():
    resultado = calcular(registro("MAT101", "convalidada"), registro("FIS101", "convalidada"))

    assert como_decimal(resultado["nota_media"]) == Decimal("0")
    assert resultado["creditos_superados"] == 12


def test_la_convalidacion_tiene_prioridad_sobre_la_aprobada_de_la_misma_asignatura():
    """MAT101 cuenta como convalidada y su 9,0 se ignora. Antes del refactor daba
    (5,0 x 6 + 7,0 x 6) / 6 = 12,0; con D-02 la convalidada no entra y la media es la de
    FIS101: 7,0."""
    resultado = calcular(registro("MAT101", "convalidada"), registro("MAT101", "aprobada", 9.0),
                         registro("FIS101", "aprobada", 7.0))

    assert como_decimal(resultado["nota_media"]) == Decimal("7.0")
    assert resultado["creditos_superados"] == 12


def test_cuenta_la_aprobada_de_mayor_convocatoria_aunque_sea_de_un_curso_anterior():
    resultado = calcular(registro("MAT101", "aprobada", 8.0, convocatoria=3, curso="2023-2024"),
                         registro("MAT101", "aprobada", 6.0, convocatoria=2, curso="2024-2025"))

    assert como_decimal(resultado["nota_media"]) == Decimal("8.0")


def test_una_aprobada_sin_nota_no_cuenta_en_la_media_pero_si_en_los_creditos():
    resultado = calcular(registro("MAT101", "aprobada", None), registro("FIS101", "aprobada", 7.0))

    assert como_decimal(resultado["nota_media"]) == Decimal("7.0")
    assert resultado["creditos_superados"] == 12


def test_una_asignatura_fuera_del_plan_se_ignora():
    resultado = calcular(registro("XXX999", "aprobada", 10.0), registro("MAT101", "aprobada", 6.0))

    assert como_decimal(resultado["nota_media"]) == Decimal("6.0")
    assert resultado["creditos_superados"] == 6


def test_media_ponderada_por_creditos():
    """(9,0 x 9 + 6,0 x 3) / 12 = 8,25."""
    resultado = calcular(registro("PRG101", "aprobada", 9.0), registro("ING101", "aprobada", 6.0))

    assert como_decimal(resultado["nota_media"]) == Decimal("8.25")


# --- creditos y progreso ---

def test_los_creditos_superados_cuentan_aprobadas_y_convalidadas_y_no_suspensas():
    """PRG101 (9) + ING101 (3) = 12 creditos; 12 x 100 / 192 = 6,25 %."""
    resultado = calcular(registro("PRG101", "aprobada", 7.0), registro("ING101", "convalidada"),
                         registro("ALG101", "suspensa", 3.0))

    assert resultado["creditos_superados"] == 12
    assert como_decimal(resultado["progreso_pct"]) == Decimal("6.25")


def test_el_progreso_redondea_el_empate_hacia_el_par():
    """6 x 100 / 192 = 3,125 exacto; round() de Python lleva el empate al par: 3,12."""
    resultado = calcular(registro("MAT101", "aprobada", 5.0))

    assert como_decimal(resultado["progreso_pct"]) == Decimal("3.12")


def test_un_expediente_vacio_da_ceros():
    resultado = calcular()

    assert como_decimal(resultado["nota_media"]) == Decimal("0")
    assert resultado["creditos_superados"] == 0
    assert como_decimal(resultado["progreso_pct"]) == Decimal("0")


# --- convocatorias ---

def test_las_convocatorias_cuentan_todo_menos_las_convalidaciones():
    suspensas = []
    for numero in range(1, 6):
        suspensas.append(registro("MAT101", "suspensa", 2.0, convocatoria=numero))
    datos = expediente(*suspensas, registro("MAT101", "no_presentado", convocatoria=6),
                       registro("FIS101", "convalidada"), registro("ALG101", "suspensa", 4.0))

    assert legado.convocatorias(datos) == {"MAT101": 6, "ALG101": 1}
    assert legado.puede_matricular(datos, "MAT101") is False     # 6 consumidas: el maximo
    assert legado.puede_matricular(datos, "ALG101") is True
    assert legado.puede_matricular(datos, "FIS101") is True      # la convalidacion no consume


# --- el punto de entrada del proceso nocturno ---

def test_la_cache_devuelve_el_resultado_antiguo_si_el_estudiante_cambia():
    """calcular() guarda el resultado por estudiante y plan: si el expediente cambia y se vuelve a
    calcular, devuelve el de antes."""
    datos = expediente(registro("MAT101", "aprobada", 6.0))
    primero = legado.calcular(datos, RUTA_PLAN)
    datos["registros"].append(registro("FIS101", "aprobada", 8.0))
    segundo = legado.calcular(datos, RUTA_PLAN)

    assert como_decimal(segundo["nota_media"]) == Decimal("6.0")
    assert segundo["creditos_superados"] == 6
    assert segundo == primero


def test_calcular_lote_devuelve_un_resultado_por_estudiante_en_el_mismo_orden():
    lote = [expediente(registro("MAT101", "aprobada", 6.0), estudiante="EST-A"),
            expediente(registro("FIS101", "aprobada", 8.0), estudiante="EST-B")]

    resultados = legado.calcular_lote(lote, RUTA_PLAN)

    identificadores = []
    for resultado in resultados:
        identificadores.append(resultado["estudiante_id"])
    assert identificadores == ["EST-A", "EST-B"]
    assert como_decimal(resultados[1]["nota_media"]) == Decimal("8.0")
    assert sorted(resultados[0].keys()) == ["creditos_superados", "estudiante_id", "nota_media",
                                            "progreso_pct"]
