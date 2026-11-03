# SPEC-002: cálculo de expediente

Versión: v0.1.0 | Estado: activa
Autor: plantilla del laboratorio | Revisor: pendiente

> Especificación de partida para S2. Antes de implementar, registra las preguntas
> que necesiten una decisión de negocio y acuerda la resolución con el mentor.

## Propósito

Calcular el estado académico de un estudiante respecto de su plan: nota media
ponderada por créditos, créditos superados y porcentaje de título completado.
De la nota media dependen procesos aguas abajo, entre ellos la ordenación para
becas, así que la reproducibilidad exacta del número es un requisito, no un detalle.

## Entradas y salidas

| Elemento | Tipo | Restricciones |
|----------|------|---------------|
| Expediente | lista de registros académicos | Un registro por convocatoria consumida o convalidación |
| Plan | plan versionado | Determina créditos por asignatura y créditos del título |
| Nota media | decimal | Exactamente dos decimales, redondeo half-up |
| Créditos superados | entero | |
| Progreso | decimal | Porcentaje con dos decimales |

## Invariantes

- INV-01: el redondeo se aplica una sola vez y al final del cálculo. Ningún valor intermedio se redondea.
- INV-02: el cálculo usa aritmética decimal, nunca coma flotante binaria.
- INV-03: el resultado es determinista: el mismo expediente y el mismo plan producen siempre el mismo número, con independencia del orden de los registros.

## Criterios de aceptación

- CA-01: dado un expediente con asignaturas aprobadas en primera convocatoria, cuando se calcula la nota media, entonces es la media de las notas ponderada por los créditos de cada asignatura, con dos decimales.

- CA-02: dada una asignatura repetida y finalmente aprobada, cuando se calcula la nota media, entonces su calificación se incorpora conforme a la normativa académica vigente.
RESOLUCION: dada una asignatura repetida y finalmente aprobada, cuando se calcula la nota media, entonces se toma exclusivamente la calificación de la última convocatoria aprobada. Los intentos previos suspensos o no presentados quedan excluidos tanto del numerador como del denominador.

- CA-03: dada una asignatura convalidada, cuando se calcula la nota media, entonces recibe el tratamiento previsto para las convalidaciones.
RESOLUCION:dada una asignatura convalidada, cuando se calcula la nota media, entonces queda excluida tanto del numerador como del denominador al no disponer de una calificación numérica evaluable.

- CA-04: dado cualquier expediente, cuando se calcula la nota media, entonces el redondeo a dos decimales se aplica una sola vez sobre el cociente final y nunca sobre cada asignatura.
- CA-05: dada una asignatura convalidada, cuando se calculan los créditos superados, entonces sus créditos sí cuentan como superados.
- CA-06: dado un expediente, cuando se calcula el progreso, entonces es el porcentaje de créditos superados sobre los créditos del título, con dos decimales.
- CA-07: dado un expediente sin ninguna asignatura computable, cuando se calcula la nota media, entonces devuelve 0,00 sin error.

- CA-08: dado un expediente, cuando se consulta `GET /expedientes/{estudiante_id}`, entonces `nota_media`, `progreso` y `progreso_pct` se devuelven como string con dos decimales fijos (por ejemplo "7.00"), sin pasar por coma flotante, y `progreso_pct` es igual a `progreso`.

## Casos límite

| Caso | Resultado esperado |
|------|--------------------|
| Expediente vacío | Nota media 0,00, créditos 0, progreso 0,00 |
| Todas las asignaturas convalidadas | Nota media 0,00 (sin asignaturas computables en media) y créditos superados iguales a la suma de créditos convalidados |
| Asignatura aprobada en convocatoria 2 y también en convocatoria 4 | Prevalece y computa únicamente la nota obtenida en la convocatoria 4 por ser la más reciente |
| Nota con más de dos decimales en origen | Se conserva íntegra en el numerador y solo se redondea el cociente final |
| Media exactamente en el punto medio, por ejemplo 7,005 | Redondeo half-up a 7,01 |

## Fuera de alcance

Rutas: src/aula/reglas/media.py, tests/test_media_expediente.py, specs/SPEC-002-expediente.md

