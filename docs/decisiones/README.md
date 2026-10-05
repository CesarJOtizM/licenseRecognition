# Decisiones de arquitectura (ADR)

Un ADR (Architecture Decision Record) es un documento corto que explica una decisión importante: qué problema había, qué opciones se consideraron, qué se eligió y qué consecuencias trae. Sirve para que, meses después, se entienda por qué el proyecto es como es.

Cada archivo se llama `NNNN-titulo.md` y sigue la [plantilla](0000-plantilla.md). Un ADR no se borra: si una decisión cambia, se escribe uno nuevo que lo reemplaza y se marca el anterior como "Reemplazado por NNNN".

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-monorepo.md) | Un solo repositorio (monorepo) para todo el sistema | Aceptado |
| [0002](0002-herramientas-uv-pnpm.md) | uv para Python y pnpm para Node | Aceptado |
