"""Worktrees de la flotilla: una copia de trabajo por agente, todas en la misma revision.

Van fuera de OneDrive (~/aula-flotilla/<agente>) y en modo --detach: no crean ramas ni se suben
a ningun sitio. El coordinador los reutiliza de un ciclo a otro, y nunca toca una carpeta que no
sea un worktree de este repositorio.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


class ErrorDeGit(Exception):
    """Git ha fallado, o una carpeta no es lo que deberia."""


def git(argumentos: list, carpeta: Path = RAIZ) -> str:
    proceso = subprocess.run(["git"] + argumentos, cwd=carpeta, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    if proceso.returncode != 0:
        raise ErrorDeGit("git %s: %s" % (" ".join(argumentos), proceso.stderr.strip()))
    return proceso.stdout


def revision(referencia: str, repositorio: Path = RAIZ) -> str:
    """El SHA completo del commit al que apunta `referencia` (HEAD, una rama, un SHA corto)."""
    return git(["rev-parse", "--verify", referencia + "^{commit}"], repositorio).strip()


def registrados(repositorio: Path = RAIZ) -> list:
    """Carpetas de los worktrees de este repositorio, sin contar la copia principal."""
    carpetas = []
    for linea in git(["worktree", "list", "--porcelain"], repositorio).splitlines():
        if linea.startswith("worktree "):
            carpetas.append(Path(linea[len("worktree "):]).resolve())
    return carpetas[1:]


def preparar(carpeta: Path, sha: str, repositorio: Path = RAIZ) -> None:
    """Deja `carpeta` como un worktree limpio en `sha`; lo crea si no existe."""
    if not carpeta.exists():
        git(["worktree", "add", "--detach", str(carpeta), sha], repositorio)
        return
    if carpeta.resolve() not in registrados(repositorio):
        raise ErrorDeGit("%s ya existe y no es un worktree de este repositorio: no se toca" % carpeta)
    git(["checkout", "--force", "--detach", sha], carpeta)
    git(["clean", "-fdx"], carpeta)     # borra lo que dejo el ciclo anterior, como el escenario


def aplicar_escenario(carpeta: Path, parche: str) -> None:
    """Aplica el parche sin hacer commit; tambien al indice, para que un fichero nuevo cuente.

    Se pasa en bytes y con saltos de linea \\n: en modo texto, en Windows, Python convertiria
    cada \\n en \\r\\n y git no reconoceria el parche.
    """
    datos = parche.replace("\r\n", "\n").encode("utf-8")
    proceso = subprocess.run(["git", "apply", "--index", "-"], cwd=carpeta, input=datos,
                             capture_output=True)
    if proceso.returncode != 0:
        raise ErrorDeGit("git apply: %s" % proceso.stderr.decode("utf-8", errors="replace").strip())


def cambiados(carpeta: Path) -> list:
    """Ficheros que el escenario cambia en el worktree."""
    rutas = []
    for linea in git(["diff", "--name-only", "HEAD"], carpeta).splitlines():
        if linea.strip():
            rutas.append(linea.strip())
    return rutas


def eliminar(carpeta: Path, repositorio: Path = RAIZ) -> bool:
    """Elimina el worktree de `carpeta`. Devuelve False si alli no habia ninguno."""
    if carpeta.resolve() not in registrados(repositorio):
        return False
    git(["worktree", "remove", "--force", str(carpeta)], repositorio)
    return True
