# Flotilla de S4b

Tres agentes trabajan sobre el mismo servidor MCP (`agentes/mcp_aula/servidor.py`):
conformidad, triaje de pipeline y propuesta de modernizacion. Un coordinador los lanza a la vez,
cada uno en su worktree, y decide con lo que devuelven. La fuente de verdad es el contrato
`agentes/flotilla/contrato.json`; este documento lo dibuja y explica un ciclo completo.

## Diagrama de un ciclo

Los numeros [0] a [7] son los pasos del recorrido que se explica debajo. A la derecha de cada
paso, la funcion que lo hace.

```text
 [0] ENTRADA DEL CICLO
 +--------------------------------------------------------------------------------------+
 | revision:  HEAD (en el ciclo grabado, faff074): el mismo commit para los tres        |
 | escenario: labs/S4b-flotilla/escenario/redondeo_por_asignatura.json + .diff          |
 |            - el .diff cambia src/aula/reglas/media.py: redondea cada asignatura      |
 |            - el .json declara SPEC-002 / CA-04, como lo haria la descripcion de un PR |
 | contrato:  agentes/flotilla/contrato.json: las reglas de todo el ciclo               |
 +--------------------------------------------------------------------------------------+
        |
        v
 [1] COORDINADOR comprueba el contrato                       validar_contrato()
        |   si esta roto, el ciclo no se lanza (sale con 3)
        v
 [2] COORDINADOR prepara un worktree por agente              preparar_worktrees()
        |
        |   ~/aula-flotilla/conformidad-spec      \   git worktree add --detach <revision>
        |   ~/aula-flotilla/triaje-pipeline        >  + git apply del .diff (sin commit)
        |   ~/aula-flotilla/modernizacion-legado  /
        |
        |   = tres copias identicas del repositorio, todas con el mismo parche aplicado
        |   ficheros cambiados (git diff):  src/aula/reglas/media.py
        v
 [3] COORDINADOR prepara la entrada de cada agente           trabajos()
        |
        |   conformidad   <-  JSON con media.py y los criterios (CA-04)  +  --spec SPEC-002
        |   triaje        <-  --cambiados src/aula/reglas/media.py
        |   modernizacion <-  el legado (calculadora_expediente_v1.py)  +  media.py
        v
 [4] LOS TRES A LA VEZ, cada uno en su worktree y en su proceso   lanzar_en_paralelo()
 +---------------------------+  +---------------------------+  +---------------------------+
 | conformidad-spec          |  | triaje-pipeline           |  | modernizacion-legado      |
 |                           |  |                           |  |                           |
 | MCP: obtener_spec         |  | MCP: resultado_tests,     |  | MCP: version_plan         |
 |                           |  |      trazabilidad,        |  |                           |
 | compara el cambio con     |  |      listar_specs,        |  | lee el codigo con ast,    |
 | la spec                   |  |      obtener_spec         |  | sin ejecutarlo            |
 |                           |  | ejecuta pytest            |  |                           |
 | da: no_conforme           |  | da: rojo, 2 regresiones   |  | da: 10 hallazgos y        |
 |     (CA-04 sin test)      |  |     de CA-04              |  |     4 pasos; el primero,  |
 | propone tocar: nada       |  | propone tocar: media.py   |  |     caracterizar          |
 |                           |  |                           |  | propone tocar: legado,    |
 |                           |  |                           |  |   media.py y la bateria   |
 |                           |  |                           |  |   de caracterizacion      |
 +---------------------------+  +---------------------------+  +---------------------------+
        |   ninguno escribe ficheros: solo imprimen su respuesta en JSON
        |   acaban en 0,77 s, 23,25 s y 0,86 s: empezaron todos antes de que acabara ninguno
        v
 [5] COORDINADOR revisa cada respuesta con el contrato       revisar_resultado()
        |   acabo a tiempo, codigo de salida declarado, es JSON y trae todos sus campos
        v
 [6] COORDINADOR decide                                      decidir_ciclo()
        |   conflicto: media.py lo proponen triaje y modernizacion
        |              -> gana triaje (prioridad del contrato);
        |                 se pospone solo la propuesta de modernizacion sobre media.py
        |   handoffs:  conformidad (siempre), triaje (esta en rojo), modernizacion (siempre)
        v
 [7] SALIDA DEL CICLO                                        grabar()
 +--------------------------------------------------------------------------------------+
 | al humano:  los tres handoffs y el conflicto ya decidido                             |
 | grabacion:  labs/S4b-flotilla/ciclo/ciclo.jsonl y ciclo.md                           |
 |             (lo unico que se escribe en todo el ciclo)                               |
 | worktrees:  se quedan para el siguiente ciclo; --limpiar los elimina                 |
 +--------------------------------------------------------------------------------------+
```

