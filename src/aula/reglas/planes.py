"""Carga de planes de estudio versionados."""
from __future__ import annotations

import json
from pathlib import Path

from ..dominio.modelos import Asignatura, Plan

RUTA_PLANES = Path(__file__).resolve().parents[3] / "datos" / "planes"


def cargar_plan(codigo: str, ruta: Path = None) -> Plan:
    base = ruta or RUTA_PLANES
    archivo = base / f"{codigo}.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    
    asignaturas_dict = {}
    for item in datos["asignaturas"]:
        asignatura_obj = Asignatura(
            codigo=item["codigo"],
            nombre=item["nombre"],
            creditos=item["creditos"],
            curso=item["curso"],
            prerrequisitos=tuple(item.get("prerrequisitos", []))
        )
        asignaturas_dict[item["codigo"]] = asignatura_obj
        
    return Plan(
        codigo=datos["codigo"],
        version=datos["version"],
        creditos_titulo=datos["creditos_titulo"],
        limite_creditos_curso=datos["limite_creditos_curso"],
        max_convocatorias=datos["max_convocatorias"],
        umbral_final_carrera=datos["umbral_final_carrera"],
        asignaturas=asignaturas_dict,
    )
