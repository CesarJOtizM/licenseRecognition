# Infra

Infraestructura local de la portería con Docker Compose. Por ahora levanta:

- **PostgreSQL 18** con dos bases: `porteria` (la de la aplicación) y `porteria_test` (para las pruebas automáticas de la API).
- **Adminer** (opcional): una página web para ver las tablas sin instalar nada.

La API, la web y el equipo local se agregarán aquí cuando existan. Las razones de cada decisión están en el [ADR 0005](../docs/decisiones/0005-infraestructura-local-docker-compose.md).

## Conceptos

- **Imagen:** la "plantilla" de un programa ya instalado y configurado, por ejemplo `postgres:18`. Se descarga una vez.
- **Contenedor:** una imagen en ejecución. Si lo borras, se pierde todo lo que no esté en un volumen.
- **Volumen:** una carpeta que Docker guarda aparte del contenedor. Aquí `postgres-data` guarda la base: sobrevive a `down`, pero no a `down -v`.
- **Healthcheck:** un comando que Docker repite para saber si el servicio ya está listo. Aquí es `pg_isready`; `up --wait` espera a que responda.
- **Perfil:** un grupo de servicios que solo arranca si lo pides. Adminer está en el perfil `tools`.
- **Locale:** las reglas para ordenar y comparar texto. Usamos el locale `builtin` `C.UTF-8`, que no cambia aunque se actualice la imagen.

## Archivos

| Archivo | Qué hace |
|---|---|
| `compose.yaml` | Define los servicios `postgres` y `adminer` |
| `.env.example` | Valores que puedes cambiar (copia a `infra/.env`; no es obligatorio) |
| `postgres/init/01-create-test-db.sql` | Crea `porteria_test` la primera vez |
| `scripts/smoke.sh` | Prueba de humo: comprueba que todo quedó bien |

## Uso

Requisito: Docker Desktop abierto (abajo debe decir "Engine running"). Todos los comandos se ejecutan desde la raíz del repositorio.

| Qué | Comando |
|---|---|
| Levantar y esperar a que esté listo | `docker compose -f infra/compose.yaml up -d --wait` |
| Ver el estado | `docker compose -f infra/compose.yaml ps` |
| Ver los logs | `docker compose -f infra/compose.yaml logs postgres` |
| Reiniciar | `docker compose -f infra/compose.yaml restart postgres` |
| Apagar (los datos se conservan) | `docker compose -f infra/compose.yaml down` |
| Apagar y **borrar los datos** | `docker compose -f infra/compose.yaml down -v` |

## Conectarse

Desde dentro del contenedor, sin instalar nada:

```powershell
docker compose -f infra/compose.yaml exec postgres psql -U porteria -d porteria
```

Desde tu máquina (por ejemplo con `psql` o DBeaver): host `localhost`, puerto `5432`, usuario `porteria`, contraseña `porteria`, base `porteria`. La API usará esta URL en el paso 4:

```text
DATABASE_URL=postgresql+psycopg://porteria:porteria@localhost:5432/porteria
```

## Adminer

```powershell
docker compose -f infra/compose.yaml --profile tools up -d --wait
```

Abre <http://127.0.0.1:8080>, elige "PostgreSQL" y usa servidor `postgres`, usuario `porteria`, contraseña `porteria`. Para apagarlo: `docker compose -f infra/compose.yaml --profile tools stop adminer`.

## Cómo probar

Desde Git Bash, en la raíz del repositorio:

```bash
bash infra/scripts/smoke.sh
```

El script valida `compose.yaml`, levanta PostgreSQL (máximo 90 s) y revisa en las dos bases que respondan, que usen `UTF8`, zona horaria `UTC` y locale `builtin`; que los datos estén en el volumen `porteria_postgres-data`, que el puerto solo escuche en `127.0.0.1` y que Adminer no arranque sin `--profile tools`. Si algo falla, termina con `FALLO: ...` y código de salida 1. No apaga nada al terminar. La CI corre el mismo script en el job `infra`.

## Problemas comunes en Windows

- **`Docker no responde`:** abre Docker Desktop y espera "Engine running".
- **Docker Desktop no arranca:** necesita WSL2. En PowerShell como administrador: `wsl --install` y reinicia.
- **`port is already allocated` o `bind: address already in use`:** ya hay algo en el puerto 5432 (por ejemplo, PostgreSQL instalado en Windows). Copia `infra/.env.example` a `infra/.env`, cambia `POSTGRES_PORT=5433` y vuelve a levantar. Lo mismo con `ADMINER_PORT`.
- **No existe `porteria_test` o cambiaste usuario/contraseña y no funciona:** los scripts de `postgres/init/` y las variables `POSTGRES_*` solo se aplican con el volumen vacío. Borra los datos con `down -v` y vuelve a levantar.
- **`bash: infra/scripts/smoke.sh: /usr/bin/env: bad interpreter` o `\r`:** el archivo quedó con finales de línea de Windows. `.gitattributes` lo evita; si pasa, ejecuta `git checkout -- infra/scripts/smoke.sh`.
