"""Tests de los subagentes de .claude/agents/.

Comprueban que cada subagente tiene las herramientas que su rol permite y
ninguna mas. Un revisor con permiso de escritura dejaria de ser independiente.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_AGENTES = RAIZ / ".claude" / "agents"

HERRAMIENTAS_DE_ESCRITURA = ("Edit", "Write", "MultiEdit", "NotebookEdit", "Bash")


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


def test_el_revisor_es_de_solo_lectura():
    herramientas = herramientas_de("revisor.md")
    for herramienta in HERRAMIENTAS_DE_ESCRITURA:
        assert herramienta not in herramientas, herramienta


def test_el_revisor_puede_leer_para_dar_contexto():
    herramientas = herramientas_de("revisor.md")
    assert "Read" in herramientas
    assert "Grep" in herramientas


def test_el_implementador_puede_editar_y_ejecutar_tests():
    herramientas = herramientas_de("implementador.md")
    assert "Edit" in herramientas
    assert "Bash" in herramientas
