"""Grabacion de un ciclo de la flotilla: ciclo.jsonl, un evento por linea, y ciclo.md, el resumen.

La grabacion se versiona en el repositorio, asi que no lleva rutas personales: la raiz del
repositorio se escribe como <repositorio> y la carpeta del usuario como ~.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
# De la mas larga a la mas corta: la raiz del repositorio esta dentro de la carpeta del usuario.
RUTAS_PERSONALES = [(str(RAIZ), "<repositorio>"), (RAIZ.as_posix(), "<repositorio>"),
                    (str(Path.home()), "~"), (Path.home().as_posix(), "~")]


def sin_rutas_personales(valor):
    """Cambia las rutas personales en todos los textos, tambien dentro de listas y objetos."""
    if isinstance(valor, str):
        for ruta, sustituta in RUTAS_PERSONALES:
            # Sin distinguir mayusculas: en Windows C:\Users y c:\users son la misma carpeta.
            valor = re.compile(re.escape(ruta), re.IGNORECASE).sub(sustituta, valor)
        return valor
    if isinstance(valor, list):
        limpia = []
        for elemento in valor:
            limpia.append(sin_rutas_personales(elemento))
        return limpia
    if isinstance(valor, dict):
        limpio = {}
        for clave, elemento in valor.items():
            limpio[clave] = sin_rutas_personales(elemento)
        return limpio
    return valor


def se_solapan(resultados: list) -> bool:
    """Todos empezaron antes de que acabara ninguno: se ejecutaron a la vez."""
    if len(resultados) < 2:
        return False
    inicios = []
    fines = []
    for resultado in resultados:
        inicios.append(resultado["inicio"])
        fines.append(resultado["fin"])
    return max(inicios) < min(fines)


def eventos(ciclo: dict) -> list:
    lista = [{"evento": "ciclo", "revision": ciclo["revision"], "escenario": ciclo["escenario"],
              "contrato": ciclo["contrato"], "empieza": ciclo["empieza"],
              "cambiados": ciclo["cambiados"]}]
    for resultado in ciclo["resultados"]:
        evento = {"evento": "agente"}
        evento.update(resultado)
        lista.append(evento)
    for decision in ciclo["conflictos"]:
        evento = {"evento": "conflicto"}
        evento.update(decision)
        lista.append(evento)
    for entrega in ciclo["handoffs"]:
        evento = {"evento": "handoff"}
        evento.update(entrega)
        lista.append(evento)
    lista.append({"evento": "fin", "estado": ciclo["estado"], "motivos": ciclo["motivos"],
                  "en_paralelo": se_solapan(ciclo["resultados"]), "worktrees": ciclo["worktrees"]})
    return sin_rutas_personales(lista)


def resultado_breve(resultado: dict) -> str:
    salida = resultado["salida"]
    if resultado["errores"]:
        return "FALLO: %s" % "; ".join(resultado["errores"])
    if "veredicto" in salida:
        return "%s: %s" % (salida["veredicto"], salida["explicacion"])
    if "estado" in salida:
        return "%s: %s" % (salida["estado"], salida["resumen"])
    return "%d hallazgos, %d pasos" % (len(salida["hallazgos"]), len(salida["pasos"]))


def valor_breve(valor) -> str:
    """Un dato del handoff en una linea. Una lista de objetos se cuenta: el detalle esta en el JSONL."""
    if not isinstance(valor, list):
        return str(valor)
    if not valor:
        return "-"
    if isinstance(valor[0], dict):
        return "%d (el detalle esta en ciclo.jsonl)" % len(valor)
    textos = []
    for elemento in valor:
        textos.append(str(elemento))
    return "; ".join(textos)


def resumen(ciclo: dict) -> str:
    """ciclo.md: lo que paso en el ciclo, para leerlo sin abrir el JSONL."""
    ciclo = sin_rutas_personales(ciclo)
    escenario = ciclo["escenario"]
    lineas = ["# Ciclo de la flotilla", "",
              "- Revision: `%s`" % ciclo["revision"][:12],
              "- Escenario: %s. %s" % (escenario["id"], escenario["descripcion"]),
              "- Ficheros que cambia: %s" % ", ".join(ciclo["cambiados"]),
              "- Contrato: version %s" % ciclo["contrato"],
              "- Empieza: %s" % ciclo["empieza"],
              "- Estado: **%s**" % ciclo["estado"]]
    for motivo in ciclo["motivos"]:
        lineas.append("  - %s" % motivo)

    lineas += ["", "## Cronologia", "", "Segundos desde el comienzo del ciclo.", "",
               "| Agente | Worktree | Empieza | Acaba | Resultado |", "|---|---|---|---|---|"]
    for resultado in ciclo["resultados"]:
        lineas.append("| %s | `%s` | %.2f | %.2f | %s |" % (
            resultado["agente"], resultado["carpeta"], resultado["inicio"], resultado["fin"],
            resultado_breve(resultado)))
    if se_solapan(ciclo["resultados"]):
        lineas += ["", "Todos empezaron antes de que acabara ninguno: se ejecutaron a la vez."]

    lineas += ["", "## Conflictos", ""]
    for decision in ciclo["conflictos"]:
        lineas.append("- `%s`: gana %s; se pospone la propuesta de %s sobre este fichero." % (
            decision["fichero"], decision["gana"], ", ".join(decision["se_pospone"])))
    if not ciclo["conflictos"]:
        lineas.append("Ninguno decidido.")

    lineas += ["", "## Lo que llega al humano (handoff)", ""]
    for entrega in ciclo["handoffs"]:
        lineas.append("- **%s**: %s" % (entrega["de"], entrega["que_pasa"]))
        for campo, valor in entrega["datos"].items():
            if campo == "pasos":
                lineas.append("  - pasos:")
                for numero, paso in enumerate(valor, start=1):
                    lineas.append("    %d. %s" % (numero, paso))
            else:
                lineas.append("  - %s: %s" % (campo, valor_breve(valor)))
    lineas += ["", "## Worktrees activos", "", "```"] + ciclo["worktrees"] + ["```", ""]
    return "\n".join(lineas)


def grabar(ciclo: dict, carpeta: Path) -> None:
    lineas = []
    for evento in eventos(ciclo):
        lineas.append(json.dumps(evento, ensure_ascii=False))
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "ciclo.jsonl").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (carpeta / "ciclo.md").write_text(resumen(ciclo), encoding="utf-8")
