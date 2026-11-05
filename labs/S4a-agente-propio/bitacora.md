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

Revision (revisor, Opus): APROBAR CON CAMBIOS. Se aplicaron:

| Hallazgo | Arreglo |
|---|---|
| El servidor se caia con `"arguments": 5` | Se validan los tipos y el bucle tiene red de seguridad (-32603) |
| Test de trazabilidad decorativo (solo miraba las claves) | Comprueba que CA-01 esta cubierto y que no se pierde ningun criterio |
| Ramas sin test: fallidos, tiempo agotado, isError, ping | Tests nuevos, con pytest simulado donde hace falta |
| Si pytest no llegaba a ejecutar (ruta inexistente) no se sabia por que | Se devuelve el motivo y el codigo |
| Cambio de workflows mezclado con el servidor | Separado en su propio PR |

El trabajo se partio en tres PRs para no pasar de 400 lineas: control de workflows,
transporte y herramientas.

Prueba en vivo desde Claude Code: al reiniciar, Claude Code cargo `aula-contexto` desde
`.mcp.json` y aparecieron sus cinco herramientas (`mcp__aula-contexto__...`). Llamadas reales:

- `trazabilidad("SPEC-002")`: 11 criterios, 100 % cubiertos, con el test que cubre cada uno.
- `version_plan("PLAN-2024")`: version 1.2.0, 192 creditos, 6 convocatorias, 30 asignaturas.

Sorpresa: VS Code tiene su propio menu "Add MCP Server" (para Copilot), que no es el de
Claude Code. No hace falta usarlo: Claude Code lee `.mcp.json` solo.
