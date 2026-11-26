# Bitacora de S5

Registra caracterizacion antes del refactor y las desviaciones justificadas.

## Aviso: S5-02 falla por un commit de S3, no por el orden de S5

**Que pasa.** El criterio S5-02 ("la caracterizacion precede al refactor en el historial") sale
en rojo aunque en S5 la caracterizacion se commitea antes de tocar una sola linea del legado.

**Por que.** El commit `3c6b882` de S3 se titulo "refactor: unificar creditos_superados en
media.py". Cambio `motor.py` y dos specs; no toco `src/aula/legado/`. Es el commit 24 del
historial, y cualquier commit de caracterizacion de S5 ira detras.

**Como valida el verificador.** `orden_en_historial(r"caracteriz", r"^refactor", por_asunto=True)`
(`aula_cli/verificacion.py`) recorre `git log --reverse` y solo mira el titulo de cada commit: el
primero que contiene "caracteriz" tiene que ir antes del primero que empieza por "refactor". No
mira que ficheros cambia cada commit.

**Que se hace.**
- El orden real de S5 se demuestra con los SHAs de sus commits al final de esta bitacora:
  caracterizacion, equivalencia, apertura del legado y refactor, en ese orden.
- No se reescribe el historial de main ni se toca `verificar.py`.
- Si al final de la estacion no hay otra salida, se usara
  `python -m aula_cli desbloquear S5 --motivo "..."`, con este aviso como motivo.

## Que se hizo

Cinco PRs, en este orden:

1. **#28 Caracterizacion.** `tests/test_caracterizacion_legado.py` fija lo que hacia el legado,
   con los valores calculados a mano. No toca `src/aula/legado/`.
2. **#29 Equivalencia.** Una copia exacta del original en `tests/oraculo/` y
   `tests/test_equivalencia_legado.py`, que compara original y modulo actual sobre los 500
   expedientes. Antes del refactor daba 500 de 500 identicos.
3. **#30 Refactor sin cambiar numeros.** Se abre `src/aula/legado/`, se elimina el codigo muerto
   (D-01) y se extraen las reglas. La equivalencia sigue en 500 de 500.
4. **#31 Correcciones.** Cada defecto se arregla en su commit y se declara en
   `src/aula/legado/DESVIACIONES.md` (D-02 a D-07). Al final el legado usa las reglas de
   `src/aula/reglas/media.py`: una sola implementacion de SPEC-002.
5. **Cierre.** Se vuelve a proteger `src/aula/legado/`, indice de tests y esta bitacora.

## El orden, demostrado

Posicion en el historial de main (`git log --reverse`, la numeracion del verificador):

| Commit | Que es |
|---|---|
| 76 `765bba1` | `test: caracterizacion del modulo heredado`: ningun cambio en el legado |
| 77 `bf35e44` y 79 `0ca187e` | la equivalencia sobre el corpus: ningun cambio en el legado |
| 81 `e6fa177` | se abre `src/aula/legado/`, con la caracterizacion y la equivalencia ya en main |
| 82 `91caa6a` | primer cambio del legado: `refactor: eliminar el codigo muerto del modulo heredado` |
| 83 a 89 | el resto del refactor y las correcciones, cada uno con la bateria en verde |

`git log --format=%h -- src/aula/legado/` lo confirma: antes de `91caa6a` el legado solo tiene el
commit inicial de la plantilla.

## Lo que se descubrio al ejecutar

Ademas de los dos comportamientos que el propio fichero marcaba como no documentados:

| Comportamiento | Ejemplo |
|---|---|
| `no_documentado_1`: la convalidada sumaba 5,0 x creditos arriba y nada abajo | aprobada 6,0 + convalidada (6 creditos cada una) = 11,0, por encima de 10 |
| `no_documentado_2`: redondeaba cada asignatura antes de sumar | 6,004 + 6,004 + 6,009 = 6,00; redondeando al final, 6,01 |
| la cache devolvia el resultado antiguo | recalcular a un estudiante con una nota nueva daba lo de antes |
| el progreso redondeaba el empate al par | 6 creditos de 192 = 3,125 % daba 3,12 |
| la coma flotante movia notas | 6,675 se guarda como 6,67499... y daba 6,67 |
| el maximo de convocatorias era un 6 fijo | no seguia al plan del estudiante |

## Desviaciones

El detalle (categoria, causa y efecto aguas abajo) esta en `src/aula/legado/DESVIACIONES.md`.

| Id | Que cambia | Efecto en los 500 expedientes |
|---|---|---|
| D-01 | se elimina el codigo muerto | ninguno |
| D-02 | la convalidada no entra en la media | 360 medias, hasta 10,00; 469 estudiantes cambian de puesto en becas |
| D-03 | redondeo una sola vez al final | 35 medias, 0,01 como mucho; 79 cambian de puesto |
| D-04 | `Decimal` en vez de coma flotante | 4 medias y 61 progresos, 0,01 como mucho; 8 cambian de puesto |
| D-05 | sin cache | ninguno |
| D-06 | usa las reglas de `media.py`; un dato mal escrito es un error | ninguno |
| D-07 | el maximo de convocatorias es el del plan | ninguno (0 de 15.000 respuestas) |

Equivalencia final: 106 expedientes identicos, 360 cambios justificados por D-02, 10 medias por
D-03 o D-04 y 61 progresos por D-04; ninguna desviacion sin justificar. Con todos los arreglos,
el legado da exactamente lo mismo que `media.py` en los 500.

## Problemas y como se resolvieron

| Problema | Solucion |
|---|---|
| El test de equivalencia pasaba en local y fallaba en el CI | `datos/expedientes_sinteticos.json` esta en `.gitignore`. El test genera el corpus con `herramientas/generar_corpus.py`, que es determinista |
| `DESVIACIONES.md` podia justificar diferencias que aun no existian | El test lee los identificadores D-0n del fichero; cada uno se escribe en el mismo commit que su arreglo |
| `src/aula/legado/` estaba protegido en tres sitios | Se abrio con aprobacion humana despues de mergear la caracterizacion y la equivalencia, y se volvio a cerrar al final |

## Antes y despues

El agente de modernizacion de S4b sobre `src/aula/legado/calculadora_expediente_v1.py`:

- antes: 9 hallazgos (sin caracterizar, coma flotante en tres funciones, un redondeo dentro de un
  bucle y cuatro constantes fijas);
- despues: ninguno.
