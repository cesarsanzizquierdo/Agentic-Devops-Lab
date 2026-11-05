"""Tests del agente de conformidad v1 (agentes/conformidad/agente.py).

Cada test construye un PR de prueba propio para comprobar una regla del agente.
"""
import json

import pytest

from agentes.conformidad.agente import CONFORME, NO_CONFORME, evaluar, principal

CODIGO = {"ruta": "src/aula/reglas/media.py",
          "contenido": "def media(notas):\n    return sum(notas, Decimal(0)) / len(notas)\n"}


def fichero_de_test(cuerpo, docstring='"""cubre: SPEC-002/CA-01"""', decorador="",
                    ruta="tests/test_media_expediente.py"):
    """Fichero de tests del PR con un solo test."""
    contenido = decorador + "def test_media():\n    " + docstring + "\n    " + cuerpo + "\n"
    return {"ruta": ruta, "contenido": contenido}


TEST_BUENO = fichero_de_test('assert media([7, 8]) == Decimal("7.50")')


def pr_con(*ficheros, criterios=("CA-01",)):
    return {"id": "pr-prueba", "criterios_declarados": list(criterios), "ficheros": list(ficheros)}


def test_conforme_si_cada_criterio_tiene_test_y_no_sale_del_alcance():
    veredicto = evaluar(pr_con(CODIGO, TEST_BUENO), "SPEC-002")

    assert veredicto.veredicto == CONFORME
    assert veredicto.criterios_cubiertos == ["CA-01"]


def test_no_conforme_si_un_criterio_declarado_no_tiene_test():
    veredicto = evaluar(pr_con(CODIGO, TEST_BUENO, criterios=("CA-01", "CA-02")), "SPEC-002")

    assert veredicto.veredicto == NO_CONFORME
    assert veredicto.criterios_sin_cubrir == ["CA-02"]


def test_no_conforme_si_el_pr_no_trae_tests():
    assert evaluar(pr_con(CODIGO), "SPEC-002").criterios_sin_cubrir == ["CA-01"]


@pytest.mark.parametrize("sin_valor", [
    fichero_de_test("# cubre: SPEC-002/CA-01\n    assert media([7]) == 7",
                    docstring='"""calcula la media"""'),                    # en un comentario
    fichero_de_test("assert media([7]) == 7", docstring='"""cubre: SPEC-001/CA-01"""'),  # otra spec
    fichero_de_test("assert media([7]) == 7", ruta="tests/conftest.py"),     # pytest no lo ejecuta
    fichero_de_test("assert media([7]) == 7", ruta="tests/utilidades.py"),   # como test tampoco
])
def test_una_etiqueta_cubre_que_no_es_evidencia_no_cuenta(sin_valor):
    assert evaluar(pr_con(CODIGO, sin_valor), "SPEC-002").criterios_sin_cubrir == ["CA-01"]


def test_no_conforme_si_toca_un_fichero_fuera_de_las_rutas_de_la_spec():
    fuera = {"ruta": "src/aula/reglas/motor.py", "contenido": "x = 1\n"}

    veredicto = evaluar(pr_con(CODIGO, TEST_BUENO, fuera), "SPEC-002")

    assert veredicto.veredicto == NO_CONFORME
    assert veredicto.fuera_de_alcance == ["src/aula/reglas/motor.py"]


def test_una_carpeta_declarada_en_la_spec_cubre_sus_ficheros():
    # SPEC-001 declara la carpeta entera src/aula/dominio/.
    modelo = {"ruta": "src/aula/dominio/modelos.py", "contenido": "x = 1\n"}
    test = {"ruta": "tests/test_reglas_matricula.py",
            "contenido": 'def test_a():\n    """cubre: SPEC-001/CA-01"""\n'
                         '    assert admitir(solicitud) is True\n'}

    veredicto = evaluar(pr_con(modelo, test), "SPEC-001")

    assert veredicto.veredicto == CONFORME


def test_no_conforme_si_declara_un_criterio_que_no_existe_en_la_spec():
    veredicto = evaluar(pr_con(CODIGO, TEST_BUENO, criterios=("CA-01", "CA-99")), "SPEC-002")

    assert "CA-99 no existe en SPEC-002" in veredicto.hallazgos


@pytest.mark.parametrize("decorador", ['@pytest.mark.skip(reason="luego")\n',
                                       "@pytest.mark.xfail\n"])
