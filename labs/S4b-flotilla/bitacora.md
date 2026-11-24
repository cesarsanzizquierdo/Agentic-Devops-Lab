# Bitacora de S4b

Registra coordinacion, handoffs, conflictos y evidencia de ejecucion.

## AVISO PARA S5: el verificador de la regla dura solo lee el titulo de los commits

En S5, el criterio S5-02 ("la caracterizacion precede al refactor en el historial") fallara
aunque el codigo heredado no se haya tocado, y `aula cerrar S5` no sella con un criterio en rojo.

**Por que.** El commit `3c6b882` de S3 se titulo "refactor: unificar creditos_superados en
media.py". Cambio `motor.py` y dos specs; **no toco `src/aula/legado/`**. Pero el verificador solo
mira el titulo.

**Como valida exactamente.** `labs/S5-legado/verificar.py` llama a
`orden_en_historial(r"caracteriz", r"^refactor", por_asunto=True)` (`aula_cli/verificacion.py`):

1. Recorre `git log --reverse` del mas antiguo al mas nuevo.
2. Solo mira el titulo de cada commit, no los ficheros que cambia.
3. Busca el primer titulo que contiene "caracteriz" y el primero que empieza por "refactor".
4. Pasa si el de caracterizacion va antes, o si no hay ningun refactor.

El primer titulo con "refactor" es el commit 24 del historial (`3c6b882`), y todavia no hay ninguno
con "caracteriz": cualquier caracterizacion que se haga en S5 ira detras. **Hay que contarselo al
mentor.** Reescribir ese titulo en main seria maquillar el historial, y no se hace. En S4b ningun
commit empieza por "refactor" ni menciona la caracterizacion.

## Como se trabajo

En solitario, por instruccion del tutor: la escuadra no participo en la construccion.

## Que se hizo

Ocho PRs, en este orden:

1. `S4b-restos-s4a`: cierre de S4a (su bitacora, el sellado y dos convenciones de legibilidad en
   CLAUDE.md).
2. `S4b-contrato`: el contrato de contexto (`agentes/flotilla/contrato.json`) y su validador.
3. `S4b-acceso-mcp`: la puerta de los agentes al servidor MCP, que solo deja pasar lo que declara
   el contrato, y dos ajustes en `resultado_tests`.
4. `S4b-agente-triaje`: el agente de triaje de pipeline.
5. `S4b-agente-modernizacion`: el agente de propuesta de modernizacion, y el test de que el codigo
   de cada agente cumple su contrato.
6. `S4b-decisiones-grabacion`: las reglas de conflicto y handoff, y la grabacion del ciclo.
7. `S4b-coordinador`: el coordinador, los worktrees y el escenario.
8. `S4b-flotilla`: el diagrama y el recorrido de un ciclo (`flotilla.md`), el ciclo grabado y
   esta bitacora.

## Decisiones

- **El contrato primero**, porque es lo que se evalua: que ve cada agente, que escribe, que se
  pasan y que pasa cuando dos quieren tocar el mismo fichero. Se valida en el pipeline, y un test
  comprueba que el codigo de cada agente usa justo las herramientas que declara y no escribe.
- **Agentes deterministas, sin modelo**, como conformidad: reglas fijas y resultados
  reproducibles.
- **Paralelo para leer, secuencial para decidir.** Ningun agente usa la salida de otro, asi que
  van a la vez, cada uno en su worktree. Despues decide el coordinador, que es el unico que
  escribe.
- **En un conflicto gana triaje**, porque primero hay que devolver el verde. Del que pierde solo
  se pospone ese fichero.
- **Un escenario en vez de un PR real**: un parche que se aplica sin commit en los worktrees, para
  probar la flotilla con un fallo conocido sin tocar main.

El diagrama y el recorrido completo de un ciclo, paso a paso y con sus funciones, estan en
`labs/S4b-flotilla/flotilla.md`.

## Problemas y como se resolvieron

| Problema | Solucion |
|---|---|
| OneDrive bloquea los ficheros de git y no deja borrar los worktrees | Los worktrees van en `~/aula-flotilla/`, fuera de OneDrive. Quedan restos en `.git/worktrees/` (git avisa con "Permission denied" en cada commit): son inofensivos y se borran a mano con OneDrive en pausa |
| Con la salida capturada, pytest recortaba el motivo de cada fallo y triaje no podia clasificarlo | `resultado_tests` ejecuta pytest con `COLUMNS=1000` |
| Un fichero de tests roto escondia el resultado del resto | `resultado_tests` usa `--continue-on-collection-errors` |
| En Windows, `git apply` no reconocia el parche (saltos de linea `CRLF`) | El parche se pasa a git en bytes y con saltos `LF` |
| El diagrama en Mermaid no se veia ni en el PR ni en VS Code | Diagrama de texto, que se ve igual en todas partes |

## Ciclo grabado

`labs/S4b-flotilla/ciclo/` (`ciclo.jsonl` y `ciclo.md`), con el escenario que redondea la nota de
cada asignatura en `media.py`:

| Agente | Resultado |
|---|---|
| conformidad | no conforme: CA-04 sin test |
| triaje | rojo: 2 tests de CA-04 fallan, regresion, sospechoso `src/aula/reglas/media.py` |
| modernizacion | legado sin caracterizar, coma flotante, redondeo dentro de un bucle (tambien en `media.py`) y `MAX_CONV = 6`, que repite `max_convocatorias` del plan |

- Los tres empezaron antes de que acabara ninguno: se ejecutaron a la vez.
- **Conflicto** sobre `media.py`: lo proponen triaje y modernizacion; gana triaje y se pospone la
  propuesta de modernizacion sobre ese fichero.
- `git worktree list` muestra los tres worktrees de la flotilla, uno por agente.
