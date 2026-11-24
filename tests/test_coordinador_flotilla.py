"""Tests del coordinador de la flotilla: ejecucion en paralelo y worktrees."""
import subprocess
import sys
from pathlib import Path

import pytest

from agentes.flotilla import grabacion, worktrees
from agentes.flotilla.coordinador import lanzar_en_paralelo


def test_los_trabajos_se_ejecutan_a_la_vez(tmp_path):
    espera = [sys.executable, "-c", "import time; time.sleep(1)"]
    lista = []
    for nombre in ("a", "b", "c"):
        lista.append({"agente": nombre, "carpeta": tmp_path, "comando": espera})

    ejecuciones = lanzar_en_paralelo(lista)

    assert grabacion.se_solapan(ejecuciones)
    assert ejecuciones[-1]["fin"] < 2.5     # en fila tardarian 3 segundos o mas


def git(carpeta: Path, *argumentos):
    subprocess.run(["git"] + list(argumentos), cwd=carpeta, check=True, capture_output=True)


def test_un_worktree_por_agente_en_la_revision_y_con_el_escenario(tmp_path):
    repositorio = tmp_path / "repo"
    repositorio.mkdir()
    git(repositorio, "init", "-q")
    (repositorio / "media.py").write_text("NOTA = 5\n", encoding="utf-8")
    git(repositorio, "add", ".")
    git(repositorio, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "inicio")
    sha = worktrees.revision("HEAD", repositorio)
    parche = "--- a/media.py\n+++ b/media.py\n@@ -1 +1 @@\n-NOTA = 5\n+NOTA = 6\n"
    carpeta = tmp_path / "flotilla" / "triaje-pipeline"

    worktrees.preparar(carpeta, sha, repositorio)
    worktrees.aplicar_escenario(carpeta, parche)
    assert worktrees.cambiados(carpeta) == ["media.py"]
    assert carpeta.resolve() in worktrees.registrados(repositorio)

    worktrees.preparar(carpeta, sha, repositorio)     # el siguiente ciclo empieza limpio
    assert worktrees.cambiados(carpeta) == []

    ajena = tmp_path / "ajena"
    ajena.mkdir()
    with pytest.raises(worktrees.ErrorDeGit, match="no es un worktree"):
        worktrees.preparar(ajena, sha, repositorio)

    assert worktrees.eliminar(carpeta, repositorio)
    assert not worktrees.eliminar(carpeta, repositorio)
