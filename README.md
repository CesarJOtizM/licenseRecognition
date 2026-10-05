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
| [`ml/`](ml/) | Datasets, entrenamiento y evaluación de YOLO y OCR | 1 |
| [`infra/`](infra/) | docker-compose para levantar todo en local | 0 |
| [`docs/`](docs/) | Plan, decisiones y privacidad | — |

## Requisitos

| Herramienta | Para qué | Comprobar |
|---|---|---|
| Python 3.12 o superior | API y equipo local | `python --version` |
| [uv](https://docs.astral.sh/uv/) | Entornos y dependencias de Python | `uv --version` |
| Node 22 o superior y pnpm | Interfaz web | `node --version`, `pnpm --version` |
| Docker Desktop | PostgreSQL y servicios en contenedores | `docker compose version` |

## Estado

Fase 0 en curso. Ver el avance en la sección "Fases" del plan.
