"""Calculadora de expediente heredada: nota media, creditos superados y progreso.

La usa el proceso nocturno de secretaria a traves de calcular() y calcular_lote(), y de ella
depende la ordenacion de becas. Su comportamiento esta fijado en
tests/test_caracterizacion_legado.py; cada diferencia con el original
(tests/oraculo/calculadora_expediente_v1_original.py) se declara en DESVIACIONES.md.

Historico (lo poco que se sabe):
  2019-03  version inicial
  2020-11  parche convalidaciones (jlm)
  2021-06  ajuste redondeo por peticion de secretaria
  2023-01  se anade progreso, sin tocar la media
  2026-11  S5: caracterizacion, equivalencia sobre 500 expedientes y refactor
"""
import json
from decimal import ROUND_HALF_UP, Decimal

# D-04: todo con Decimal y redondeo half-up (invariante 2).
DOS_DECIMALES = Decimal("0.01")
CERO = Decimal("0.00")
# Repite max_convocatorias de PLAN-2024; ver la deuda conocida en DESVIACIONES.md.
MAX_CONV = 6


# --- el plan ---------------------------------------------------------------------

def cargar_plan(ruta):
    """Lee el plan: devuelve (plan, {codigo: asignatura})."""
    with open(ruta, "r", encoding="utf-8") as fichero:
        plan = json.load(fichero)
    asignaturas = {}
    for asignatura in plan["asignaturas"]:
        asignaturas[asignatura["codigo"]] = asignatura
    return plan, asignaturas


def creditos_de(asignaturas, codigo):
    """Creditos de la asignatura en el plan; 0 si no pertenece al plan."""
    if codigo in asignaturas:
        return asignaturas[codigo]["creditos"]
    return 0


# --- las reglas de una asignatura ------------------------------------------------

def registros_por_asignatura(expediente):
    """{codigo: [registros]}, en el orden en que aparece cada asignatura por primera vez.

    El orden importa: la media suma en coma flotante, y sumar en otro orden podria cambiar el
    ultimo decimal.
    """
    agrupados = {}
    for registro in expediente["registros"]:
        codigo = registro["codigo_asignatura"]
        if codigo not in agrupados:
            agrupados[codigo] = []
        agrupados[codigo].append(registro)
    return agrupados


def esta_convalidada(registros):
    for registro in registros:
        if registro["estado"] == "convalidada":
            return True
    return False


def esta_superada(registros):
    """Aprobada o convalidada en algun registro: sus creditos cuentan como superados."""
    for registro in registros:
        if registro["estado"] in ("aprobada", "convalidada"):
            return True
    return False


def ultima_aprobada(registros):
    """El registro aprobado de mayor convocatoria (con empate, el primero), o None."""
    elegido = None
    for registro in registros:
        if registro["estado"] != "aprobada":
            continue
        if elegido is None or registro["convocatoria"] > elegido["convocatoria"]:
            elegido = registro
    return elegido


def nota_que_cuenta(registros):
    """La nota de la ultima aprobada, sin redondear, o None si no hay ninguna con nota.

    D-03: ya no se redondea por asignatura; la media se redondea una sola vez, al final.
    """
    aprobada = ultima_aprobada(registros)
    if aprobada is None or aprobada.get("nota") is None:
        return None
    return Decimal(str(aprobada["nota"]))


def redondear(valor):
    return valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


# --- los calculos del expediente -------------------------------------------------

def media(expediente, asignaturas):
    """Media ponderada por creditos de las asignaturas con nota, como Decimal."""
    numerador = Decimal("0")
    denominador = 0
    for codigo, registros in registros_por_asignatura(expediente).items():
        creditos = creditos_de(asignaturas, codigo)
        if creditos == 0:
            continue     # fuera del plan
        if esta_convalidada(registros):
            continue     # D-02: la convalidada no entra en la media (SPEC-002 CA-03)
        nota = nota_que_cuenta(registros)
        if nota is None:
            continue
        numerador = numerador + nota * creditos
        denominador = denominador + creditos
    if denominador == 0:
        return CERO
    return redondear(numerador / denominador)


def creditos_superados(expediente, asignaturas):
    total = 0
    for codigo, registros in registros_por_asignatura(expediente).items():
        if esta_superada(registros):
            total = total + creditos_de(asignaturas, codigo)
    return total


def progreso(expediente, plan, asignaturas):
    """Porcentaje de creditos superados sobre los del titulo, como Decimal."""
    creditos_del_titulo = plan["creditos_titulo"]
    if creditos_del_titulo == 0:
        return CERO
    superados = creditos_superados(expediente, asignaturas)
    return redondear(Decimal(superados) * 100 / Decimal(creditos_del_titulo))


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
    """False si ya se han consumido MAX_CONV convocatorias de la asignatura."""
    return convocatorias(expediente).get(codigo, 0) < MAX_CONV


# --- puntos de entrada del proceso nocturno --------------------------------------

def calcular(expediente, ruta_plan):
    """Resultado de un estudiante, calculado siempre con su expediente actual (D-05)."""
    plan, asignaturas = cargar_plan(ruta_plan)
    return {
        "estudiante_id": expediente["estudiante_id"],
        "nota_media": media(expediente, asignaturas),
        "creditos_superados": creditos_superados(expediente, asignaturas),
        "progreso_pct": progreso(expediente, plan, asignaturas),
    }


def calcular_lote(expedientes, ruta_plan):
    resultados = []
    for expediente in expedientes:
        resultados.append(calcular(expediente, ruta_plan))
    return resultados
