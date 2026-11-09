"""Ejecuta el agente de conformidad sobre un PR real y prepara el comentario para GitHub.

El PR declara en su descripcion que spec implementa:
    AULA_SPEC_ID: SPEC-002
    AULA_CRITERIOS: CA-05, CA-06

El script saca del diff los ficheros que cambian, se los pasa al agente y escribe el
veredicto en Markdown. El workflow .github/workflows/conformidad.yml lo publica en el PR.

Codigos de salida: 0 conforme, 1 no conforme, 2 el PR no declara spec.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# Lanzado como "python herramientas/conformidad_pr.py", Python solo ve herramientas/.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

SIN_SPEC = """### Agente de conformidad: sin spec declarada

Este PR no declara que spec implementa, asi que el agente no lo evalua ({motivo}).

Si implementa una spec, anade estas dos lineas a la descripcion del PR:

```
AULA_SPEC_ID: SPEC-002
AULA_CRITERIOS: CA-05, CA-06
```
"""

PIE = ("<sub>Veredicto determinista: reglas fijas sobre la spec, los ficheros y los tests del PR "
       "(`agentes/conformidad/agente.py`), sin modelo. Informa; no bloquea el merge.</sub>")


def metadatos(cuerpo: str) -> tuple[str, list[str]]:
    spec = re.search(r"^AULA_SPEC_ID:\s*(SPEC-\d+)$", cuerpo, re.M)
    criterios = re.search(r"^AULA_CRITERIOS:\s*(.+)$", cuerpo, re.M)
    if not spec or not criterios:
        raise ValueError("el cuerpo del PR debe incluir AULA_SPEC_ID y AULA_CRITERIOS")
    valores = re.findall(r"(?:CA|INV)-\d{2}", criterios.group(1))
    if not valores:
        raise ValueError("AULA_CRITERIOS debe declarar al menos un criterio")
    return spec.group(1), valores


def archivos(base: str) -> list[dict]:
    rutas = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=RAIZ, text=True
    ).splitlines()
    salida = []
    for ruta in rutas:
        fichero = RAIZ / ruta
        if fichero.is_file() and fichero.suffix in {".py", ".md"}:
            salida.append({"ruta": ruta, "contenido": fichero.read_text(encoding="utf-8")})
    return salida


def lista_o_guion(valores: list) -> str:
    if not valores:
        return "-"
    return ", ".join(valores)


def comentario(veredicto: dict) -> str:
    """Texto en Markdown con el veredicto, para publicarlo en el PR."""
    if veredicto["veredicto"] == "conforme":
        cabecera = "### Agente de conformidad: :white_check_mark: conforme"
    else:
        cabecera = "### Agente de conformidad: :x: no conforme"

    lineas = [
        cabecera,
        "",
        "| | |",
        "|---|---|",
        "| Spec | %s |" % veredicto["spec"],
        "| Criterios declarados | %s |" % lista_o_guion(veredicto["criterios_declarados"]),
        "| Con test | %s |" % lista_o_guion(veredicto["criterios_cubiertos"]),
        "| Sin test | %s |" % lista_o_guion(veredicto["criterios_sin_cubrir"]),
        "| Fuera de alcance | %s |" % lista_o_guion(veredicto["fuera_de_alcance"]),
        "",
    ]
    if veredicto["hallazgos"]:
        lineas.append("Hallazgos:")
        for hallazgo in veredicto["hallazgos"]:
            lineas.append("- %s" % hallazgo)
        lineas.append("")
    lineas.append(PIE)
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--cuerpo", required=True)
    parser.add_argument("--salida", default=".conformidad-pr.json")
    parser.add_argument("--comentario", default=".conformidad-pr.md")
    args = parser.parse_args(argv)
    try:
        spec, criterios = metadatos(Path(args.cuerpo).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        Path(args.comentario).write_text(SIN_SPEC.format(motivo=exc), encoding="utf-8")
        return 2

    entrada = {"id": "pr", "ficheros": archivos(args.base), "criterios_declarados": criterios}
    Path(args.salida).write_text(json.dumps(entrada, ensure_ascii=False), encoding="utf-8")

    from agentes.conformidad.agente import NO_CONFORME, evaluar

    veredicto = evaluar(entrada, spec).a_dict()
    print(json.dumps(veredicto, ensure_ascii=False, indent=2))
    Path(args.comentario).write_text(comentario(veredicto), encoding="utf-8")
    return 1 if veredicto["veredicto"] == NO_CONFORME else 0


if __name__ == "__main__":
    raise SystemExit(main())