## Recorrido de un ciclo, paso a paso

Se lanza con:

```
python -m agentes.flotilla.coordinador --escenario labs/S4b-flotilla/escenario/redondeo_por_asignatura.json
```

`principal()` lee los argumentos y llama a `lanzar_ciclo()`, que hace los pasos 1 a 7. Las
funciones sin fichero indicado estan en `agentes/flotilla/coordinador.py`. Los ejemplos son del
ciclo grabado en `labs/S4b-flotilla/ciclo/`.

**[0] La entrada.** El ciclo necesita tres cosas:
- **La revision:** un commit (por defecto HEAD). Los tres agentes leen exactamente ese codigo,
  asi que sus resultados se pueden comparar.
- **El escenario:** un `.json` y un `.diff`. El `.diff` es el cambio que se prueba: aqui redondea
  la nota de cada asignatura en `media.py`, contra el invariante 1. El `.json` lo describe y dice
  que spec y criterios declara (SPEC-002, CA-04), como la descripcion de un PR. Sirve para
  simular un PR malo sin tocar main. Lo lee `cargar_escenario()`.
- **El contrato:** que ve cada agente, que devuelve, que se pasan y quien gana en un conflicto.

**[1] Comprobar el contrato.** `cargar()` y `validar_contrato()` (`agentes/flotilla/contrato.py`)
comprueban que el contrato es coherente. Si esta roto, el ciclo no se lanza: no tiene sentido
aplicar unas reglas que no se sostienen.

**[2] Un worktree por agente.** `preparar_worktrees()` llama, para cada agente, a:
- `worktrees.preparar()`: crea `~/aula-flotilla/<agente>` con `git worktree add --detach`, o lo
  devuelve limpio a la revision si ya existe de un ciclo anterior;
- `worktrees.aplicar_escenario()`: aplica el `.diff` con `git apply`, sin hacer commit.

Por que asi:
- **Aislamiento:** cada agente tiene su propia copia; lo que ensucie uno (pytest crea ficheros)
  no afecta a los otros ni a la copia del humano.
- **El mismo punto de partida:** los tres worktrees tienen el mismo commit y el mismo parche.
- **Sin commit ni rama:** el parche nunca entra en el historial ni se puede subir por error.
- **Fuera de OneDrive:** OneDrive bloquea los ficheros de git.

Despues, `worktrees.cambiados()` (`git diff --name-only`) da los ficheros que cambia el escenario:
`src/aula/reglas/media.py`.

**[3] La entrada de cada agente.** `trabajos()` arma la linea de comandos de cada uno con lo que
su contrato declara en `entradas`:
- conformidad: `entrada_de_conformidad()` escribe un JSON con el contenido de los ficheros
  cambiados y los criterios declarados, y se le pasa la spec;
- triaje: la lista de ficheros cambiados;
- modernizacion: `modulos_que_analizar()` le da el legado entero y el codigo de `src/` que cambia.

**[4] Los tres a la vez.** `lanzar_en_paralelo()` abre un hilo por agente y en cada uno
`ejecutar()` lanza `python -m <agente>` dentro de su worktree, con un limite de 600 s, y apunta
cuando empieza y cuando acaba. Pueden ir a la vez porque ninguno usa lo que dice otro.

Dentro de cada agente (los tres son deterministas, sin modelo):
- **Conformidad** (`agentes/conformidad/agente.py`) lee la spec con `obtener_spec` y mira si cada
  criterio declarado tiene un test en el cambio. CA-04 no lo tiene: **no conforme**.
- **Triaje** (`agentes/triaje/agente.py`, `triar()`):
  1. pide `resultado_tests`: el servidor ejecuta pytest en su worktree y fallan 2 tests;
  2. `criterios_por_test()` pregunta con `listar_specs` y `trazabilidad` de que criterio es cada
     test: SPEC-002/CA-04;
  3. `categoria()` los clasifica como **regresion**;
  4. `sospechosos()` cruza las rutas de la spec (`obtener_spec`) con los ficheros cambiados:
     **propone tocar `media.py`**.
- **Modernizacion** (`agentes/modernizacion/agente.py`, `proponer()`) pide el plan con
  `version_plan` y, sin ejecutar el codigo, busca legado sin caracterizar, coma flotante, redondeo
  dentro de un bucle (tambien el de `media.py`) y constantes que repiten el plan (`MAX_CONV = 6`).
  Da 10 hallazgos y 4 pasos, el primero caracterizar, y **propone tocar el legado, `media.py` y la
  bateria de caracterizacion**.

