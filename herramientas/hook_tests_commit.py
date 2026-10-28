"""Hook de tests antes de commit. Si la suite no esta en verde, no hay commit.

Claude Code lo ejecuta antes de cada comando de Bash y le pasa por stdin un JSON
con el comando. Si el comando es un "git commit", ejecuta pytest; si falla, sale
con codigo 2 y Claude Code cancela el commit.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PERMITIR = 0
BLOQUEAR = 2

# "git commit" seguido de espacio o fin de texto. Asi no confunde "git commit-tree".
PATRON_GIT_COMMIT = re.compile(r"\bgit\s+commit(\s|$)")

# El hook se lanza con el Python del sistema, que no tiene pytest ni fastapi.
# Por eso se busca el Python del entorno virtual del proyecto.
PYTHON_DEL_VENV_WINDOWS = RAIZ / ".venv" / "Scripts" / "python.exe"
PYTHON_DEL_VENV_LINUX = RAIZ / ".venv" / "bin" / "python"

LINEAS_DE_SALIDA_A_MOSTRAR = 15


def leer_comando_de_la_entrada(texto_entrada):
    """Extrae el comando de Bash del JSON que envia Claude Code. Devuelve "" si no hay."""
    try:
        entrada = json.loads(texto_entrada)
    except json.JSONDecodeError:
        return ""
    if not isinstance(entrada, dict):
        return ""

    datos_herramienta = entrada.get("tool_input") or {}
    return datos_herramienta.get("command", "")


def es_git_commit(comando):
    """True si el comando contiene un git commit."""
    return PATRON_GIT_COMMIT.search(comando) is not None


def python_del_proyecto():
    """Devuelve el Python del entorno virtual si existe, o el que ejecuta este hook."""
    if PYTHON_DEL_VENV_WINDOWS.exists():
        return str(PYTHON_DEL_VENV_WINDOWS)
    if PYTHON_DEL_VENV_LINUX.exists():
        return str(PYTHON_DEL_VENV_LINUX)
    return sys.executable


def ejecutar_tests():
    """Ejecuta la suite completa. Devuelve (en_verde, ultimas_lineas_de_salida)."""
    comando = [python_del_proyecto(), "-m", "pytest", "tests/", "-q"]
    resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)

    lineas = resultado.stdout.strip().splitlines()
    ultimas_lineas = "\n".join(lineas[-LINEAS_DE_SALIDA_A_MOSTRAR:])
    return resultado.returncode == 0, ultimas_lineas


def main():
    comando = leer_comando_de_la_entrada(sys.stdin.read())
    if not es_git_commit(comando):
        return PERMITIR

    en_verde, salida = ejecutar_tests()
    if en_verde:
        return PERMITIR

    print("bloqueado por hook_tests_commit: la suite no esta en verde. "
          "Arregla los tests antes de hacer commit.\n" + salida,
          file=sys.stderr)
    return BLOQUEAR


if __name__ == "__main__":
    sys.exit(main())
