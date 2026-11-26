"""Equivalencia del modulo heredado sobre el corpus de 500 expedientes.

Ejecuta el original congelado (tests/oraculo/calculadora_expediente_v1_original.py) y el modulo
actual (src/aula/legado/calculadora_expediente_v1.py) sobre datos/expedientes_sinteticos.json, y
compara nota_media, creditos_superados y progreso_pct expediente a expediente.

Una diferencia solo esta justificada si la explica una desviacion declarada en
src/aula/legado/DESVIACIONES.md:
  D-02  la convalidada no entra en la media: cambia la media de expedientes con convalidadas
  D-03  redondeo unico al final: la media cambia como mucho 0,01
  D-04  Decimal en vez de float: la media o el progreso cambian como mucho 0,01
Los creditos superados no tienen ninguna desviacion: tienen que coincidir siempre. Cualquier otra
diferencia es una desviacion sin justificar y el test falla.
"""
import hashlib
import importlib.util
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from aula.legado import calculadora_expediente_v1 as actual

RAIZ = Path(__file__).resolve().parents[1]
RUTA_ORACULO = RAIZ / "tests" / "oraculo" / "calculadora_expediente_v1_original.py"
RUTA_CORPUS = RAIZ / "datos" / "expedientes_sinteticos.json"
RUTA_PLAN = str(RAIZ / "datos" / "planes" / "PLAN-2024.json")
RUTA_DESVIACIONES = RAIZ / "src" / "aula" / "legado" / "DESVIACIONES.md"
# Blob de git del legado tal como llego en el primer commit del repositorio (5d2bd54).
BLOB_DEL_ORIGINAL = "343eebf51fc64155d95dbe048a93a1e739822d9f"
UN_CENTESIMO = Decimal("0.01")
NOTA_MAXIMA = Decimal("10")
CAMPOS = ["nota_media", "creditos_superados", "progreso_pct"]


def cargar_oraculo():
    especificacion = importlib.util.spec_from_file_location("legado_original", RUTA_ORACULO)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def vaciar_cache(modulo):
    cache = getattr(modulo, "_CACHE", None)
    if cache is not None:
        cache.clear()


def desviaciones_declaradas() -> list:
    if not RUTA_DESVIACIONES.exists():
        return []
    texto = RUTA_DESVIACIONES.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"D-\d\d", texto)))


def como_decimal(valor) -> Decimal:
    return Decimal(str(valor))


def tiene_convalidada(expediente: dict) -> bool:
    for registro in expediente["registros"]:
        if registro["estado"] == "convalidada":
            return True
    return False


def justificacion(campo, antes, despues, expediente, declaradas) -> str:
    """La desviacion declarada que explica la diferencia, o "" si ninguna la explica."""
    diferencia = abs(despues - antes)
    if campo == "nota_media":
        if "D-02" in declaradas and tiene_convalidada(expediente):
            return "D-02"
        redondeo = []
        for ident in ("D-03", "D-04"):
            if ident in declaradas:
                redondeo.append(ident)
        if redondeo and diferencia <= UN_CENTESIMO:
            return " o ".join(redondeo)
    if campo == "progreso_pct" and "D-04" in declaradas and diferencia <= UN_CENTESIMO:
        return "D-04"
    return ""


def comparar(oraculo, corpus: list, declaradas: list) -> tuple:
    """(resumen, sin_justificar): cuantos expedientes son identicos, cuantas diferencias explica
    cada desviacion y la lista de las que no explica ninguna."""
    resumen = {"identicos": 0}
    sin_justificar = []
    for expediente in corpus:
        original = oraculo.calcular(expediente, RUTA_PLAN)
        nuevo = actual.calcular(expediente, RUTA_PLAN)
        es_identico = True
        for campo in CAMPOS:
            antes = como_decimal(original[campo])
            despues = como_decimal(nuevo[campo])
            if antes == despues:
                continue
            es_identico = False
            motivo = justificacion(campo, antes, despues, expediente, declaradas)
            if not motivo:
                sin_justificar.append("%s %s: %s -> %s" % (expediente["estudiante_id"], campo,
                                                           antes, despues))
                continue
            clave = "%s (%s)" % (motivo, campo)
            resumen[clave] = resumen.get(clave, 0) + 1
        if es_identico:
            resumen["identicos"] += 1
    return resumen, sin_justificar


def test_el_oraculo_es_la_copia_exacta_del_original():
    datos = RUTA_ORACULO.read_bytes().replace(b"\r\n", b"\n")
    blob = hashlib.sha1(b"blob %d\0" % len(datos) + datos).hexdigest()

    assert blob == BLOB_DEL_ORIGINAL, "el oraculo se ha modificado: tiene que ser el original"


def test_equivalencia_sobre_el_corpus_sin_desviaciones_sin_justificar():
    corpus = json.loads(RUTA_CORPUS.read_text(encoding="utf-8"))
    oraculo = cargar_oraculo()
    vaciar_cache(oraculo)
    vaciar_cache(actual)
    declaradas = desviaciones_declaradas()

    resumen, sin_justificar = comparar(oraculo, corpus, declaradas)

    print("\nequivalencia sobre %d expedientes; declaradas: %s; %s"
          % (len(corpus), ", ".join(declaradas) or "ninguna", resumen))
    assert len(corpus) == 500
    assert sin_justificar == [], "desviaciones sin justificar: %s" % "; ".join(sin_justificar[:10])
    if "D-02" in declaradas:
        for expediente in corpus:
            assert como_decimal(actual.calcular(expediente, RUTA_PLAN)["nota_media"]) <= NOTA_MAXIMA


CONVALIDADA = {"registros": [{"estado": "convalidada"}]}
SIN_CONVALIDADA = {"registros": [{"estado": "aprobada"}]}


@pytest.mark.parametrize("campo, antes, despues, expediente, declaradas, esperada", [
    ("nota_media", "11.0", "6.00", CONVALIDADA, ["D-02"], "D-02"),
    ("nota_media", "11.0", "6.00", CONVALIDADA, [], ""),                 # sin declarar
    ("nota_media", "7.50", "7.20", SIN_CONVALIDADA, ["D-02"], ""),       # D-02 no la explica
    ("nota_media", "6.00", "6.01", SIN_CONVALIDADA, ["D-03"], "D-03"),
    ("nota_media", "6.00", "6.02", SIN_CONVALIDADA, ["D-03", "D-04"], ""),   # mas de 0,01
    ("progreso_pct", "3.12", "3.13", SIN_CONVALIDADA, ["D-04"], "D-04"),
    ("progreso_pct", "3.12", "3.13", SIN_CONVALIDADA, ["D-03"], ""),
    ("creditos_superados", "12", "18", CONVALIDADA, ["D-02", "D-03", "D-04"], ""),
])
def test_solo_una_desviacion_declarada_justifica_una_diferencia(campo, antes, despues, expediente,
                                                                declaradas, esperada):
    obtenida = justificacion(campo, Decimal(antes), Decimal(despues), expediente, declaradas)

    assert obtenida == esperada