Triaje y modernizacion piden las herramientas a traves de `consultar()` (`agentes/flotilla/mcp.py`),
que rechaza las que su contrato no declara. **Ningun agente escribe ficheros**: solo imprimen su
respuesta en JSON. En el ciclo grabado acaban en 0,77 s, 23,25 s y 0,86 s, y todos empezaron antes
de que acabara ninguno.

**[5] Revisar cada respuesta.** `revisar_resultado()` (`agentes/flotilla/decisiones.py`)
comprueba que el agente acabo a tiempo, salio con un codigo que su contrato declara, devolvio
JSON y trae todos los campos prometidos (`validar_salida()`). El coordinador no se fia de lo que
le llega: si algo falla, ese agente cuenta como fallido y el ciclo queda incompleto.

**[6] Decidir.** `decidir_ciclo()` (`agentes/flotilla/decisiones.py`):
- **Conflicto** (`conflictos()`): junta los `propone_tocar` de todos y busca ficheros repetidos.
  `media.py` lo proponen triaje y modernizacion; segun la prioridad del contrato **gana triaje**,
  porque primero hay que devolver el verde. De modernizacion solo se pospone lo de `media.py`; el
  resto de su propuesta sigue adelante. Si el ciclo es incompleto, no se decide ningun conflicto.
- **Handoffs** (`handoffs()` y `se_cumple()`): cada handoff del contrato llega al humano si se
  cumple su condicion. Conformidad y modernizacion, siempre; triaje, porque esta en rojo.

**[7] La salida.** `grabar()` (`agentes/flotilla/grabacion.py`) escribe `ciclo.jsonl` (un evento
por linea: el ciclo, cada agente, el conflicto, cada handoff y el fin) y `ciclo.md` (el resumen).
`se_solapan()` comprueba que los tres fueron a la vez, y `sin_rutas_personales()` quita las rutas
del usuario. **Es lo unico que se escribe en todo el ciclo.** Los worktrees se quedan para el
siguiente ciclo (S4b-04 los cuenta); `--limpiar` los elimina. El coordinador sale con 0 si el ciclo
es completo, 1 si es incompleto y 3 si no se pudo lanzar.

## Que ve cada agente y que escribe

| Agente | Herramientas MCP | Entrada | Salida (JSON) | Escribe |
|---|---|---|---|---|
| `conformidad-spec` | `obtener_spec` | los ficheros del cambio, los criterios que declara y su spec | veredicto, criterios sin cubrir, fuera de alcance | nada |
| `triaje-pipeline` | `resultado_tests`, `trazabilidad`, `listar_specs`, `obtener_spec` | los tests y los ficheros cambiados | estado (verde, rojo o no ejecutado), fallos clasificados con su criterio, `propone_tocar` | nada |
| `modernizacion-legado` | `version_plan` | el legado y el codigo de `src/` que cambia | hallazgos, pasos en orden (caracterizar primero), `propone_tocar` | nada |

## Que se pasan (handoff)

Todo llega al humano, a traves del coordinador:

| De | Cuando | Que pasa |
|---|---|---|
| conformidad | siempre | el veredicto, para decidir el merge |
| triaje | si el estado es rojo o no ejecutado | cada fallo con su categoria, su criterio y los ficheros que mirar |
| modernizacion | siempre | la propuesta por pasos; ningun paso se aplica sin aprobacion humana |

## Que pasa cuando dos quieren tocar el mismo fichero

1. Gana el de mas prioridad: **triaje, y despues modernizacion**. Conformidad no propone cambios.
2. Del que pierde solo se pospone la propuesta sobre ese fichero.
3. Ningun agente aplica nada. Si la propuesta toca una ruta protegida de CLAUDE.md, o hay una
   duda que la prioridad no resuelve, decide el humano.
4. En git, los agentes no crean ramas ni commits. Si dos propuestas se convierten en PRs, se
   mergea primero la del agente con mas prioridad y la otra se rehace sobre main.

## Como se valida el contrato

- `python -m agentes.flotilla.contrato` comprueba que el contrato es coherente: agentes sin
  repetir, herramientas que existen en el servidor, ningun agente que escriba, handoffs con campos
  de la salida de quien los envia y una prioridad que ordena a todos los que proponen cambios.
- `tests/test_contrato_flotilla.py` lo ejecuta en el pipeline y comprueba ademas que **el codigo
  cumple lo declarado**: cada agente usa justo las herramientas MCP de su contrato y no escribe.
- En cada ciclo, el coordinador valida la respuesta real de cada agente (paso [5]).
