"""Tests de los subagentes de .claude/agents/.

Comprueban que cada subagente tiene las herramientas que su rol permite y
ninguna mas. Un revisor que pudiera escribir podria arreglar lo que critica: quien
revisa no debe ser quien escribe.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_AGENTES = RAIZ / ".claude" / "agents"

HERRAMIENTAS_DEL_REVISOR = {"Read", "Grep", "Glob"}
HERRAMIENTAS_DEL_IMPLEMENTADOR = {"Read", "Grep", "Glob", "Edit", "Write", "Bash"}

MODELO_DEL_REVISOR = "opus"
MODELO_DEL_IMPLEMENTADOR = "sonnet"


def leer_cabecera(nombre_fichero):
    """Devuelve los campos de la cabecera (entre las dos lineas "---") como diccionario."""
    texto = (CARPETA_AGENTES / nombre_fichero).read_text(encoding="utf-8")
    lineas = texto.splitlines()
    assert lineas[0] == "---", "el fichero debe empezar por una cabecera ---"

    campos = {}
    for linea in lineas[1:]:
        if linea == "---":
            break
        nombre, separador, valor = linea.partition(":")
        if separador:
            campos[nombre.strip()] = valor.strip()
    return campos


def herramientas_de(nombre_fichero):
    """Devuelve la lista de herramientas que declara el subagente."""
    cabecera = leer_cabecera(nombre_fichero)
    herramientas = []
    for herramienta in cabecera["tools"].split(","):
        herramientas.append(herramienta.strip())
    return herramientas


def test_los_dos_subagentes_declaran_nombre_y_descripcion():
    for fichero in ("implementador.md", "revisor.md"):
        cabecera = leer_cabecera(fichero)
        assert cabecera["name"] == fichero.removesuffix(".md")
        assert cabecera["description"], fichero


def test_el_revisor_tiene_exactamente_sus_herramientas():
    assert set(herramientas_de("revisor.md")) == HERRAMIENTAS_DEL_REVISOR


def test_el_implementador_tiene_exactamente_sus_herramientas():
    assert set(herramientas_de("implementador.md")) == HERRAMIENTAS_DEL_IMPLEMENTADOR


def test_los_subagentes_fijan_su_modelo():
    """Sin la linea model el subagente hereda el modelo de la sesion."""
    assert leer_cabecera("revisor.md").get("model") == MODELO_DEL_REVISOR
    assert leer_cabecera("implementador.md").get("model") == MODELO_DEL_IMPLEMENTADOR
