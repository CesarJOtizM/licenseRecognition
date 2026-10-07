# 0005. Infraestructura local con Docker Compose

- **Estado:** Aceptado
- **Fecha:** 2026-10-05

## Contexto

La API (fase 0, paso 4) necesita PostgreSQL. Si cada persona lo instala a mano en Windows, cada máquina termina con otra versión, otra codificación y otra zona horaria, y los errores no se pueden reproducir. La CI también necesita la misma base para comprobar que la configuración funciona.

Restricciones:

- Se desarrolla en Windows; Docker Desktop corre sobre WSL2.
- La base no debe quedar expuesta a la red local: son credenciales de desarrollo.
- Lo que se configure hoy debe servirle a la API sin cambios: una base `porteria` para la aplicación y otra `porteria_test` para sus pruebas.

## Opciones

1. **PostgreSQL instalado en Windows:** sin Docker, pero no es reproducible y la CI (Linux) tendría otra configuración.
2. **Compose solo con PostgreSQL:** mínimo, pero para mirar las tablas hay que usar `psql`.
3. **Compose con PostgreSQL y Adminer opcional (elegida):** Adminer es una página web para explorar la base; queda detrás de un perfil y no arranca si no se pide.
4. **Compose con todo (API, web, edge y MinIO):** todavía no existen esos servicios, así que serían contenedores vacíos.

## Decisión

Opción 3, en `infra/compose.yaml` con el nombre de proyecto `porteria`:

- **Imagen `postgres:18`.** PostgreSQL 18 guarda los datos en `/var/lib/postgresql/18/docker`, así que el volumen con nombre `postgres-data` se monta en la carpeta padre `/var/lib/postgresql`. Montarlo en `/var/lib/postgresql/data` (la ruta de versiones anteriores) dejaría los datos fuera del volumen.
- **Locale `builtin` con `C.UTF-8`** (`--locale-provider=builtin`, disponible desde PostgreSQL 17). La propuesta solo pedía `UTF8`; se cambió porque el orden del texto con el locale de glibc puede cambiar al actualizar la imagen y dañar índices sin avisar. Con `builtin` el orden es por código de carácter y no depende de glibc. Las placas son ASCII; si más adelante se necesita orden "a la española" (nombres de residentes), se usa una collation ICU por columna.
- **`TZ=UTC` sin `PGTZ`.** `initdb` lee `TZ` y deja `timezone = 'UTC'` como valor por defecto del servidor. `PGTZ` solo afecta a clientes dentro del contenedor y escondería un error en la prueba de humo, que usa `psql` dentro del contenedor.
- **Puertos solo en `127.0.0.1`** y todas las variables con valor por defecto: funciona sin `infra/.env`.
- **Healthcheck por TCP** (`pg_isready -h 127.0.0.1`): por socket responde antes de que terminen los scripts de inicio.
- **Adminer `adminer:6`** en el perfil `tools`.
- **Prueba de humo `infra/scripts/smoke.sh`**, única fuente de verificación, ejecutada por el job `infra` de la CI.

Quedan fuera:

- **MinIO:** el proyecto fue archivado. El almacenamiento compatible con S3 se elige cuando exista `CloudImageStore`.
- **Dockerfiles** de la API, edge y web: se escriben cuando exista cada servicio (ver la nota del contexto de construcción en el [ADR 0004](0004-paquete-de-contratos-compartido.md)).
- **Hooks de pre-commit que necesiten Docker:** no todos los commits deberían exigir Docker Desktop abierto.

## Consecuencias

- Un comando levanta la misma base en cualquier máquina y en la CI.
- Los scripts de `infra/postgres/init/` solo corren con el volumen vacío. Si se agrega uno nuevo, hay que borrar los datos con `down -v`.
- La etiqueta `postgres:18` es flotante (recibe versiones menores). Se acepta; se fija una versión exacta si alguna actualización rompe algo.
- En local se necesita Docker Desktop; sin él, la verificación real solo ocurre en la CI.
- Se agregan los hooks de shebang y `shellcheck` para revisar los scripts de shell.
