# 0006. Convenciones de la base de datos y migraciones

- **Estado:** Aceptado
- **Fecha:** 2026-10-07

## Contexto

La API (fase 0, paso 4) empieza a crear tablas en PostgreSQL: topología del conjunto, residentes, vehículos y visitantes, y después la bitácora de accesos. Si cada tabla se diseña a su manera, los cambios de esquema se vuelven frágiles y las pruebas se contaminan entre sí. Hace falta decidir una vez cómo se nombran las cosas, cómo son las llaves y las fechas, cómo se versiona el esquema y cómo se prueba.

Restricciones:

- El esquema debe poder subir y bajar de versión sin intervención manual (`alembic downgrade`).
- Los ids deben poder generarse en el equipo local de la portería sin preguntarle a la base, como el `event_id` de `PlateRead` ([ADR 0004](0004-paquete-de-contratos-compartido.md)).
- Las pruebas usan el PostgreSQL real de compose ([ADR 0005](0005-infraestructura-local-docker-compose.md)), no una base en memoria.

## Opciones

1. **Nombres de restricciones**
   - Dejar que PostgreSQL los invente (*descartada*): cambian según el orden de creación y Alembic no puede borrarlos en un downgrade.
   - Convención en `MetaData` (*elegida*): `pk_<tabla>`, `fk_<tabla>_<columna>_<tabla_destino>`, `uq_<tabla>_<columnas>`, `ck_<tabla>_<nombre>`, `ix_<tabla>_<columna>`.
2. **Llave primaria**
   - Entero autoincremental (*descartada*): revela cuántos registros hay y obliga a ir a la base para tener el id.
   - UUIDv4 (*descartada*): aleatorio; los índices se fragmentan al insertar.
   - `uuidv7()` de PostgreSQL 18 (*descartada*): el id solo existe después del `INSERT`.
   - UUIDv7 generado en Python con `uuid-utils` (*elegida*): ordenado por tiempo, se conoce antes de guardar y coincide con `PlateRead`.
3. **Fechas**
   - `timestamp` sin zona (*descartada*): la hora queda ambigua.
   - `timestamptz` con `server_default=now()` (*elegida*): `created_at` y `updated_at` en todas las tablas; la base pone la hora, en UTC.
4. **Valores de un conjunto cerrado** (dirección del carril, estado del vehículo)
   - `ENUM` nativo de PostgreSQL (*descartada*): quitar un valor exige recrear el tipo.
   - Texto con `CHECK` (*elegida*): se guarda el valor (`'entry'`), no el nombre del miembro del enum de Python.
5. **Borrado**
   - Columna `deleted_at` genérica (*descartada*): cada consulta debe acordarse de filtrarla.
   - Estado de dominio (`active`, `inactive`) y llaves foráneas `ON DELETE RESTRICT` (*elegida*): no se borra nada que tenga historia.
6. **Versionado del esquema**
   - `Base.metadata.create_all()` (*descartada*): no altera tablas existentes ni deshace cambios.
   - Alembic con revisiones numeradas `0001`, `0002`... (*elegida*): cada cambio es un archivo revisable con `upgrade` y `downgrade`.
7. **Aislamiento de las pruebas**
   - SQLite en memoria (*descartada*): no tiene los `CHECK`, índices parciales ni tipos de PostgreSQL.
   - Borrar las tablas después de cada prueba (*descartada*): lento y frágil.
   - Transacción por prueba con rollback (*elegida*): `Session(join_transaction_mode="create_savepoint")`; un `commit()` del código bajo prueba solo libera un savepoint.

## Decisión

Se aplican las opciones elegidas. `porteria_api.models.base` define `Base` (con la convención), `UUIDPrimaryKeyMixin` y `TimestampMixin`. `migrations/env.py` toma la URL de `Settings` y compara contra `Base.metadata` con `compare_type`. La revisión `0001_baseline` está vacía: es el punto de partida.

Tres pruebas protegen las convenciones: el *stairway* sube, baja y vuelve a subir cada revisión; la de *drift* exige que los modelos y la base migrada coincidan (`compare_metadata == []`); y la CI corre `alembic upgrade head` y `alembic check` sobre la base `porteria`.

Los nombres de tablas y columnas van en inglés; la equivalencia con el español está en el glosario del [README de la API](../../services/api/README.md#glosario).

## Consecuencias

- Toda tabla nueva hereda los mixins y su migración se prueba sola en el *stairway*.
- La autogeneración de Alembic no detecta cambios en un `CHECK`: cada restricción necesita su propia prueba.
- Las pruebas de migraciones no usan `db_session`: el DDL esperaría a los bloqueos de la transacción abierta. Tampoco pueden correr en paralelo.
- `updated_at` usa `now()`, que es la hora de inicio de la transacción: dentro de una misma transacción no cambia.
