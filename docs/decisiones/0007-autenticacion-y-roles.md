# 0007. Autenticación, roles y bitácora de auditoría

- **Estado:** Aceptado
- **Fecha:** 2026-10-08

## Contexto

Hoy cualquiera puede llamar a la API y las acciones manuales no dejan rastro. La consola del guarda y el panel de administración (fase 3) y el portal de residentes (fase 4) necesitan saber quién hace cada petición y qué puede hacer. Restricciones:

- Tres roles fijos: administrador, guarda y residente; un usuario tiene un solo rol.
- Desactivar a un usuario o a su residente debe cortarle el acceso de inmediato, no cuando venza su token.
- Los cambios hechos por un administrador deben quedar registrados y no poder editarse después.
- `alembic upgrade` y `alembic check` deben seguir funcionando en la CI sin configurar secretos.

## Opciones

1. **Formato de la sesión**
   - Sesión guardada en la base con cookie (*descartada*): exige tabla de sesiones y protección CSRF para una API que también usarán clientes no web.
   - JWT firmado sin consultar la base (*descartada*): un usuario desactivado seguiría entrando hasta que venza el token.
   - JWT HS256 de 30 minutos con PyJWT y recarga del usuario en cada petición (*elegida*): el token dice quién es (`sub`) y su versión (`ver`); el rol y el estado se leen de la base, así que mandan los datos actuales. Cambiar la contraseña sube `token_version` e invalida los tokens viejos.
2. **Hash de contraseñas**
   - bcrypt (*descartada*): corta las contraseñas a 72 bytes.
   - Argon2id con pwdlib (*elegida*): el algoritmo recomendado por OWASP. Las pruebas usan parámetros baratos inyectados para no volver lenta la suite.
3. **Secreto `JWT_SECRET`**
   - Valor por defecto para desarrollo (*descartada*): es fácil terminar en producción con él.
   - Obligatorio en toda la configuración (*descartada*): Alembic y el CLI fallarían sin una variable que no usan.
   - `DatabaseSettings` (base de datos) y `Settings` (API, añade el secreto) (*elegida*): Alembic usa la primera; la API exige un secreto de al menos 32 caracteres al arrancar y nunca lo muestra en `repr`.
4. **Bitácora de auditoría**
   - Triggers que copian cada cambio de la base (*descartada*): no saben qué usuario de la API actuó.
   - Tabla `audit_logs` escrita por la API en la misma transacción, con un trigger que rechaza `UPDATE`, `DELETE` y `TRUNCATE` (*elegida*): si el cambio se deshace, su registro también; y nadie puede reescribir la historia. Solo se guardan campos de una lista permitida, nunca el hash de la contraseña.

## Decisión

Se aplican las opciones elegidas. `porteria_api.security` agrupa el hash (`Passwords`) y los tokens (`encode_access_token`, `decode_access_token`); no depende de FastAPI. Un login fallido responde siempre el mismo 401, exista o no el usuario, y verifica un hash de relleno para que el tiempo de respuesta no lo delate. Sin token válido la respuesta es 401; con token pero sin el rol necesario, 403.

`audit_logs` se aparta del [ADR 0006](0006-convenciones-base-de-datos.md): no tiene `created_at` ni `updated_at`, sino `occurred_at`, porque una fila que nunca se modifica no necesita fecha de actualización.

No hay regla de "último administrador activo". Solo un administrador puede modificar usuarios y no puede desactivarse ni quitarse el rol a sí mismo (responde 409). Quien hace el cambio siempre sigue siendo un administrador activo, así que siempre queda al menos uno.

## Consecuencias

- Cada petición protegida hace una consulta más (cargar el usuario); a cambio, desactivar a alguien tiene efecto inmediato.
- Antes de arrancar la API hay que definir `JWT_SECRET`; las pruebas y la CI de migraciones no lo necesitan.
- Quedan pendientes:
  - Autenticación de los equipos de portería (`edge-agent`): fase 2.
  - Tokens de refresco y cierre de sesión: fase 3.
  - Límite de intentos y bloqueo por fuerza bruta: fase 5. Mientras tanto, la API no se expone fuera de la red local y los intentos quedan en el log.
