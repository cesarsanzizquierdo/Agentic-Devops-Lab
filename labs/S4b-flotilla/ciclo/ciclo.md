# Ciclo de la flotilla

- Revision: `faff074f2600`
- Escenario: redondeo-por-asignatura. Un PR redondea la nota de cada asignatura a un decimal antes de ponderarla. Rompe el invariante 1 de CLAUDE.md: el redondeo se aplica una sola vez y al final.
- Ficheros que cambia: src/aula/reglas/media.py
- Contrato: version 1.0.0
- Empieza: 2026-11-17T11:12:11+00:00
- Estado: **completo**

## Cronologia

Segundos desde el comienzo del ciclo.

| Agente | Worktree | Empieza | Acaba | Resultado |
|---|---|---|---|---|
| conformidad-spec | `~\aula-flotilla\conformidad-spec` | 0.00 | 0.77 | no_conforme: criterios sin test: CA-04 |
| triaje-pipeline | `~\aula-flotilla\triaje-pipeline` | 0.00 | 23.25 | rojo: 2 failed, 201 passed in 20.91s |
| modernizacion-legado | `~\aula-flotilla\modernizacion-legado` | 0.00 | 0.86 | 10 hallazgos, 4 pasos |

Todos empezaron antes de que acabara ninguno: se ejecutaron a la vez.

## Conflictos

- `src/aula/reglas/media.py`: gana triaje-pipeline; se pospone la propuesta de modernizacion-legado sobre este fichero.

## Lo que llega al humano (handoff)

- **conformidad-spec**: El veredicto, para decidir el merge.
  - spec: SPEC-002
  - veredicto: no_conforme
  - criterios_sin_cubrir: CA-04
  - fuera_de_alcance: -
- **triaje-pipeline**: La incidencia: cada fallo con su categoria, su criterio y los ficheros que hay que mirar.
  - estado: rojo
  - resumen: 2 failed, 201 passed in 20.91s
  - fallos: 2 (el detalle esta en ciclo.jsonl)
  - propone_tocar: src/aula/reglas/media.py
- **modernizacion-legado**: La propuesta por pasos. Ningun paso se aplica sin aprobacion humana.
  - hallazgos: 10 (el detalle esta en ciclo.jsonl)
  - pasos:
    1. Caracterizar el modulo heredado: escribir tests/test_caracterizacion_legado.py con su comportamiento actual y commitearla antes de tocar el codigo (regla dura de S5).
    2. Cambiar la coma flotante por Decimal (invariante 2).
    3. Redondear una sola vez y al final (invariante 1).
    4. Leer del plan las constantes que repiten sus parametros.
  - propone_tocar: src/aula/legado/calculadora_expediente_v1.py; src/aula/reglas/media.py; tests/test_caracterizacion_legado.py

## Worktrees activos

```
<repositorio> faff074 [S4b-flotilla]
~/aula-flotilla/conformidad-spec                 faff074 (detached HEAD)
~/aula-flotilla/modernizacion-legado             faff074 (detached HEAD)
~/aula-flotilla/triaje-pipeline                  faff074 (detached HEAD)
```
