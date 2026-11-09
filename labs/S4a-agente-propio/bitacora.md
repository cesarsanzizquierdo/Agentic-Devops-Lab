# Bitacora de S4a

Registra iteraciones, hipotesis de mejora y metricas recibidas del mentor.

## Cambio de control: .github/workflows/ pasa de deny a ask

- Motivo: la tabla de limites de CLAUDE.md pide aprobacion humana explicita, no prohibicion.
  Con deny, los workflows de S4a (veredictos en PRs) y de S6 (gates) tendria que escribirlos
  el humano a mano. Lo decidio el humano.
- Ahora el agente propone el cambio y Claude Code pregunta antes de cada edicion. El hook ya
  no bloquea esa ruta: si lo hiciera, la pregunta nunca saldria.
- Riesgo detectado por el revisor: en modo bypass Claude Code no pregunta nada (lo dice su
  documentacion), asi que ask dejaria de proteger. Se cierra con
  `"disableBypassPermissionsMode": "disable"` en `.claude/settings.json`: en este repo no se
  puede arrancar en bypass. Es el mismo descuido que en S3 (Orca arrancaba en bypass).
- Las demas rutas de la tabla siguen en deny.

## Punto 1: servidor MCP

| Pieza | Que hace |
|---|---|
| `manejar` | Responde initialize, ping, tools/list y tools/call. Las notificaciones y las respuestas del cliente no se contestan |
| `principal` | Transporte stdio: una linea JSON por peticion y otra por respuesta. stdout solo lleva protocolo |
| `resultado_tests` | pytest solo dentro de tests/, con 120 s como maximo |
| `version_plan` | Version y parametros del plan, con la `cargar_plan` del proyecto |
| `.mcp.json` | Registra el servidor en Claude Code como `aula-contexto` |

- Si el cliente pide una herramienta o argumentos que no existen: error JSON-RPC (-32602).
  Si falla la herramienta: resultado con isError, para que el modelo lo lea y se corrija.
- La plantilla lanzaba el servidor con `python3 -m`. Falla si el proceso no arranca en la raiz
  (probado desde /tmp: "No module named 'agentes'") y la documentacion de Claude Code no
  garantiza esa carpeta. Se lanza el fichero por su ruta.
- `resultado_tests` lo puede llamar cualquier agente: sin limites serviria para ejecutar
  cualquier cosa. Se rechazan rutas fuera de tests/, rodeos con `..`, rutas absolutas y textos
  que empiezan por `-` (pytest los tomaria como opciones).

Primera revision (revisor, Opus): APROBAR CON CAMBIOS, 8 hallazgos:

| Hallazgo | Arreglo |
|---|---|
| 1. Cambio de workflows mezclado con el servidor | Separado en su propio PR, y modo bypass prohibido |
| 2. El servidor se caia con `"arguments": 5` | Se validan los tipos y el bucle tiene red de seguridad (-32603) |
| 3. Test de trazabilidad decorativo (solo miraba las claves) | Comprueba que CA-01 esta cubierto y que no se pierde ningun criterio |
| 4. Ramas sin test: fallidos, tiempo agotado, isError, ping | Tests nuevos, con pytest simulado donde hace falta |
| 5. Si pytest no llegaba a ejecutar no se sabia por que | Se devuelve el motivo (completado en la segunda revision) |
| 6. Desviaciones de JSON-RPC (contestar respuestas, no validar jsonrpc) | Corregidas (-32600) |
| 7. Aserciones debiles | Reforzadas |
| 8. pytest heredaba el canal stdin del protocolo | `stdin=DEVNULL` |

Segunda revision: APROBAR CON CAMBIOS. Lo bloqueante:

- Si el `python` del servidor no tiene pytest, sale con codigo 1, el mismo que cuando un test
  falla, y la herramienta decia "hay fallos" sin haber ejecutado nada. Ahora se exige la linea
  de resumen de pytest ("4 passed in 0.05s"); si no esta, se devuelve el motivo.
