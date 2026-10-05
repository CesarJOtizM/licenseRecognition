# 0003. Calidad de código: Ruff, mypy estricto, pytest, pre-commit y CI

- **Estado:** Aceptado
- **Fecha:** 2026-10-04

## Contexto

Queremos que los errores de estilo, de tipos y las pruebas rotas se detecten antes de llegar al repositorio, y no meses después. El repositorio tiene varios lenguajes: Python en la API, el equipo local y ML, y TypeScript en la web (desde la fase 3).

## Opciones

**Hooks de git** (scripts que git ejecuta solo, por ejemplo antes de cada commit):

1. **Husky:** el estándar en proyectos de Node. Necesita un `package.json` y Node en la raíz, aunque las primeras fases sean solo Python.
2. **Lefthook:** rápido y sirve para varios lenguajes, pero es un binario que hay que instalar aparte.
3. **pre-commit:** sirve para varios lenguajes, tiene un catálogo grande de hooks listos (Ruff, ESLint, Prettier, detección de llaves privadas) y se ejecuta con `uvx` sin instalar nada global.

**Linter y formateador de Python:** flake8 + black + isort (tres herramientas) o **Ruff** (una sola, mucho más rápida, con las mismas reglas).

**Tipos:** mypy básico, **mypy estricto** o nada.

## Decisión

- **Ruff** como linter y formateador, configurado una sola vez en `ruff.toml` en la raíz.
- **mypy en modo estricto** en cada servicio. Es más fácil empezar estricto que endurecerlo después con cientos de errores acumulados.
- **pytest con pytest-cov** en cada servicio, con una cobertura mínima del 80 %.
- **pre-commit** con tres momentos:
  - `pre-commit` (al hacer commit): formato, lint, tipos, archivos grandes y llaves privadas.
  - `commit-msg` (al escribir el mensaje): formato [Conventional Commits](https://www.conventionalcommits.org/es/), por ejemplo `feat: contrato PlateRead`. Además, `scripts/quitar_coautor_ia.py` borra los trailers `Co-authored-by: Cursor` que algunas herramientas agregan solas, porque los mensajes del proyecto no llevan atribución de IA.
  - `pre-push` (antes de `git push`): las pruebas, que son más lentas.
- **GitHub Actions** corre los mismos chequeos en cada push a `main` y en cada pull request. Así no dependen de que alguien haya instalado los hooks en su equipo.

## Consecuencias

- Cada servicio nuevo de Python agrega en su `pyproject.toml` las secciones `[tool.mypy]`, `[tool.pytest.ini_options]` y `[tool.coverage.report]`, y sus hooks locales en `.pre-commit-config.yaml` y `ci.yml`.
- Cuando llegue la web se agregan ESLint y Prettier al mismo `.pre-commit-config.yaml`; no hace falta Husky.
- Los hooks se pueden saltar con `git commit --no-verify`, pero la CI los vuelve a correr.
- Las versiones de los hooks se actualizan con `uvx pre-commit autoupdate`.
