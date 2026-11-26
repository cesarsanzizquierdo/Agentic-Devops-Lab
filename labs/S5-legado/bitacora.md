# Bitacora de S5

Registra caracterizacion antes del refactor y las desviaciones justificadas.

## Aviso: S5-02 falla por un commit de S3, no por el orden de S5

**Que pasa.** El criterio S5-02 ("la caracterizacion precede al refactor en el historial") sale
en rojo aunque en S5 la caracterizacion se commitea antes de tocar una sola linea del legado.

**Por que.** El commit `3c6b882` de S3 se titulo "refactor: unificar creditos_superados en
media.py". Cambio `motor.py` y dos specs; no toco `src/aula/legado/`. Es el commit 24 del
historial, y cualquier commit de caracterizacion de S5 ira detras.

**Como valida el verificador.** `orden_en_historial(r"caracteriz", r"^refactor", por_asunto=True)`
(`aula_cli/verificacion.py`) recorre `git log --reverse` y solo mira el titulo de cada commit: el
primero que contiene "caracteriz" tiene que ir antes del primero que empieza por "refactor". No
mira que ficheros cambia cada commit.

**Que se hace.**
- El orden real de S5 se demuestra con los SHAs de sus commits al final de esta bitacora:
  caracterizacion, equivalencia, apertura del legado y refactor, en ese orden.
- No se reescribe el historial de main ni se toca `verificar.py`.
- Si al final de la estacion no hay otra salida, se usara
  `python -m aula_cli desbloquear S5 --motivo "..."`, con este aviso como motivo.
