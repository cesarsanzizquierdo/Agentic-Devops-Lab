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
