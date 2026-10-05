# 0002. uv para Python y pnpm para Node

- **Estado:** Aceptado
- **Fecha:** 2026-10-04

## Contexto

Hace falta una forma repetible de crear entornos e instalar dependencias, tanto en el equipo de desarrollo (Windows) como en los contenedores Docker y en el mini-PC de la portería. Las versiones exactas deben quedar fijadas para que "funciona en mi máquina" también funcione en las demás.

## Opciones

**Python:**

1. **pip + venv:** viene con Python, pero no genera un archivo de bloqueo (lockfile) por sí solo y es lento.
2. **Poetry:** maneja dependencias y lockfile, pero es más lento y tiene su propio formato de configuración.
3. **uv:** muy rápido, usa `pyproject.toml` estándar, genera `uv.lock` con las versiones exactas y puede instalar la versión de Python que el proyecto necesite.

**Node:**

1. **npm:** viene con Node.
2. **pnpm:** más rápido, ocupa menos disco y es estricto con las dependencias que no se declararon.

## Decisión

uv para los servicios de Python y pnpm para la web. Ambos ya están instalados en el equipo de desarrollo.

Un **lockfile** es un archivo que guarda la versión exacta de cada dependencia (y de las dependencias de esas dependencias). Ejemplo: `pyproject.toml` dice "FastAPI 0.115 o superior" y `uv.lock` dice "FastAPI 0.115.6 exactamente". Así todos instalan lo mismo.

## Consecuencias

- Cada servicio de Python tiene su `pyproject.toml` y su `uv.lock`, que sí se suben a git.
- Los comandos de los README usan `uv run ...` y `pnpm ...`.
- Quien clone el proyecto debe instalar uv y pnpm.
