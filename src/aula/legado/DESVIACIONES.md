# Desviaciones del modulo heredado

Cada diferencia entre el original (`tests/oraculo/calculadora_expediente_v1_original.py`) y
`calculadora_expediente_v1.py` se declara aqui, con su categoria, su causa y su efecto aguas abajo.
`tests/test_equivalencia_legado.py` lee los identificadores de este fichero: una diferencia que no
explique ninguna desviacion declarada hace fallar la equivalencia sobre los 500 expedientes.

La interfaz que usa el proceso nocturno se conserva con la misma firma: `calcular`,
`calcular_lote`, `convocatorias` y `puede_matricular`. Las funciones internas del calculo
(`es_aprobada`, `hay_convalidacion`, `ultima_aprobada`...) se reorganizan en el refactor; nada
del repositorio las usa desde fuera.

## D-01. Se elimina el codigo muerto

- **Categoria:** eliminacion de codigo muerto. No cambia ningun numero.
- **Que cambia:** desaparecen `media_simple`, `formatea`, `exporta_csv`, `DEBUG`, `_log` y la
  constante `APROBADO`, que no se usaba. El propio fichero decia "quedo de la migracion de 2020,
  no lo llama nadie", y `DEBUG` era siempre `False`, asi que `_log` nunca escribia nada.
- **Causa:** nada del repositorio los llama (comprobado con una busqueda en todo el codigo, los
  tests, los workflows y los datos).
- **Efecto aguas abajo:** ninguno en los resultados: los 500 expedientes dan lo mismo. Si algun
  proceso externo al repositorio llamara a `exporta_csv` o `media_simple`, fallaria con
  `AttributeError`; habria que avisar a secretaria antes de desplegar.
- **Expedientes afectados:** 0 de 500.

## D-02. La convalidada no entra en la media

- **Categoria:** correccion de defecto (comportamiento no documentado 1).
- **Que cambia:** la convalidada sumaba 5,0 x creditos en el numerador y nada en el
  denominador; ahora no entra en la media. Sus creditos siguen contando como superados.
  Ejemplo: una aprobada con 6,0 y una convalidada (6 creditos cada una) daban 11,0 y ahora 6,0.
- **Causa:** contradice SPEC-002 CA-03 y su ambiguedad A-02, que ya lo describia como
  "comportamiento defectuoso detectado en `calculadora_expediente_v1.py`": distorsiona la media
  y puede dar notas por encima de 10.
- **Efecto aguas abajo:** cambia la nota media de 360 de los 500 expedientes (los que tienen
  alguna convalidada), hasta 10,00 puntos; 37 tenian una media por encima de 10. Al ordenar por
  media para becas, 469 estudiantes cambian de puesto: la ordenacion de becas hay que
  recalcularla y avisar a secretaria antes de desplegar.
- **Expedientes afectados:** 360 de 500.

## Deuda conocida que se conserva

- `MAX_CONV = 6` en `puede_matricular`: repite el `max_convocatorias` de PLAN-2024. La funcion no
  recibe el plan, asi que no puede leerlo sin cambiar su firma, que es parte de la API historica.
