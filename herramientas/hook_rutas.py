"""Hook de rutas prohibidas. Determinista, no negociable con el agente.

Lo innegociable no se pide en lenguaje natural: se hace determinista. Este hook
es lo que convierte la seccion de limites de CLAUDE.md en un control real.

Claude Code lo ejecuta antes de cada escritura y le pasa por stdin un JSON con
la ruta del fichero. Si la ruta esta protegida, el hook sale con codigo 2 y
Claude Code cancela la escritura.
"""
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PERMITIR = 0
BLOQUEAR = 2

# Carpetas protegidas segun la tabla de limites de CLAUDE.md.
# "evals/dorado" no lleva barra final porque protege evals/dorado*/.
PREFIJOS_PROTEGIDOS = (
    "manifiestos/",
    ".github/workflows/",
    "evals/dorado",
    "src/aula/legado/",
)


def leer_ruta_de_la_entrada(texto_entrada):
    """Extrae la ruta del fichero del JSON que envia Claude Code. Devuelve "" si no hay."""
    try:
        entrada = json.loads(texto_entrada)
    except json.JSONDecodeError:
        return ""
    if not isinstance(entrada, dict):
        return ""

    datos_herramienta = entrada.get("tool_input") or {}
    ruta = datos_herramienta.get("file_path")
    if not ruta:
        ruta = datos_herramienta.get("notebook_path", "")
    return ruta


def ruta_relativa_al_proyecto(ruta_recibida):
    """Convierte la ruta a relativa a la raiz, en minusculas y con barras "/".

    Devuelve None si la ruta queda fuera del proyecto.
    En Windows la ruta llega con barras invertidas (C:\\...\\manifiestos\\x.yaml).
    Se normaliza para que una misma carpeta se reconozca se escriba como se escriba.
    """
    ruta = Path(ruta_recibida)
    if not ruta.is_absolute():
        ruta = RAIZ / ruta

    # abspath resuelve trucos como "src/../manifiestos/x"; normcase iguala mayusculas en Windows.
    ruta_texto = os.path.normcase(os.path.abspath(ruta))
    raiz_texto = os.path.normcase(os.path.abspath(RAIZ))

    if not ruta_texto.startswith(raiz_texto + os.sep):
        return None

    relativa = ruta_texto[len(raiz_texto) + 1:]
    relativa = relativa.replace("\\", "/")
    return relativa.lower()


def es_verificador_de_laboratorio(relativa):
    """True si la ruta es labs/<estacion>/verificar.py, la vara de medir del laboratorio."""
    partes = relativa.split("/")
    if len(partes) != 3:
        return False
    return partes[0] == "labs" and partes[2] == "verificar.py"


def es_ruta_prohibida(ruta_recibida):
    """True si la ruta esta en la tabla de limites de CLAUDE.md."""
    relativa = ruta_relativa_al_proyecto(ruta_recibida)
    if relativa is None:
        return False

    for prefijo in PREFIJOS_PROTEGIDOS:
        if relativa.startswith(prefijo):
            return True

    return es_verificador_de_laboratorio(relativa)


def main():
    ruta = leer_ruta_de_la_entrada(sys.stdin.read())
    if not ruta:
        return PERMITIR

    if es_ruta_prohibida(ruta):
        print("bloqueado por hook_rutas: %s esta en la lista de limites de "
              "CLAUDE.md. Requiere aprobacion humana explicita." % ruta,
              file=sys.stderr)
        return BLOQUEAR

    return PERMITIR


if __name__ == "__main__":
    sys.exit(main())
