# API (backend central)

Backend en FastAPI. Guarda en PostgreSQL la bitácora, los residentes, los vehículos, los visitantes y las preautorizaciones. Recibe los eventos que sincroniza el equipo local de cada portería y alimenta la interfaz web por REST y WebSocket.

## Estado

Fase 0, paso 4: esqueleto ejecutable con `GET /health`, migraciones con Alembic y la topología del conjunto (revisión `0002`: torres, unidades, porterías, carriles, cámaras y talanqueras). Residentes, vehículos y visitantes llegan en el siguiente PR del mismo paso.

## Estructura

```text
services/api/
├── pyproject.toml          # dependencias y configuración de pytest, coverage y mypy
├── uv.lock                 # versiones exactas (se sube a git)
├── alembic.ini             # configuración de Alembic (la URL sale de Settings)
├── migrations/             # env.py, plantilla y versions/ (una revisión por cambio de esquema)
├── src/porteria_api/
│   ├── config.py           # Settings: variables de entorno
│   ├── db.py               # motor de SQLAlchemy y sesión por petición
│   ├── app.py              # create_app(): fábrica de la app y su ciclo de vida
│   ├── models/base.py      # Base, convención de nombres y mixins de id y fechas
│   ├── models/enums.py     # valores fijos (sentido del carril, tipo de cámara)
│   ├── models/site.py      # torres, unidades, porterías, carriles, cámaras, talanqueras
│   └── routes/health.py    # GET /health
└── tests/
```

Topología: una torre tiene unidades (el número no se repite dentro de la torre); una portería tiene carriles, y cada carril tiene cámaras y una sola talanquera. Las porterías no dependen de una torre. El `code` del carril (por ejemplo `entrada-1`) es el `lane_id` que llega en cada lectura de placa. Las FK son `RESTRICT`: no se puede borrar un carril que todavía tiene cámaras. Los valores fijos (`entry`/`exit`, `ip`/`lpr`) se guardan como texto con un `CHECK`, no como tipo `ENUM` de PostgreSQL, para poder cambiarlos con una migración sencilla.

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

## Migraciones

Una migración es un archivo de Python que cambia el esquema (crea una tabla, agrega una columna) y sabe deshacerse. Alembic anota en la tabla `alembic_version` cuál es la última aplicada. Los comandos usan `DATABASE_URL`:

```powershell
uv run --directory services/api alembic upgrade head        # aplica todas las pendientes
uv run --directory services/api alembic downgrade -1        # deshace la última
uv run --directory services/api alembic current             # muestra en qué revisión está la base
uv run --directory services/api alembic revision --autogenerate -m "crea torres" --rev-id 0002
uv run --directory services/api alembic check               # falla si los modelos tienen cambios sin migración
```

`--autogenerate` compara los modelos con la base y escribe un borrador: hay que revisarlo, porque no detecta todo (por ejemplo, cambios en un `CHECK`). Las revisiones se numeran a mano (`0002`, `0003`...) para que se lean en orden.

## Cómo se prueba

```powershell
uv sync --directory services/api          # crea .venv e instala dependencias
uv run --directory services/api pytest    # pruebas con cobertura (mínimo 80 %)
uv run --directory services/api mypy      # chequeo de tipos estricto
```

Las pruebas marcadas `db` usan la base `porteria_test` de compose (`TEST_DATABASE_URL` la cambia). Si PostgreSQL no está levantado, se saltan con el motivo; con `API_TEST_REQUIRE_DB=1` (como en la CI) fallan.

```powershell
uv run --directory services/api pytest -m "not db" --no-cov   # lo que corre el pre-push, sin Docker
$env:API_TEST_REQUIRE_DB = "1"; uv run --directory services/api pytest   # todas, como la CI
```

Las pruebas que escriben en la base usan el fixture `db_session` (o `client`, que hace que la API use esa misma sesión): todo corre en una transacción que se deshace al terminar, así que una prueba no ve los datos de otra. Las convenciones están en el [ADR 0006](../../docs/decisiones/0006-convenciones-base-de-datos.md).

`tests/db/test_migrations.py` sube y baja cada revisión (prueba "stairway") y compara los modelos con la base migrada; siempre deja la base de pruebas en `head`.

Si la base `porteria_test` no existe (volumen creado antes del paso 3): `docker compose -f infra/compose.yaml down -v`.

## Glosario

El código usa nombres en inglés; esta es la equivalencia con el lenguaje del proyecto.

| Español | Inglés (código) |
|---|---|
| portería | gatehouse |
| carril (de entrada o de salida) | lane (direction `entry` / `exit`) |
| cámara (IP o lectora de placas) | camera (kind `ip` / `lpr`) |
| puerta / talanquera | gate |
| torre | tower |
| unidad (apartamento o casa) | unit |
| chequeo de salud | health check |
| ciclo de vida de la app | lifespan |
| motor / sesión de base de datos | engine / session |
| migración / revisión | migration / revision |
| desfase entre modelos y base | drift |
