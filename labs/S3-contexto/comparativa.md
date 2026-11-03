# Comparativa: Claude Code frente a OpenCode

## Que se pudo medir y que no

- **Claude Code: medido.** Resolvio el encargo del punto 5 (nota media de float a texto) dentro
  del ciclo escritor/revisor. Hay diff, tests y revisiones.
- **OpenCode: no se pudo ejecutar.** Se instalo (1.19.5), se configuro con el modelo gratuito
  GLM-5.3-Flash Free y se le envio el mismo encargo. Respondio "Free limit reached" al primer
  mensaje y no ejecuto nada (ver `error_opencode.png` y la bitacora). Sus filas salen de su
  documentacion oficial y van marcadas como "documentado".

## Tabla

| Dimension | Claude Code (medido) | OpenCode (documentado) |
|---|---|---|
| Contexto del proyecto | `CLAUDE.md`. Lo respeto: pregunto antes de cambiar la API y anoto la ambiguedad en la spec | `AGENTS.md`, y lee `CLAUDE.md` si no hay `AGENTS.md`: nuestro contrato serviria sin cambios |
| Permisos | `.claude/settings.json` con `allow`, `ask` y `deny`. `deny` probado en vivo | `opencode.json` con `allow`, `ask` y `deny` por herramienta y patron. Gana la ultima regla que coincide |
| Hooks | Scripts en cualquier lenguaje antes y despues de cada herramienta. Los nuestros, en Python, probados | Plugins en JavaScript/TypeScript (`tool.execute.before/after`), que bloquean lanzando un error. Habria que reescribir los nuestros |
| Subagentes | `.claude/agents/*.md` con modelo y herramientas fijados. Probados | `.opencode/agents/*.md` u `opencode.json`, con modelo y permisos por agente. Equivalente |
| Modelos | Solo Anthropic | Varios proveedores. Con una suscripcion de Claude no se puede (lo prohibe Anthropic) |
| Coste en este laboratorio | Incluido en el acceso que ya tenemos | Gratuito muy limitado (agotado al primer mensaje). Suscripcion de 10 $/mes |
| Resultado del encargo | 65 tests en verde y APROBAR del revisor tras las correcciones | Sin resultado |

## Criterio de eleccion

**Para este proyecto, Claude Code**, por tres motivos:
1. Los controles del proyecto (permisos, hooks y subagentes) ya estan construidos y probados para el.
2. Es el unico que se pudo ejecutar con el acceso disponible.
3. Se ha medido que respeta el contrato de `CLAUDE.md`.

**Cuando tendria sentido OpenCode:** si se necesita usar modelos de varios proveedores, o no
depender de uno solo. Migrar costaria poco en contexto (lee `CLAUDE.md`) y subagentes, algo mas en
permisos (reescribirlos en `opencode.json`) y mas en hooks (reescribirlos en JavaScript).

**Lo que esta comparativa no puede afirmar:** la calidad del codigo de OpenCode, si respeta las
reglas en la practica o su coste por tarea, porque no llego a ejecutar nada. Queda pendiente de
validar con el mentor.
