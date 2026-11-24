"""Tests de las decisiones del coordinador (conflicto, handoff, ciclo incompleto) y de la grabacion."""
import json
from pathlib import Path

import pytest

from agentes.flotilla import grabacion
from agentes.flotilla.contrato import cargar
from agentes.flotilla.decisiones import decidir_ciclo, revisar_resultado

CONTRATO = cargar()
MEDIA = "src/aula/reglas/media.py"
LEGADO = "src/aula/legado/calculadora_expediente_v1.py"


def ejecucion(agente: str, codigo, salida) -> dict:
    return {"agente": agente, "carpeta": "/wt/" + agente, "codigo": codigo, "stdout": json.dumps(salida),
            "stderr": "", "inicio": 0.0, "fin": 1.0}


def triaje(estado: str, propone: list) -> dict:
    return {"agente": "triaje-pipeline", "raiz": "/wt", "estado": estado, "resumen": "1 failed",
            "fallos": [], "propone_tocar": propone}


def modernizacion(propone: list) -> dict:
    return {"agente": "modernizacion-legado", "raiz": "/wt", "modulos": [], "hallazgos": [],
            "pasos": ["Caracterizar"], "propone_tocar": propone}


def decidir(*ejecuciones) -> dict:
    resultados = []
    for una in ejecuciones:
        resultados.append(revisar_resultado(CONTRATO, una))
    return decidir_ciclo(resultados, CONTRATO)


def test_si_dos_proponen_el_mismo_fichero_gana_triaje_y_se_pospone_modernizacion():
    ciclo = decidir(ejecucion("triaje-pipeline", 1, triaje("rojo", [MEDIA])),
                    ejecucion("modernizacion-legado", 0, modernizacion([LEGADO, MEDIA])))

    assert ciclo["estado"] == "completo"
    assert ciclo["conflictos"] == [{"fichero": MEDIA, "gana": "triaje-pipeline",
                                    "se_pospone": ["modernizacion-legado"]}]


def test_triaje_solo_pasa_la_incidencia_al_humano_si_no_esta_en_verde():
    en_verde = decidir(ejecucion("triaje-pipeline", 0, triaje("verde", [])))
    en_rojo = decidir(ejecucion("triaje-pipeline", 1, triaje("rojo", [MEDIA])))

    assert en_verde["handoffs"] == []
    assert en_rojo["handoffs"][0]["a"] == "humano"
    assert en_rojo["handoffs"][0]["datos"]["propone_tocar"] == [MEDIA]


@pytest.mark.parametrize("codigo, stdout, motivo", [
    (None, "", "no acabo a tiempo"),
    (5, json.dumps(triaje("rojo", [MEDIA])), "codigo 5, que su contrato no declara"),
    (1, "Traceback ...", "no devolvio JSON"),
    (1, json.dumps({"estado": "rojo"}), "le falta agente"),
])
def test_si_un_agente_falla_el_ciclo_es_incompleto_y_no_decide_conflictos(codigo, stdout, motivo):
    roto = {"agente": "triaje-pipeline", "carpeta": "/wt", "codigo": codigo, "stdout": stdout,
            "stderr": "", "inicio": 0.0, "fin": 1.0}
    ciclo = decidir(roto, ejecucion("modernizacion-legado", 0, modernizacion([MEDIA])))

    assert ciclo["estado"] == "incompleto"
    assert motivo in ciclo["motivos"][0]
    assert ciclo["conflictos"] == []
    assert ciclo["handoffs"][0]["de"] == "modernizacion-legado"     # el sano si llega


def test_la_grabacion_no_lleva_rutas_personales():
    casa = str(Path.home())
    texto = grabacion.sin_rutas_personales({"carpeta": [casa + "/aula-flotilla/triaje-pipeline"]})

    assert texto == {"carpeta": ["~/aula-flotilla/triaje-pipeline"]}
