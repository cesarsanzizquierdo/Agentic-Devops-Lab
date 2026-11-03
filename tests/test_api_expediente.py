"""Pruebas de la API de expediente para SPEC-002 (serializacion JSON).

TestClient necesita httpx, que no esta en requirements.txt, asi que se invoca
el manejador del endpoint directamente y se serializa con json.dumps.
"""
import json
from decimal import Decimal

import pytest

from aula.api import app as api
from aula.dominio.modelos import EstadoRegistro, Expediente, RegistroAcademico


def registro(codigo: str, nota: str) -> RegistroAcademico:
    return RegistroAcademico(
        codigo_asignatura=codigo,
        curso_academico="2025-2026",
        convocatoria=1,
        estado=EstadoRegistro("aprobada"),
        nota=Decimal(nota),
    )


@pytest.fixture
def consultar(monkeypatch):
    def _consultar(estudiante_id: str, notas: dict[str, str]) -> str:
        registros = [registro(codigo, nota) for codigo, nota in notas.items()]
        expediente = Expediente(estudiante_id, api.PLAN_ACTUAL.codigo, registros)
        monkeypatch.setitem(api.BD_EXPEDIENTES, estudiante_id, expediente)
        return json.dumps(api.ver_expediente(estudiante_id))

    return _consultar


def test_spec002_ca08_siete_exacto_sale_con_dos_decimales(consultar):
    """cubre: SPEC-002/CA-08. Un 7 exacto se serializa como string "7.00"."""
    cuerpo = json.loads(consultar("EST-API-1", {"MAT101": "7.00", "PRG101": "7.00"}))

    assert cuerpo["nota_media"] == "7.00"


def test_spec002_ca08_valores_son_string_y_no_float(consultar):
    """cubre: SPEC-002/CA-08. Con float saldria 6.8 (numero): debe salir "6.80" (string)."""
    texto = consultar("EST-API-2", {"MAT101": "8.00", "PRG101": "6.00"})
    cuerpo = json.loads(texto)

    assert cuerpo["nota_media"] == "6.80"
    assert '"nota_media": "6.80"' in texto
    for campo in ("nota_media", "progreso", "progreso_pct"):
        assert isinstance(cuerpo[campo], str)


def test_spec002_ca08_progreso_pct_es_alias_de_progreso(consultar):
    """cubre: SPEC-002/CA-08. 15 creditos de 192 = 7.8125 -> "7.81" en ambos campos."""
    cuerpo = json.loads(consultar("EST-API-3", {"MAT101": "8.00", "PRG101": "6.00"}))

    assert cuerpo["progreso"] == "7.81"
    assert cuerpo["progreso_pct"] == cuerpo["progreso"]