- Ademas: test de la red de seguridad (un JSON anidado 100000 veces lanza RecursionError),
  test de la segunda barrera de rutas con un enlace a una carpeta de fuera (en Windows sin
  permisos para enlaces se usa una junction) y test de `stdin=DEVNULL`. Los dos tests nuevos
  mas importantes se comprobaron rompiendo el codigo a proposito: fallan.

El trabajo se partio en tres PRs para no pasar de 400 lineas: control de workflows,
transporte y herramientas.

Prueba en vivo desde Claude Code: al reiniciar, Claude Code cargo `aula-contexto` desde
`.mcp.json` y aparecieron sus cinco herramientas (`mcp__aula-contexto__...`). Llamadas reales:

- `trazabilidad("SPEC-002")`: 11 criterios, 100 % cubiertos, con el test que cubre cada uno.
- `version_plan("PLAN-2024")`: version 1.2.0, 192 creditos, 6 convocatorias, 30 asignaturas.
- `resultado_tests("tests/test_mcp_transporte.py")`: "16 passed". Confirma que el `python` que
  resuelve `.mcp.json` es el del .venv, que tiene pytest.
- `resultado_tests("tests/../src")`: rechazada, y Claude Code la recibe como error.

Pendiente y riesgos conocidos:

- `${CLAUDE_PROJECT_DIR:-.}` en `.mcp.json`: segun la documentacion, esa variable no existe al
  expandir el comando, asi que se usa `.` y funciona porque Claude Code arranca en la raiz del
  repo. El servidor en si no depende de la carpeta (probado desde otra).
- Que el modo bypass quede bloqueado no se ha probado en vivo.
- Fuera de este cambio: la regla `allow` `Bash(python -m pytest:*)` deja pasar opciones de
  pytest que escriben ficheros (`--junitxml=.github/workflows/ci.yml`) sin preguntar. Hay que
  acotarla en otro PR.

Sorpresa: VS Code tiene su propio menu "Add MCP Server" (para Copilot), que no es el de
Claude Code. No hace falta usarlo: Claude Code lee `.mcp.json` solo.

## Punto 3: medicion del agente v0

Antes de tocar el agente se mide el v0 de la semilla, para que el historial demuestre que la
linea base es la de partida. Informe: `evals/informes/evaluacion_v0.json`.

| Metrica | v0 |
|---|---|
| Casos | 15 (10 no conformes, 5 conformes) |
| Matriz | vp 1, fp 0, vn 5, fn 9 |
| Precision | 1,00 |
| Recall | 0,10 |
| F1 | 0,18 |

Lectura: cuando acusa acierta, pero deja pasar 9 de los 10 PRs no conformes. Como gate es lo
peor posible: da sensacion de control y no para casi nada.

Por que, segun su codigo: el v0 dice "conforme" si algun fichero de
tests/ menciona el identificador de la spec. No comprueba que criterio cubre cada test, que
ficheros se tocan fuera del alcance ni si los tests comprueban algo de verdad.

## Punto 2: agente de conformidad v1

El agente recibe un PR (sus ficheros y los criterios que declara) y la spec que dice
implementar, y devuelve un veredicto estructurado: conforme o no_conforme, con criterios
cubiertos, criterios sin cubrir, ficheros fuera de alcance, hallazgos y una explicacion.

- La spec se la pide al servidor MCP (`obtener_spec`), que ahora devuelve tambien sus rutas.
- El veredicto es determinista: lo deciden reglas fijas, no un modelo. El mismo PR da siempre
  el mismo veredicto, que es lo que necesita un gate (PLAYBOOK, S4a).
- Solo usa lo que tiene un PR real ("ficheros" y "criterios_declarados"). Un test comprueba que
  el veredicto no cambia si el caso trae `etiqueta` o `titulo`.
- Para conocer el formato de los casos de evaluacion se consultaron `oro-001` y `oro-005`.