- Menciones, matrículas de honor y premios extraordinarios.
- Reconocimiento de créditos por actividades no académicas.
- Media de acceso a máster, que usa otra normativa.
- Decisión de convalidar, que es un proceso previo.

## Ambigüedades detectadas y resolución

| # | Ambigüedad | Resolución adoptada | Alternativas descartadas y por qué |
|---|-----------|---------------------|-------------------------------------|
| A-01 | En asignaturas repetidas con varios intentos (CA-02), el enunciado inicial remitía de forma genérica a la "normativa vigente" sin especificar si debía usarse la última nota aprobada, la nota más alta o el promedio de todas las convocatorias, ni si los suspensos sumaban créditos en el denominador. | Se toma únicamente la calificación de la última convocatoria aprobada, ignorando por completo las convocatorias previas (suspensas, no presentadas o aprobadas anteriores) tanto en el numerador como en el denominador. | Promediar todos los intentos castigaría por partida doble al estudiante (ya penalizado por el límite de convocatorias consumidas). Escoger la nota más alta incentivaría repetir asignaturas ya aprobadas de forma oportunista. |
| A-02 | En una asignatura convalidada (CA-03), no se definía qué significaba "el tratamiento previsto": si debía asignarse una nota por defecto en el numerador, si sus créditos debían sumar en el denominador o si debía omitirse de la fracción. | La asignatura convalidada no interviene ni en el numerador ni en el denominador de la nota media, aunque sus créditos sí se suman al total de créditos superados y al progreso del título (CA-05). | Incluirla en el numerador con una nota fija de 5.0 sin sumar sus créditos en el denominador (comportamiento defectuoso detectado en `calculadora_expediente_v1.py`) distorsiona la media ponderada y puede generar notas superiores a 10. Asignarle un 5.0 en ambos términos penalizaría artificialmente la media real de los alumnos con buen expediente que convalidan asignaturas.
| A-03 | La spec fija que nota media y progreso son decimales con dos decimales, pero no define la serializacion JSON de `GET /expedientes/{estudiante_id}` (`nota_media`, `progreso`, `progreso_pct`). Hoy se convierten a `float`, lo que contradice INV-02. Opciones: (a) string "7.35"; (b) numero JSON emitido desde Decimal sin pasar por float; (c) otra. Tampoco esta claro si `progreso` y `progreso_pct` (hoy con el mismo valor) deben ser dos campos o uno solo. | Decidido por el humano el 2026-10-29: `nota_media`, `progreso` y `progreso_pct` se serializan como string con dos decimales fijos (por ejemplo "7.35", "7.00"), nunca via float. Se mantienen `progreso` y `progreso_pct`; este ultimo es un alias por compatibilidad. Ver CA-08. | (b) Numero JSON: obliga a una serializacion propia o a pasar por float. Un 7 exacto saldria como 7 o 7.0. |
| A-04 | `creditos_superados(expediente, plan)` esta duplicada con `src/aula/reglas/motor.py` (SPEC-001, CA-06, usada por `creditos_pendientes` y `prioridad`). Son equivalentes, pero ninguna spec fija a cual de las dos pertenece ni en que sentido va la dependencia. Las rutas declaradas en "Fuera de alcance" de cada spec no incluyen un modulo comun | Decidido por el humano el 2026-11-03: la implementacion unica vive en `src/aula/reglas/media.py` y este fichero no se modifica. `motor.py` elimina su copia e importa `creditos_superados` de `media`. Motivo, segun el humano: "media.py y sus tests no cambian (S2-06 del laboratorio muta media.py); la matricula consume datos del expediente; asi no hace falta un fichero nuevo ni ampliar las rutas de las specs". Ver SPEC-001 A-05 | (a) Que viva en `motor.py` y `media.py` la importe: obligaria a modificar `media.py` y SPEC-002 pasaria a depender de `motor.py`. (c) Modulo comun nuevo (por ejemplo `reglas/creditos.py`): ambos modulos importarian de el, obligaria a modificar `media.py` y habria que anadir la ruta del modulo a las rutas de una de las specs. |