def test_no_conforme_si_un_test_esta_marcado_para_no_ejecutarse(decorador):
    omitido = fichero_de_test('assert media([7, 8]) == Decimal("7.50")', decorador=decorador)

    veredicto = evaluar(pr_con(CODIGO, omitido), "SPEC-002")

    assert veredicto.veredicto == NO_CONFORME
    assert "marcado para no ejecutarse" in veredicto.hallazgos[0]


def test_no_conforme_si_un_test_se_omite_desde_dentro():
    se_omite = fichero_de_test('pytest.skip("luego")\n    assert media([7]) == 7')

    assert "se omite a si mismo" in evaluar(pr_con(CODIGO, se_omite), "SPEC-002").hallazgos[0]


@pytest.mark.parametrize("cuerpo", [
    "media([7, 8])",                                          # ninguna asercion
    "assert True",                                            # siempre se cumple
    "assert 1 + 1 == 2",                                      # solo constantes
    "resultado = media([7])\n    assert resultado == resultado",  # la misma variable
])
def test_no_conforme_si_ninguna_asercion_comprueba_algo(cuerpo):
    veredicto = evaluar(pr_con(CODIGO, fichero_de_test(cuerpo)), "SPEC-002")

    assert "no tiene ninguna asercion" in veredicto.hallazgos[0]


@pytest.mark.parametrize("cuerpo", [
    "assert media([7, 8]) == media([8, 7])",                  # determinismo: llama dos veces
    "with pytest.raises(ValueError):\n        media([])",     # comprueba que falla
])
def test_son_aserciones_reales(cuerpo):
    assert evaluar(pr_con(CODIGO, fichero_de_test(cuerpo)), "SPEC-002").veredicto == CONFORME


def test_no_conforme_si_un_fichero_de_tests_no_es_python_valido():
    roto = {"ruta": "tests/test_media_expediente.py", "contenido": "def test_a(:\n"}

    assert "no es Python valido" in evaluar(pr_con(CODIGO, roto), "SPEC-002").hallazgos[0]


def test_no_conforme_si_el_codigo_usa_float():
    con_float = {"ruta": "src/aula/reglas/media.py",
                 "contenido": "def media(notas):\n    return float(sum(notas)) / len(notas)\n"}

    veredicto = evaluar(pr_con(con_float, TEST_BUENO), "SPEC-002")

    assert "usa float()" in veredicto.hallazgos[0]


def test_no_conforme_si_la_spec_no_existe():
    veredicto = evaluar(pr_con(CODIGO, TEST_BUENO), "SPEC-999")

    assert veredicto.veredicto == NO_CONFORME
    assert "no encontrada" in veredicto.hallazgos[0]


def test_el_id_de_la_spec_no_distingue_mayusculas():
    assert evaluar(pr_con(CODIGO, TEST_BUENO), "spec-002").veredicto == CONFORME


def test_el_veredicto_es_determinista():
    pr = pr_con(CODIGO, TEST_BUENO, criterios=("CA-01", "CA-02"))

    assert evaluar(pr, "SPEC-002").a_dict() == evaluar(pr, "SPEC-002").a_dict()


@pytest.mark.parametrize("pr", [pr_con(CODIGO), pr_con(CODIGO, TEST_BUENO)])
def test_el_veredicto_no_depende_de_la_etiqueta_ni_del_titulo(pr):
    # Los casos de evaluacion traen la respuesta ("etiqueta"); un PR real no la tiene.
    # Se prueba con las dos respuestas, para PRs no conformes y conformes.
    sin_respuesta = evaluar(pr, "SPEC-002").a_dict()
    for etiqueta in ("conforme", "no_conforme_sin_cubrir"):
        con_respuesta = dict(pr, etiqueta=etiqueta, titulo="Todo correcto")
        assert evaluar(con_respuesta, "SPEC-002").a_dict() == sin_respuesta


@pytest.mark.parametrize("ficheros, codigo_esperado", [([CODIGO, TEST_BUENO], 0), ([CODIGO], 1)])
def test_la_linea_de_comandos_sale_con_1_si_no_es_conforme(tmp_path, ficheros, codigo_esperado):
    # conformidad_pr.py usa este codigo de salida como resultado del gate.
    entrada = tmp_path / "pr.json"
    entrada.write_text(json.dumps(pr_con(*ficheros)), encoding="utf-8")

    assert principal(["--pr", str(entrada), "--spec", "SPEC-002"]) == codigo_esperado
