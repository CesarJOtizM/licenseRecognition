# 0004. Paquete de contratos compartido (`packages/contracts`)

- **Estado:** Aceptado
- **Fecha:** 2026-10-04

## Contexto

El evento `PlateRead` (una lectura de placa) lo produce el equipo local de la portería y lo consume la API. Si cada servicio define su propia versión del evento, tarde o temprano dejan de coincidir: por ejemplo, el equipo local empieza a enviar `lane_id` y la API todavía espera `carril`.

Restricciones que ya existen:

- [ADR 0001](0001-monorepo.md): cada servicio se ejecuta solo desde su carpeta y no importa código de otro servicio por rutas relativas.
- [ADR 0002](0002-herramientas-uv-pnpm.md): cada proyecto de Python tiene su propio `pyproject.toml` y su propio `uv.lock`.
- [ADR 0003](0003-calidad-de-codigo.md): mypy estricto, pytest con cobertura mínima del 80 %, pre-commit y CI en cada proyecto.

## Opciones

Se evaluaron cuatro alternativas; solo la cuarta se adoptó.

1. **Copiar el modelo en cada servicio (descartada):** no hay dependencias nuevas, pero cada cambio se hace dos veces y nada avisa si las copias se separan. Es justo el problema que este ADR quiere evitar.
2. **Workspace de uv en la raíz, con un solo `uv.lock` para todo (descartada):** uv resuelve todos los proyectos juntos. Contradice el ADR 0002 y obliga a que la API y el equipo local usen exactamente las mismas versiones de todo, aunque se desplieguen por separado.
3. **Publicar el paquete en un índice (PyPI privado) o instalarlo desde una URL de git (descartada):** es como se haría entre varios repositorios, pero exige publicar una versión por cada cambio. Para una persona en un monorepo es trabajo sin beneficio.
4. **Paquete propio en `packages/contracts`, instalado como dependencia de ruta editable (elegida):** un proyecto de Python independiente (con su `pyproject.toml`, su `uv.lock`, sus pruebas y su mypy) que cada servicio declara como dependencia.

## Decisión

Opción 4. El paquete se distribuye como `lr-contracts` y se importa como `lr_contracts`. Usa el layout `src/` e incluye `py.typed` para que mypy use sus tipos. Sus únicas dependencias de ejecución son `pydantic` y `uuid-utils`.

Cada servicio que lo usa lo declara así en su `pyproject.toml`:

```toml
[project]
dependencies = ["lr-contracts"]

[tool.uv.sources]
lr-contracts = { path = "../../packages/contracts", editable = true }
```

Una **dependencia de ruta** le dice a uv que el paquete no se descarga de internet, sino que está en una carpeta del disco. **Editable** significa que se instala apuntando a esa carpeta en vez de copiar los archivos: si cambias `packages/contracts/src/lr_contracts/__init__.py`, edge-agent ve el cambio sin reinstalar nada.

## Consecuencias

- **Aclaración del ADR 0001.** Una dependencia declarada en `pyproject.toml` y fijada en `uv.lock` no es un import por ruta relativa. edge-agent escribe `import lr_contracts`, igual que con cualquier paquete instalado; nunca `sys.path.append("../../packages")` ni imports de archivos de otra carpeta. La regla del ADR 0001 sigue vigente para el código de los servicios.
- Un cambio en el contrato toca productor y consumidor en el mismo commit, y las pruebas de los dos lo detectan.
- Hay dos `uv.lock` que pueden fijar versiones distintas de `pydantic`. En la portería manda el lock de edge-agent; la CI prueba el paquete de contratos con su propio lock.
- Si cambian las dependencias o la versión de `packages/contracts/pyproject.toml`, el lock de edge-agent queda desactualizado y `uv sync --locked` falla hasta correr `uv lock --directory services/edge-agent`. Es intencional: la CI usa `--locked` y no deja pasar un lock viejo.
- Los hooks de mypy y pytest de edge-agent también corren cuando cambia `packages/contracts/`, y el paquete tiene sus propios hooks y su paso en la CI.
- **Pendiente:** cuando se escriba el Dockerfile de edge-agent, el contexto de construcción (build context) tendrá que ser la raíz del repositorio, porque la dependencia apunta fuera de `services/edge-agent/`. Se decide en ese momento.
- La API usará el mismo mecanismo cuando tenga su `pyproject.toml`.
