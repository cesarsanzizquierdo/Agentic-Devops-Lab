# Bitacora de S3

Registra configuraciones, pruebas de permisos y resultados comparativos.

## Punto 2: permisos y hooks (2026-10-28)

Configuracion en `.claude/settings.json`:

| Pieza | Cuando actua | Que hace |
|---|---|---|
| `hook_rutas.py` | Antes de Edit/Write | Bloquea (codigo 2) las rutas de la tabla de limites de CLAUDE.md |
| `hook_formato.py` | Despues de Edit/Write | Quita espacios finales y asegura salto de linea final en `.py` |
| `hook_tests_commit.py` | Antes de cada comando Bash | Si es un `git commit`, ejecuta pytest y bloquea si no esta en verde |
| `permissions.deny` | Antes de Edit/Write | Segunda barrera sobre las mismas rutas, aplicada por Claude Code |
| `permissions.allow` | Antes de Bash | Comandos de solo lectura o de verificacion que no piden confirmacion |

Defectos encontrados en el `hook_rutas.py` original, comprobados antes de cambiarlo:

| Ruta | Hook original | Hook corregido |
|---|---|---|
| `manifiestos\agente.yaml` (Windows) | 0, la dejaba pasar | 2, bloqueada |
| `labs/S3-contexto/comparativa.md` | 2, bloqueada sin motivo | 0, permitida |

`aula_cli check` no esta en la allowlist a proposito: cada ejecucion suma un intento a la
estacion activa en `.aula/progreso.json`, que es el registro del alumno, asi que debe pedir
confirmacion. (Solo desella una estacion si se le pasa una ya sellada, como `check S2`.)

### Limitacion conocida

Los hooks de rutas y las reglas `deny` vigilan las herramientas de edicion, no lo que
escribe un comando de Bash (por ejemplo `echo x > manifiestos/a.yaml`). Las reglas de
Bash de Claude Code comparan el inicio del comando y no pueden detectar una redireccion
en mitad de el. La barrera para ese caso es humana: revisar el diff de cada PR antes del
merge. CODEOWNERS no lo garantiza en este repo: con una sola persona, GitHub no exige que
el autor apruebe su propio PR.

## Punto 3: revision del PR #8 y ajustes (2026-10-28)

El revisor (subagente, solo lectura) reviso el diff del PR #8 y devolvio APROBAR CON CAMBIOS, sin fallos bloqueantes.

| Cambio | Por que | Ejemplo |
|---|---|---|
| Lista blanca en el test del revisor | la lista negra deja pasar herramientas no previstas | `tools: Read, Grep, PowerShell` -> antes pasaba, ahora falla |
| Veredicto FALTA | la regla anterior convertia en NO APLICA los defectos por ausencia | CA sin test -> antes NO APLICA, ahora "FALTA: test de CA-03" |
| Modelo fijado | sin `model:` el subagente hereda el de la sesion | `/model haiku` hacia revisar con Haiku sin aviso |
| Implementador ejecuta evaluador y `verificar.py` | CLAUDE.md pide tres comprobaciones y ejecutaba una | pytest en verde pero sin evaluador |
| Errata del docstring | "independiente" era ambiguo (autonomo frente a imparcial) | - |
| `.claude/` y CLAUDE.md con confirmacion (`ask`) | el implementador podia editar al revisor sin que nadie se enterase | anadir Bash a `revisor.md` con Edit -> antes sin aviso, ahora pregunta al humano |

Descartados:

- "No hagas commit" es solo texto (el hook de commit ya exige tests en verde; queda como limitacion).
- `removesuffix` exige Python 3.9 (el proyecto usa 3.11).
- Unificar `python`/`python3` (decision del humano: se queda).

Proteger `.claude/` con CODEOWNERS se descarto porque en un repo de una sola persona GitHub no exige que el autor apruebe su propio PR, asi que seria decorativo.

### Segunda revision, antes de abrir el PR

El revisor (Opus) reviso los ajustes anteriores y devolvio APROBAR CON CAMBIOS:

| Hallazgo | Arreglo |
|---|---|
| La bitacora decia "ahora bloqueado", pero con Bash no lo estaba | Corregido aqui y en la limitacion conocida |
| Ningun test comprobaba las reglas de `settings.json` | `test_settings_prohibe_las_rutas_de_limites` y `test_settings_pregunta_antes_de_cambiar_las_reglas_del_agente` |
| CLAUDE.md mandaba ejecutar `aula_cli check` y el implementador lo prohibia | Nota en Verificacion: lo ejecuta el humano porque suma intentos al registro |
| `revisor.md` no decia que poner en un punto que no se puede comprobar | Se escribe "ver Dudas" |
| "Modelos distintos para no compartir puntos ciegos" era debil (misma familia) | Eliminado; se mantiene el argumento del coste |

Cambio de decision: bloquear `.claude/` con `deny` obligaba al humano a editar a mano y el
proyecto no lo pide (no esta en la tabla de limites). Se sustituye por `ask`: el agente
puede editar `.claude/` y CLAUDE.md, pero Claude Code pregunta al humano antes de cada cambio.
Comprobado en vivo: al editar CLAUDE.md aparecio la confirmacion y el humano rechazo un cambio
cuyo texto era impreciso. El hook de rutas ya no incluye `.claude/`; si lo incluyera, bloquearia
antes de que la regla `ask` pudiera preguntar.

Descartado: proteger los scripts de `herramientas/hook_*.py`. Mismo razonamiento que `.claude/`:
el proyecto no lo pide y los tests de hooks, que el CI ejecuta en cada PR, detectan si un hook
deja de bloquear.
