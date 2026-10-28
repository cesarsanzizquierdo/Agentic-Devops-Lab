"""Servicio de arranque. S1 y S2 completan los recursos pendientes."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ..dominio.modelos import SolicitudMatricula, Expediente, RegistroAcademico, EstadoRegistro
from ..reglas.motor import evaluar_solicitud, VentanaMatricula, VentanaCerrada
from ..reglas.planes import cargar_plan
from decimal import Decimal
from ..reglas.media import resumen_expediente

app = FastAPI(title="Aula Students", version="0.0.0")

# Persistencia en memoria
BD_MATRICULAS = {}
BD_EXPEDIENTES = {}

# Configuracion base
RUTA_DATOS = Path(__file__).resolve().parents[3] / "datos"
PLAN_ACTUAL = cargar_plan("PLAN-2024", RUTA_DATOS / "planes")
VENTANA_ACTUAL = VentanaMatricula("2020-01-01T00:00:00", "2030-12-31T23:59:59")
GRUPOS_ACTUALES = {}

# Carga de expedientes sinteticos en memoria al arrancar
try:
    archivo_expedientes = RUTA_DATOS / "expedientes_sinteticos.json"
    datos_estudiantes = json.loads(archivo_expedientes.read_text(encoding="utf-8"))
    
    for datos_alumno in datos_estudiantes:
        registros_historial = []

        for reg in datos_alumno["registros"]:
            if reg["nota"] is not None:
                nota_decimal = Decimal(str(reg["nota"]))
            else:
                nota_decimal = None

            nuevo_registro = RegistroAcademico(
                codigo_asignatura=reg["codigo_asignatura"],
                curso_academico=reg["curso_academico"],
                convocatoria=reg["convocatoria"],
                estado=EstadoRegistro(reg["estado"]),
                nota=nota_decimal
            )
            registros_historial.append(nuevo_registro)
            
        estudiante_id = datos_alumno["estudiante_id"]
        plan_alumno = datos_alumno["plan"]
        BD_EXPEDIENTES[estudiante_id] = Expediente(estudiante_id, plan_alumno, registros_historial)
        
except FileNotFoundError:
    pass

class SolicitudEntrada(BaseModel):
    estudiante_id: str
    curso_academico: str
    codigos: list[str]
    momento: str | None = None


@app.get("/salud")
def salud():
    return {"estado": "ok", "momento": datetime.now(timezone.utc).isoformat()}


@app.post("/matriculas")
def crear_matricula(entrada: SolicitudEntrada):
    momento_solicitud = entrada.momento or datetime.now(timezone.utc).isoformat()
    
    solicitud = SolicitudMatricula(
        estudiante_id=entrada.estudiante_id,
        curso_academico=entrada.curso_academico,
        codigos=entrada.codigos,
        momento=momento_solicitud
    )
    
    expediente = BD_EXPEDIENTES.get(
        entrada.estudiante_id, 
        Expediente(entrada.estudiante_id, PLAN_ACTUAL.codigo, [])
    )
    try:
        matricula = evaluar_solicitud(
            solicitud=solicitud,
            expediente=expediente,
            plan=PLAN_ACTUAL,
            ventana=VENTANA_ACTUAL,
            grupos=GRUPOS_ACTUALES
        )
        BD_MATRICULAS[entrada.estudiante_id] = matricula
        return matricula
    except (VentanaCerrada, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    #raise HTTPException(status_code=501, detail="S1: alta de matricula pendiente")


@app.get("/expedientes/{estudiante_id}")
def ver_expediente(estudiante_id: str):
    if estudiante_id not in BD_EXPEDIENTES:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    expediente_alumno = BD_EXPEDIENTES[estudiante_id]
    datos_resumen = resumen_expediente(expediente_alumno, PLAN_ACTUAL)

    respuesta = {
        "estudiante_id": datos_resumen["estudiante_id"],
        "plan": datos_resumen["plan"],
        "nota_media": float(datos_resumen["nota_media"]),
        "creditos_superados": datos_resumen["creditos_superados"],
        "progreso": float(datos_resumen["progreso"]),
        "progreso_pct": float(datos_resumen["progreso_pct"]),
        "convocatorias": datos_resumen["convocatorias"],
    }
    return respuesta