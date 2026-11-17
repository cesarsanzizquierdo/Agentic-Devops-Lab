"""Tests de consultar(): la puerta de la flotilla al servidor MCP, con el contrato como filtro."""
import pytest

from agentes.flotilla.mcp import ErrorDelServidor, HerramientaNoDeclarada, consultar


def test_un_agente_obtiene_las_herramientas_que_declara():
    specs = consultar("triaje-pipeline", "listar_specs", {})["specs"]

    identificadores = []
    for spec in specs:
        identificadores.append(spec["id"])
    assert "SPEC-002" in identificadores


@pytest.mark.parametrize("agente, herramienta", [
    ("modernizacion-legado", "resultado_tests"),    # modernizacion no ejecuta tests
    ("conformidad-spec", "trazabilidad"),
    ("agente-fantasma", "listar_specs"),            # no esta en el contrato
])
def test_lo_que_el_contrato_no_declara_se_rechaza(agente, herramienta):
    with pytest.raises(HerramientaNoDeclarada):
        consultar(agente, herramienta, {})


def test_un_error_de_la_herramienta_vuelve_como_dato():
    respuesta = consultar("triaje-pipeline", "obtener_spec", {"id": "SPEC-999"})

    assert respuesta == {"error": "spec SPEC-999 no encontrada"}


def test_una_llamada_mal_formada_es_un_error_del_servidor():
    with pytest.raises(ErrorDelServidor, match="faltan argumentos"):
        consultar("triaje-pipeline", "obtener_spec", {})
