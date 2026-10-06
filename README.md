# Portería con reconocimiento de placas

Sistema para la portería de un conjunto residencial: lee las placas de los vehículos, abre la puerta a quien está autorizado y deja registro de cada ingreso y salida. Es un proyecto de aprendizaje, así que cada pieza está documentada.

- Plan completo: [`docs/plan-proyecto.md`](docs/plan-proyecto.md)
- Decisiones de arquitectura: [`docs/decisiones/`](docs/decisiones/)

## Estructura

| Carpeta | Qué contiene | Fase en que arranca |
|---|---|---|
| [`apps/web/`](apps/web/) | Interfaz web en Next.js (guarda, administración y residente) | 3 |
| [`services/api/`](services/api/) | Backend FastAPI con PostgreSQL | 0 |
| [`services/edge-agent/`](services/edge-agent/) | Equipo local de la portería: captura, lectura de placas, decisión y puerta | 0 (contrato) y 1 |
| [`packages/`](packages/) | Paquetes compartidos entre servicios; por ahora `contracts` con los eventos como `PlateRead` | 0 |
| [`ml/`](ml/) | Datasets, entrenamiento y evaluación de YOLO y OCR | 1 |
| [`infra/`](infra/) | Docker Compose para la infraestructura local; por ahora PostgreSQL 18 y Adminer opcional | 0 |
| [`docs/`](docs/) | Plan, decisiones y privacidad | — |

## Requisitos

| Herramienta | Para qué | Comprobar |
|---|---|---|
| Python 3.12 o superior | API y equipo local | `python --version` |
| [uv](https://docs.astral.sh/uv/) | Entornos y dependencias de Python | `uv --version` |
| Node 22 o superior y pnpm | Interfaz web | `node --version`, `pnpm --version` |
| Docker Desktop | PostgreSQL y servicios en contenedores | `docker compose version` |

## Calidad de código

Ver el [ADR 0003](docs/decisiones/0003-calidad-de-codigo.md). Después de clonar, instala los hooks de git una sola vez:

```powershell
uvx pre-commit install
```

Desde ese momento, cada `git commit` revisa formato, lint y tipos; el mensaje del commit debe seguir Conventional Commits (`feat: ...`, `fix: ...`, `docs: ...`, `chore: ...`); y cada `git push` corre las pruebas.

| Qué | Comando |
|---|---|
| Todos los chequeos sobre todo el repositorio | `uvx pre-commit run --all-files` |
| Solo formatear y corregir lint | `uvx pre-commit run ruff-format --all-files` y `uvx pre-commit run ruff-check --all-files` |
| Pruebas de un servicio | `uv run --directory services/edge-agent pytest` |
| Tipos de un servicio | `uv run --directory services/edge-agent mypy` |

En Cursor o VS Code conviene instalar la extensión de Ruff para ver los errores mientras escribes.

## Infraestructura local

Ver [`infra/README.md`](infra/README.md) y el [ADR 0005](docs/decisiones/0005-infraestructura-local-docker-compose.md). Con Docker Desktop abierto, desde la raíz del repositorio:

| Qué | Comando |
|---|---|
| Levantar PostgreSQL y esperar a que esté listo | `docker compose -f infra/compose.yaml up -d --wait` |
| Comprobar que todo funciona (Git Bash) | `bash infra/scripts/smoke.sh` |
| Apagar (los datos se conservan) | `docker compose -f infra/compose.yaml down` |

## Estado

Fase 0 en curso. Ver el avance en la sección "Fases" del plan.
