# API (backend central)

Backend en FastAPI. Guarda en PostgreSQL la bitácora, los residentes, los vehículos, los visitantes y las preautorizaciones. Recibe los eventos que sincroniza el equipo local de cada portería y alimenta la interfaz web por REST y WebSocket.

## Estado

Fase 0, paso 4 (completo): esqueleto ejecutable con `GET /health`, migraciones con Alembic, la topología del conjunto (revisión `0002`: torres, unidades, porterías, carriles, cámaras y talanqueras) y las personas (revisión `0003`: residentes, vehículos y visitantes; `0004`: el tipo de placa no contradice la placa). Paso 5 (completo): tabla de usuarios (revisión `0005`), bitácora de auditoría (revisión `0006`), inicio de sesión (`/auth/login`, `/auth/me`), gestión de usuarios (`POST/GET /users`, `PATCH /users/{id}`, `POST /users/{id}/password`) y el comando `create-admin` para el primer administrador.

## Estructura

```text
services/api/
├── pyproject.toml          # dependencias y configuración de pytest, coverage y mypy
├── uv.lock                 # versiones exactas (se sube a git)
├── alembic.ini             # configuración de Alembic (la URL sale de Settings)
├── migrations/             # env.py, plantilla y versions/ (una revisión por cambio de esquema)
├── src/porteria_api/
│   ├── config.py           # DatabaseSettings y Settings: variables de entorno
│   ├── security.py         # hash de contraseñas (Argon2id) y tokens de acceso (JWT)
│   ├── audit.py            # record_audit() y snapshot(): escribir en la bitácora de auditoría
│   ├── auth.py             # CurrentUser y require_roles(): quién pide y si su rol puede pasar
│   ├── schemas.py          # cuerpos de petición y respuesta (Pydantic)
│   ├── db.py               # motor de SQLAlchemy y sesión por petición
│   ├── app.py              # create_app(): fábrica de la app y su ciclo de vida
│   ├── cli.py              # python -m porteria_api.cli create-admin: el primer administrador
│   ├── models/base.py      # Base, convención de nombres y mixins de id y fechas
│   ├── models/enums.py     # valores fijos (sentido del carril, estados, tipo de documento...)
│   ├── models/site.py      # torres, unidades, porterías, carriles, cámaras, talanqueras
│   ├── models/people.py    # residentes, vehículos y visitantes
│   ├── models/users.py     # usuarios de la API con su rol
│   ├── models/audit.py     # bitácora de auditoría (solo se agregan filas)
│   ├── routes/health.py    # GET /health
│   ├── routes/auth.py      # POST /auth/login y GET /auth/me
│   └── routes/users.py     # alta, listado, edición y contraseña de usuarios (solo administradores)
└── tests/
```

Topología: una torre tiene unidades (el número no se repite dentro de la torre); una portería tiene carriles, y cada carril tiene cámaras y una sola talanquera. Las porterías no dependen de una torre. El `code` del carril (por ejemplo `entrada-1`) es el `lane_id` que llega en cada lectura de placa. Las FK son `RESTRICT`: no se puede borrar un carril que todavía tiene cámaras. Los valores fijos (`entry`/`exit`, `ip`/`lpr`) se guardan como texto con un `CHECK`, no como tipo `ENUM` de PostgreSQL, para poder cambiarlos con una migración sencilla.

Personas: residentes y vehículos pertenecen a una unidad; los visitantes no (llegan a una unidad en cada visita). La placa se guarda normalizada con `normalize_plate` de [`lr-contracts`](../../packages/contracts/README.md) (`abc 123` queda `ABC123`), igual que en cada `PlateRead`, y un `CHECK` rechaza lo que no sea `^[A-Z0-9]{3,10}$`. `plate_kind` no se escribe a mano: sale de `classify_plate` al asignar la placa, y el `CHECK` `ck_vehicles_plate_kind_matches_plate` rechaza un tipo que contradiga la placa (por ejemplo `ABC123` como `motorcycle`), aunque llegue por SQL directo. Un índice único parcial (`WHERE status <> 'inactive'`) impide que dos vehículos vigentes (`active` o `blocked`) tengan la misma placa, pero deja guardar como historia los vehículos dados de baja (`inactive`). El documento del visitante es único por tipo: `cc 123` y `ce 123` son personas distintas.

Usuarios: cada uno tiene un solo rol (`admin`, `guard` o `resident`). El nombre de usuario se guarda en minúsculas (`Ana` queda `ana`) y es único; un `CHECK` rechaza mayúsculas aunque lleguen por SQL directo. Solo el rol `resident` apunta a un residente, y cada residente tiene a lo sumo un usuario (`ck_users_resident_link`, `uq_users_resident_id`). `token_version` va dentro de cada token: subirlo deja sin validez los tokens ya emitidos.

