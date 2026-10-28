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

`aula_cli check` no esta en la allowlist a proposito: reescribe `.aula/progreso.json` y
puede desellar estaciones, asi que debe pedir confirmacion.

### Limitacion conocida

Los hooks de rutas y las reglas `deny` vigilan las herramientas de edicion, no lo que
escribe un comando de Bash (por ejemplo `echo x > manifiestos/a.yaml`). Las reglas de
Bash de Claude Code comparan el inicio del comando y no pueden detectar una redireccion
en mitad de el. La barrera para ese caso es humana: CODEOWNERS exige revision en
`manifiestos/`, `labs/` y `.github/`.