Decision del humano sobre la cobertura: un criterio esta cubierto si algun `tests/test_*.py`
que toca el PR tiene un test con `cubre: SPEC/CA` en su docstring (opcion 1 de tres). Limite
conocido: si el PR toca una linea de un fichero de tests, cuentan tambien las etiquetas que ya
habia en el. Se revisara al conectar el agente a PRs reales, que es donde se construye la entrada.

## Puntos 4 y 5: iteraciones y que cambio entre v0 y v1

| Version | Precision | Recall | Matriz | Informe |
|---|---|---|---|---|
| v0 (semilla) | 1,00 | 0,10 | vp 1, fp 0, vn 5, fn 9 | `evaluacion_v0.json` |
| v1, primera medicion | 0,91 | 1,00 | vp 10, fp 1, vn 4, fn 0 | sin guardar |
| v1 tras la revision | 1,00 | 1,00 | vp 10, fp 0, vn 5, fn 0 | `evaluacion_v1.json` |

Que cambio y por que mejoro:

| v0 | v1 | Efecto |
|---|---|---|
| "Conforme" si algun test menciona el id de la spec | Cada criterio declarado necesita su propio test con `cubre:` en el docstring | Es lo que mas sube el recall: un PR con tests de otro criterio, o que declara dos criterios y prueba uno, ya no pasa |
| No mira que ficheros se tocan | Cada fichero del PR debe estar en las rutas de la spec | Detecta PRs que tocan codigo de otra spec |
| Cualquier test vale | Un test con skip/xfail, sin asercion o con una asercion que siempre se cumple es un hallazgo | Detecta tests decorativos (checklist, punto 3) |
| No mira el codigo | `float(` en `src/` es un hallazgo (invariante 2) | Detecta calculos con coma flotante |

De la primera medicion a la version final, el revisor (Opus) encontro dos fallos de las reglas:

- `assert f(e) == f(e)` se tomaba por asercion vacia, cuando es como se prueba que algo es
  determinista. Ahora solo es vacia si compara constantes (`1 + 1 == 2`) o la misma variable.
- Un `cubre:` en `tests/conftest.py` contaba como evidencia, aunque pytest no lo ejecuta como
  test. Ahora solo cuentan los `tests/test_*.py`, igual que en la trazabilidad.

Ademas, la lectura de `cubre:` paso a hacerse con `ast`. Tras estas correcciones desaparece la
falsa alarma de la primera medicion.

Limites conocidos:

- 15 casos son pocos: un caso nuevo mal clasificado bajaria la precision a 0,91.
- La regla de alcance es estricta: un PR de spec que toque tambien la bitacora o cree un fichero
  de tests nuevo sale no conforme, porque esas rutas no estan en la linea `Rutas:` de la spec.
- `float` se detecta por texto: `float(` si, pero no `7.5 / 2` ni `round(`. El redondeo unico
  (invariante 1) no se comprueba.
- El conjunto de evaluacion no se sube al repo, asi que S4a-04 solo se puede comprobar en local.

## Entregable: el agente publica sus veredictos en PRs reales

- `.github/workflows/conformidad.yml`: en cada PR a main ejecuta `herramientas/conformidad_pr.py`,
  que lee la spec declarada en la descripcion, pasa al agente los ficheros del diff y publica el
  veredicto como comentario. Si el PR se actualiza, edita el mismo comentario.
- No usa ningun modelo ni credenciales externas: corre en GitHub Actions con el token del propio
  repositorio. Informa; no bloquea el merge (convertirlo en gate es trabajo de S6).
- La plantilla de PR incluye `AULA_SPEC_ID` y `AULA_CRITERIOS`. Si no se rellenan, el agente
  comenta que el PR no declara spec y como declararla.
- `conformidad_pr.py` no encontraba el paquete `agentes` al lanzarse como
  `python herramientas/conformidad_pr.py`: se anade la raiz del repositorio al path.