Auditoría: cada fila de `audit_logs` dice quién (`actor_user_id`, `NULL` si no fue un usuario), qué acción (`user.created`; el `CHECK` exige el formato `entidad.verbo`), sobre qué entidad y la foto de antes y de después en JSON. Solo se agregan filas: un trigger de PostgreSQL rechaza `UPDATE`, `DELETE` y `TRUNCATE` aunque lleguen por SQL directo, y por eso la tabla no tiene `updated_at`. `record_audit()` agrega la fila en la misma transacción del cambio: si el cambio se deshace, la fila también. Las fotos salen de `snapshot()` con una lista de campos permitidos (`USER_AUDIT_FIELDS`); `password_hash` nunca entra.

- `create_app()` no se conecta a la base: el motor se crea al arrancar (lifespan) y se libera al apagar. Así importar el módulo o correr pruebas no necesita PostgreSQL.
- Cada petición recibe su propia sesión (`SessionDep`) y se cierra al terminar.
- Una ruta protegida pide `CurrentUser` (cualquier rol) o `AdminUser` (`require_roles(UserRole.ADMIN)`). El usuario se recarga de la base en cada petición: sin token, con token vencido o inválido, con `token_version` vieja, deshabilitado o con su residente inactivo responde `401` con `WWW-Authenticate: Bearer`; con un rol no permitido, `403`.
- `/health` hace `SELECT 1`: responde `200 {"status": "ok", "database": "ok"}` o, si la base no contesta, `503 {"status": "error", "database": "unavailable"}`. El detalle del error va al log, no al cliente.

## Configuración

| Variable | Por defecto | Para qué |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://porteria:porteria@127.0.0.1:5432/porteria` | base de la API (la de `infra/compose.yaml`) |
| `DB_CONNECT_TIMEOUT` | `3` | segundos máximos para abrir una conexión |
| `JWT_SECRET` | ninguno (obligatorio para la API) | firma los tokens de acceso; mínimo 32 caracteres. Alembic y `create-admin` no lo necesitan |
| `JWT_ALGORITHM` | `HS256` | Solo `HS256` |
| `ACCESS_TOKEN_MINUTES` | `30` | minutos que dura un token de acceso (1 a 1440) |

## Cómo se ejecuta

Primer arranque, desde la raíz del repositorio ([infra](../../infra/README.md) explica PostgreSQL):

```powershell
docker compose -f infra/compose.yaml up -d --wait              # 1. PostgreSQL
uv run --directory services/api alembic upgrade head           # 2. crea las tablas
uv run --directory services/api python -m porteria_api.cli create-admin --username ana --full-name "Ana Pérez"   # 3. primer admin
$env:JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
uv run --directory services/api uvicorn porteria_api.app:create_app --factory --reload   # 4. la API
curl http://127.0.0.1:8000/health      # documentación interactiva en /docs
```

