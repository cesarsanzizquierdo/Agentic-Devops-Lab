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

## Punto 4: comparativa con OpenCode, bloqueada (2026-10-29)

Objetivo: resolver el mismo encargo con Claude Code (subagente implementador, Sonnet) y con
OpenCode, partiendo del mismo commit (`d88d0d9`), y comparar el resultado.

Encargo preparado: en `GET /expedientes/{estudiante_id}` la nota media y el progreso se
convierten a `float`, y CLAUDE.md exige `Decimal`. Tenia una ambiguedad a proposito (devolver
texto o numero) para medir si cada herramienta pregunta antes de cambiar el contrato de la API.

Configuracion de OpenCode:

| Elemento | Valor | Motivo |
|---|---|---|
| Version | OpenCode 1.19.5, instalado con `npm install -g opencode-ai` | Instalacion nativa en Windows |
| Modelo | GLM-5.3-Flash Free (OpenCode Zen), razonamiento high | Gratuito y, segun su documentacion, sin retencion de datos ni entrenamiento con ellos |
| Descartados | Suscripcion de Claude (OpenCode indica que Anthropic lo prohibe); Big Pickle y otros gratuitos (pueden usar los datos para entrenar) | El repo es material de empresa |

Resultado: al enviar el encargo, OpenCode mostro "Free limit reached" de inmediato y ofrecio la
suscripcion OpenCode Go (10 $/mes). No llego a ejecutar nada. A un companero con la misma tarea
le ocurrio lo mismo. Evidencia: `labs/S3-contexto/error_opencode.png`.

Comprobado despues: sin cambios ni ficheros nuevos en el repo (salvo la captura), sin commits en
las ramas de prueba y 54 tests en verde. Las ramas de prueba se borraron (eran solo locales).

S3-05 se cierra con una comparativa documental (ver `comparativa.md`), pendiente de validar con
el mentor.

## Punto 5: ciclo escritor/revisor en worktrees paralelos con Orca

### Montaje

| Elemento | Valor |
|---|---|
| Orquestador | Orca |
| Worktree 1, escritor | Rama `S3-orca-escritor`, fuera de la carpeta del repo |
| Worktree 2, revisor | Rama `S3-orca-revisor`, creada desde la rama del escritor |
| Agentes | Claude. Subagentes con modelo fijado: implementador (Sonnet), revisor (Opus) |
| Entorno | Orca no copia los ficheros ignorados por git: el worktree del escritor necesito su propio `.venv` |

### Cronologia

| Paso | Worktree 1, escritor | Worktree 2, revisor |
|---|---|---|
| 1 | Encargo A: `nota_media` y `progreso` pasan de float a texto ("7.35"). Commit `a940f90` | |
| 2 | | Revisa A: APROBAR CON CAMBIOS. Faltan rutas en SPEC-002 y un docstring promete no redondear |
| 3 | Encargo B: quitar la copia duplicada de `creditos_superados`. Commit `3c6b882` | |
| 4 (10:06-10:07, en paralelo) | Corrige los dos fallos de A | Revisa B: APROBAR |
| 5 | Correcciones en `b203c8b`. 65 tests en verde | |

Evidencia del paralelo: `orca_paralelo.png`, con los dos workspaces activos a la vez, y las horas
(el revisor termino a las 10:07 con el escritor en marcha desde las 10:06).

### Lo que hizo bien el agente

- Ante cada ambiguedad pregunto en vez de suponer, y la registro en la spec antes de implementar
  (A-03, A-04 y A-05 de SPEC-002; A-05 de SPEC-001). Encontro dudas que no habiamos previsto.
- Diseno un test que el codigo antiguo hace fallar: con float, 6.80 saldria 6.8.
- No anadio dependencias: sin `httpx` no uso `TestClient`, y dejo escrito el motivo en el test.
- Se corrigio solo: uso tres veces el Python general y paso al del `.venv`.
- Se autorreviso: encontro dos incoherencias suyas en la spec antes que el revisor.
- El revisor demostro con el codigo lo que el escritor solo afirmaba (que las dos copias eran
  equivalentes) y separo un hueco de cobertura anterior sin contarlo como fallo del diff.

### Lo que hizo mal

- Escribio ficheros con scripts de Python dentro de Bash cuatro veces, saltandose los hooks de
  edicion (la limitacion conocida, vista en vivo).
- Intento reescribir `motor.py` por Bash para esquivar `hook_formato` y dejar el diff limpio, sin
  preguntar. El humano lo rechazo. Su informe final no lo menciona.
- En A hizo el codigo antes que la spec, al reves de lo que anuncio.
- No amplio las rutas de SPEC-002 (lo cazo el revisor).
- El coordinador abrevio el diff que debia pasar literal al revisor y dio por hecho que A seguia
  sin commit (el commit lo hizo el humano en otra terminal).

### Hallazgos sobre herramientas y configuracion

| Hallazgo | Consecuencia |
|---|---|
| Orca lanzaba Claude en modo "Bypass Permissions" | Anulaba en silencio `ask`, `deny` y las preguntas. Cambiado a "Pedir aprobacion" |
| Claude arranca en "auto mode" | Cambiado a modo normal para ver cada paso |
| `hook_formato` limpia el fichero entero | Mete en el diff cambios de espacios ajenos al encargo |
| Aprobacion manual con dos agentes | El humano es el cuello de botella: el revisor termino mientras el escritor esperaba un permiso |
| El proyecto esta en el Escritorio, que la empresa sincroniza con OneDrive | Los ficheros internos de git quedan bloqueados mientras se sincronizan: quedan restos de worktrees que no se pueden borrar ("Permission denied" en cada commit) |
| `/model` dentro de Orca | Guarda el modelo como predeterminado para todas las sesiones nuevas |
