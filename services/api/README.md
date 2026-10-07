# API (backend central)

Backend en FastAPI. Guarda en PostgreSQL la bitácora, los residentes, los vehículos, los visitantes y las preautorizaciones. Recibe los eventos que sincroniza el equipo local de cada portería y alimenta la interfaz web por REST y WebSocket.

## Estado

Fase 0, paso 4: esqueleto ejecutable con `GET /health`. El esquema de la base (Alembic y tablas) llega en los siguientes PR del mismo paso.

## Estructura

```text
services/api/
├── pyproject.toml          # dependencias y configuración de pytest, coverage y mypy
├── uv.lock                 # versiones exactas (se sube a git)
├── src/porteria_api/
│   ├── config.py           # Settings: variables de entorno
│   ├── db.py               # motor de SQLAlchemy y sesión por petición
│   ├── app.py              # create_app(): fábrica de la app y su ciclo de vida
│   └── routes/health.py    # GET /health
└── tests/
```

- `create_app()` no se conecta a la base: el motor se crea al arrancar (lifespan) y se libera al apagar. Así importar el módulo o correr pruebas no necesita PostgreSQL.
- Cada petición recibe su propia sesión (`SessionDep`) y se cierra al terminar.
- `/health` hace `SELECT 1`: responde `200 {"status": "ok", "database": "ok"}` o, si la base no contesta, `503 {"status": "error", "database": "unavailable"}`. El detalle del error va al log, no al cliente.

## Configuración

| Variable | Por defecto | Para qué |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://porteria:porteria@127.0.0.1:5432/porteria` | base de la API (la de `infra/compose.yaml`) |
| `DB_CONNECT_TIMEOUT` | `3` | segundos máximos para abrir una conexión |

## Cómo se ejecuta

Desde la raíz del repositorio, con PostgreSQL levantado ([infra](../../infra/README.md)):

```powershell
docker compose -f infra/compose.yaml up -d --wait
uv run --directory services/api uvicorn porteria_api.app:create_app --factory --reload
curl http://127.0.0.1:8000/health      # documentación interactiva en /docs
```

`--factory` le dice a uvicorn que `create_app` es una función que devuelve la app, no la app misma.

## Cómo se prueba

```powershell
uv sync --directory services/api          # crea .venv e instala dependencias
uv run --directory services/api pytest    # pruebas con cobertura (mínimo 80 %)
uv run --directory services/api mypy      # chequeo de tipos estricto
```

## Glosario

El código usa nombres en inglés; esta es la equivalencia con el lenguaje del proyecto.

| Español | Inglés (código) |
|---|---|
| portería | gatehouse |
| carril | lane |
| puerta / talanquera | gate |
| torre | tower |
| unidad (apartamento o casa) | unit |
| chequeo de salud | health check |
| ciclo de vida de la app | lifespan |
| motor / sesión de base de datos | engine / session |