Después entra con `ana` (ver [Iniciar sesión](#iniciar-sesión)). En los arranques siguientes bastan el paso 1, el 2 si hay migraciones nuevas, y el 4. `--factory` le dice a uvicorn que `create_app` es una función que devuelve la app, no la app misma. Guarda el `JWT_SECRET`: si cambia, los tokens emitidos dejan de servir.

### Primer administrador

`/users` solo lo usa un admin, así que el primero se crea por consola. `create-admin` pide la contraseña dos veces sin mostrarla (de 12 a 128 caracteres, las mismas reglas de `POST /users`), crea un `admin` activo y escribe `user.created` en la auditoría con actor `NULL` (no lo hizo ningún usuario). Usa `DATABASE_URL`, no `JWT_SECRET`. En un script, `--password-stdin` lee la contraseña de la primera línea de la entrada estándar, sin confirmación:

```powershell
"una-contrasena-larga" | uv run --directory services/api python -m porteria_api.cli create-admin --username ana --password-stdin
```

Sale con `0` si lo creó, `1` si la entrada no es válida, las contraseñas no coinciden o el usuario ya existe (no cambia nada), `2` si faltan argumentos y `3` si no se pudo conectar a la base. La contraseña nunca aparece en la salida.

### Iniciar sesión

`POST /auth/login` recibe un formulario (`username`, `password`) y devuelve `{"access_token": "...", "token_type": "bearer", "expires_in": 1800}`. El usuario no distingue mayúsculas (`ANA` entra como `ana`). Contraseña incorrecta, usuario inexistente, deshabilitado o residente inactivo responden el mismo `401 {"detail": "Incorrect username or password"}`; el motivo solo queda en el log, sin la contraseña. El login no escribe en la bitácora de auditoría.

```powershell
$login = Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/login -Body @{ username = "ana"; password = "una-contrasena-larga" }
Invoke-RestMethod http://127.0.0.1:8000/auth/me -Headers @{ Authorization = "Bearer $($login.access_token)" }
# con curl: curl -d "username=ana&password=una-contrasena-larga" http://127.0.0.1:8000/auth/login
```

`GET /auth/me` devuelve `id`, `username`, `role`, `resident_id` y `unit_id` (los dos últimos `null` si no es residente). En `/docs`, el botón **Authorize** pide usuario y contraseña, llama a `/auth/login` y envía el token en las demás peticiones.

### Usuarios

Solo un `admin` usa `/users` (sin token: `401`; guarda o residente: `403`). `POST /users` recibe JSON `{"username", "password", "full_name", "role", "resident_id"}` y responde `201` con el usuario, sin `password_hash` ni `token_version`. La contraseña tiene de 12 a 128 caracteres; `resident_id` es obligatorio para `resident` y prohibido para los demás. Usuario repetido (sin distinguir mayúsculas) o residente que ya tiene usuario: `409`; residente inexistente: `422`. Cada alta escribe una fila `user.created` en la auditoría con el administrador como actor; si falla, no queda ninguna. `GET /users` lista todos ordenados por `username`. No se borran usuarios (`DELETE` responde `405`).

`PATCH /users/{id}` cambia solo lo que se envía de `full_name`, `role`, `status` (`active`/`disabled`) y `resident_id` (`null` explícito lo quita); usuario inexistente: `404`; mismas reglas `409`/`422` que el alta. Un admin no puede deshabilitarse ni quitarse el rol (`409`), pero sí cambiar su nombre. Deshabilitar corta el acceso al instante y sube `token_version`, así que al reactivar los tokens viejos siguen sin servir. Cada cambio real escribe `user.updated` con `before`/`after`; un `PATCH` sin cambios no audita. `POST /users/{id}/password` con `{"new_password"}` responde `204`, sube `token_version` (los tokens del usuario dejan de servir) y audita `user.password_reset` sin datos de la contraseña.

```powershell
$admin = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Method Post http://127.0.0.1:8000/users -Headers $admin -ContentType application/json -Body '{"username": "bob", "password": "una-contrasena-larga", "full_name": "Bob", "role": "guard"}'
Invoke-RestMethod http://127.0.0.1:8000/users -Headers $admin
$bob = (Invoke-RestMethod http://127.0.0.1:8000/users -Headers $admin | Where-Object username -eq bob).id
Invoke-RestMethod -Method Patch http://127.0.0.1:8000/users/$bob -Headers $admin -ContentType application/json -Body '{"status": "disabled"}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/users/$bob/password -Headers $admin -ContentType application/json -Body '{"new_password": "otra-contrasena-larga"}'
```

## Migraciones

Una migración es un archivo de Python que cambia el esquema (crea una tabla, agrega una columna) y sabe deshacerse. Alembic anota en la tabla `alembic_version` cuál es la última aplicada. Los comandos usan `DATABASE_URL`:

```powershell
uv run --directory services/api alembic upgrade head        # aplica todas las pendientes
uv run --directory services/api alembic downgrade -1        # deshace la última
uv run --directory services/api alembic current             # muestra en qué revisión está la base
uv run --directory services/api alembic revision --autogenerate -m "crea torres" --rev-id 0002
uv run --directory services/api alembic check               # falla si los modelos tienen cambios sin migración
```

`--autogenerate` compara los modelos con la base y escribe un borrador: hay que revisarlo, porque no detecta todo (por ejemplo, cambios en un `CHECK`). Las revisiones se numeran a mano (`0002`, `0003`...) para que se lean en orden. Una revisión que ya está en `main` no se edita: una base que ya la aplicó no la vuelve a correr, así que el cambio va en una revisión nueva.

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
| residente (vigente o retirado) | resident (status `active` / `inactive`) |
| vehículo (vigente, bloqueado o dado de baja) | vehicle (status `active` / `blocked` / `inactive`) |
| tipo de placa (carro, moto, desconocido) | plate_kind (`car` / `motorcycle` / `unknown`) |
| visitante | visitor |
| tipo de documento (cédula, cédula de extranjería, pasaporte, otro) | document_type (`cc` / `ce` / `passport` / `other`) |
| usuario (activo o deshabilitado) | user (status `active` / `disabled`) |
| rol (administrador, guarda, residente) | role (`admin` / `guard` / `resident`) |
| versión del token (sube para invalidar tokens emitidos) | token_version |
| bitácora de auditoría (solo agregar) | audit log (append-only) |
| acción auditada (`entidad.verbo`) | audit action (`user.created`) |
| foto de antes / de después | before / after snapshot |
| disparador (trigger) | trigger |
| índice único parcial | partial unique index |
| chequeo de salud | health check |
| ciclo de vida de la app | lifespan |
| motor / sesión de base de datos | engine / session |
| migración / revisión | migration / revision |
| desfase entre modelos y base | drift |
