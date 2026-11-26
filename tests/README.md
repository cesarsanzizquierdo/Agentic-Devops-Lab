# Indice de tests por estacion

Los tests no se agrupan en carpetas: los verificadores de las estaciones (`labs/*/verificar.py`),
los casos de `evals/dorado*/` y varios agentes nombran sus rutas exactas. Este indice dice de que
estacion es cada fichero y que prueba.

| Estacion | Fichero | Que prueba |
|---|---|---|
| Plantilla | `conftest.py`, `utilidades.py` | configuracion de pytest y datos de prueba comunes |
| S2 | `test_media_expediente.py` | nota media, creditos y progreso segun SPEC-002 (lo usa `labs/S2-sdd/verificar.py`) |
| S2 | `test_reglas_matricula.py` | reglas de matricula segun SPEC-001 |
| S3 | `test_hooks.py` | permisos de `.claude/settings.json` y hooks de rutas protegidas y de tests antes de commit |
| S3 | `test_subagentes.py` | subagentes implementador y revisor |
| S3 | `test_api_expediente.py` | API de expediente: numeros como texto con dos decimales (SPEC-002 CA-08) |
| S4a | `test_mcp_herramientas.py`, `test_mcp_transporte.py` | servidor MCP: herramientas y transporte JSON-RPC |
| S4a | `test_agente_conformidad.py`, `test_conformidad_pr.py` | agente de conformidad y su comentario en los PRs |
| S4b | `test_contrato_flotilla.py` | contrato de la flotilla y que el codigo de cada agente lo cumple |
| S4b | `test_flotilla_mcp.py` | acceso de los agentes al servidor MCP, filtrado por el contrato |
| S4b | `test_agente_triaje.py`, `test_agente_modernizacion.py` | agentes de triaje y de modernizacion |
| S4b | `test_flotilla_decisiones.py`, `test_coordinador_flotilla.py` | conflicto, handoff, grabacion, paralelo y worktrees |
| S5 | `test_caracterizacion_legado.py` | comportamiento del modulo heredado y cada desviacion declarada |
| S5 | `test_equivalencia_legado.py` | original frente al modulo actual sobre los 500 expedientes del corpus |
| S5 | `oraculo/calculadora_expediente_v1_original.py` | no es un test: copia exacta del legado original, referencia de la equivalencia |
