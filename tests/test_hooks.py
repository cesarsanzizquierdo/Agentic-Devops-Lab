"""Tests de los hooks de .claude/settings.json.

Cada test ejecuta el hook igual que Claude Code: un proceso aparte que recibe
un JSON por stdin y responde con su codigo de salida (0 permite, 2 bloquea).
"""
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HOOK_RUTAS = RAIZ / "herramientas" / "hook_rutas.py"
HOOK_FORMATO = RAIZ / "herramientas" / "hook_formato.py"
HOOK_TESTS_COMMIT = RAIZ / "herramientas" / "hook_tests_commit.py"

PERMITIDO = 0
BLOQUEADO = 2

RUTA_SETTINGS = RAIZ / ".claude" / "settings.json"

# Una regla "deny" por cada fila de la tabla de limites de CLAUDE.md.
REGLAS_DENY_OBLIGATORIAS = (
    "Edit(manifiestos/**)",
    "Edit(.github/workflows/**)",
    "Edit(labs/*/verificar.py)",
    "Edit(evals/dorado*/**)",
    "Edit(src/aula/legado/**)",
)

# Las reglas con las que trabaja el agente: puede cambiarlas, pero siempre preguntando.
REGLAS_ASK_OBLIGATORIAS = (
    "Edit(.claude/**)",
    "Edit(CLAUDE.md)",
)


def ejecutar_hook(hook, datos_herramienta):
    """Lanza el hook con el JSON que enviaria Claude Code y devuelve el proceso terminado."""
    entrada = json.dumps({"tool_input": datos_herramienta})
    return subprocess.run([sys.executable, str(hook)], input=entrada,
                          capture_output=True, text=True, cwd=RAIZ)


def codigo_hook_rutas(ruta):
    return ejecutar_hook(HOOK_RUTAS, {"file_path": str(ruta)}).returncode


def leer_permisos():
    """Devuelve el bloque "permissions" de .claude/settings.json."""
    configuracion = json.loads(RUTA_SETTINGS.read_text(encoding="utf-8"))
    return configuracion["permissions"]


def test_settings_prohibe_las_rutas_de_limites():
    """Si alguien borra una regla deny, el hook sigue funcionando y nadie lo notaria sin este test."""
    reglas_deny = leer_permisos()["deny"]
    for regla in REGLAS_DENY_OBLIGATORIAS:
        assert regla in reglas_deny, regla


def test_settings_pregunta_antes_de_cambiar_las_reglas_del_agente():
    """Si alguien quita la regla ask, el agente podria cambiar sus propias reglas sin preguntar."""
    reglas_ask = leer_permisos().get("ask", [])
    for regla in REGLAS_ASK_OBLIGATORIAS:
        assert regla in reglas_ask, regla


def test_hook_rutas_bloquea_manifiestos_con_barras_normales():
    assert codigo_hook_rutas("manifiestos/agente.yaml") == BLOQUEADO


def test_hook_rutas_bloquea_manifiestos_con_barras_de_windows():
    assert codigo_hook_rutas("manifiestos\\agente.yaml") == BLOQUEADO


def test_hook_rutas_bloquea_ruta_absoluta_del_proyecto():
    ruta_absoluta = RAIZ / "manifiestos" / "agente.yaml"
    assert codigo_hook_rutas(ruta_absoluta) == BLOQUEADO


def test_hook_rutas_bloquea_todas_las_rutas_de_limites():
    rutas_protegidas = [
        ".github/workflows/ci.yml",
        "labs/S3-contexto/verificar.py",
        "evals/dorado-v1/casos.json",
        "src/aula/legado/calculo.py",
    ]
    for ruta in rutas_protegidas:
        assert codigo_hook_rutas(ruta) == BLOQUEADO, ruta


def test_hook_rutas_deja_pasar_las_reglas_del_agente_porque_se_preguntan():
    # .claude/ y CLAUDE.md no se bloquean: la regla "ask" de settings.json pide confirmacion.
    assert codigo_hook_rutas(".claude/agents/revisor.md") == PERMITIDO
    assert codigo_hook_rutas("CLAUDE.md") == PERMITIDO


def test_hook_rutas_no_se_engana_con_rodeos():
    assert codigo_hook_rutas("src/../manifiestos/agente.yaml") == BLOQUEADO


def test_hook_rutas_permite_el_resto_de_labs():
    assert codigo_hook_rutas("labs/S3-contexto/comparativa.md") == PERMITIDO
    assert codigo_hook_rutas("labs/S3-contexto/bitacora.md") == PERMITIDO


def test_hook_rutas_permite_codigo_normal():
    assert codigo_hook_rutas("src/aula/reglas/motor.py") == PERMITIDO


def test_hook_rutas_permite_si_la_entrada_no_es_json():
    proceso = subprocess.run([sys.executable, str(HOOK_RUTAS)], input="esto no es json",
                             capture_output=True, text=True, cwd=RAIZ)
    assert proceso.returncode == PERMITIDO


def test_hook_formato_quita_espacios_finales_y_anade_salto_final(tmp_path):
    fichero = tmp_path / "ejemplo.py"
    fichero.write_text("x = 1   \ny = 2", encoding="utf-8")

    proceso = ejecutar_hook(HOOK_FORMATO, {"file_path": str(fichero)})

    assert proceso.returncode == PERMITIDO
    assert fichero.read_text(encoding="utf-8") == "x = 1\ny = 2\n"


def test_hook_formato_no_toca_ficheros_que_no_son_python(tmp_path):
    fichero = tmp_path / "notas.md"
    fichero.write_text("texto   ", encoding="utf-8")

    ejecutar_hook(HOOK_FORMATO, {"file_path": str(fichero)})

    assert fichero.read_text(encoding="utf-8") == "texto   "


def test_hook_tests_commit_ignora_comandos_que_no_son_commit():
    # No lanza pytest: si lo hiciera, este test tardaria lo que tarda la suite.
    proceso = ejecutar_hook(HOOK_TESTS_COMMIT, {"command": "git status"})
    assert proceso.returncode == PERMITIDO


def test_hook_tests_commit_no_confunde_commit_tree():
    proceso = ejecutar_hook(HOOK_TESTS_COMMIT, {"command": "git commit-tree abc123"})
    assert proceso.returncode == PERMITIDO
