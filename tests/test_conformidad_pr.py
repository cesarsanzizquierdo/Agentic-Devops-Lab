"""Tests de herramientas/conformidad_pr.py: del cuerpo de un PR real al comentario con el veredicto."""
import pytest

from herramientas import conformidad_pr
from herramientas.conformidad_pr import comentario, main, metadatos

TEST_CA06 = {"ruta": "tests/test_media_expediente.py",
             "contenido": 'def test_progreso():\n    """cubre: SPEC-002/CA-06"""\n'
                          '    assert progreso(expediente, plan) == Decimal("7.81")\n'}


def test_lee_la_spec_y_los_criterios_del_cuerpo_del_pr():
    cuerpo = "Arregla el test.\n\nAULA_SPEC_ID: SPEC-002\nAULA_CRITERIOS: CA-05, CA-06\n"
    assert metadatos(cuerpo) == ("SPEC-002", ["CA-05", "CA-06"])


@pytest.mark.parametrize("cuerpo", [
    "Un PR de herramientas, sin spec.",
    "AULA_SPEC_ID: SPEC-0XX\nAULA_CRITERIOS: CA-0X\n",      # la plantilla sin rellenar
])
def test_sin_spec_declarada_no_hay_metadatos(cuerpo):
    with pytest.raises(ValueError):
        metadatos(cuerpo)


def test_un_pr_sin_spec_recibe_un_comentario_que_explica_como_declararla(tmp_path):
    cuerpo = tmp_path / "cuerpo.md"
    cuerpo.write_text("Un PR de herramientas, sin spec.", encoding="utf-8")
    salida = tmp_path / "comentario.md"

    codigo = main(["--base", "main", "--cuerpo", str(cuerpo), "--comentario", str(salida)])

    assert codigo == 2
    assert "sin spec declarada" in salida.read_text(encoding="utf-8")
    assert "AULA_SPEC_ID: SPEC-002" in salida.read_text(encoding="utf-8")


@pytest.mark.parametrize("ficheros, codigo_esperado, cabecera", [
    ([TEST_CA06], 0, ":white_check_mark: conforme"),
    ([], 1, ":x: no conforme"),
])
def test_publica_el_veredicto_del_agente(tmp_path, monkeypatch, ficheros, codigo_esperado, cabecera):
    # Sin git: los ficheros del diff se sustituyen por los de la prueba.
    monkeypatch.setattr(conformidad_pr, "archivos", lambda base: ficheros)
    cuerpo = tmp_path / "cuerpo.md"
    cuerpo.write_text("AULA_SPEC_ID: SPEC-002\nAULA_CRITERIOS: CA-06\n", encoding="utf-8")
    salida = tmp_path / "comentario.md"

    codigo = main(["--base", "main", "--cuerpo", str(cuerpo), "--comentario", str(salida),
                   "--salida", str(tmp_path / "pr.json")])

    assert codigo == codigo_esperado
    assert cabecera in salida.read_text(encoding="utf-8")


def test_el_comentario_lista_lo_que_falta():
    veredicto = {"veredicto": "no_conforme", "spec": "SPEC-002",
                 "criterios_declarados": ["CA-05", "CA-06"], "criterios_cubiertos": ["CA-06"],
                 "criterios_sin_cubrir": ["CA-05"], "fuera_de_alcance": ["src/aula/reglas/motor.py"],
                 "hallazgos": ["test_a no tiene ninguna asercion que compruebe algo"]}

    texto = comentario(veredicto)

    assert "| Sin test | CA-05 |" in texto
    assert "| Fuera de alcance | src/aula/reglas/motor.py |" in texto
    assert "- test_a no tiene ninguna asercion que compruebe algo" in texto
