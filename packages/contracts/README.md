# Contratos compartidos (`lr-contracts`)

Paquete de Python con los contratos de los eventos que se intercambian los servicios. Por ejemplo, el evento `PlateRead` (una lectura de placa) lo produce el equipo local de la portería y lo consume la API; si los dos usan la misma clase, no pueden quedar desalineados.

Ver la decisión en el [ADR 0004](../../docs/decisiones/0004-paquete-de-contratos-compartido.md).

## Estado

Solo el esqueleto del paquete, su configuración de calidad y la conexión con edge-agent. El modelo `PlateRead` llega en el siguiente paso.

## Estructura

```text
packages/contracts/
├── pyproject.toml        # dependencias (pydantic, uuid-utils) y configuración de pytest, coverage y mypy
├── uv.lock               # versiones exactas (se sube a git)
├── src/lr_contracts/     # código del paquete; py.typed indica a mypy que el paquete trae tipos
└── tests/                # pruebas con pytest
```

El nombre de distribución es `lr-contracts` (el que aparece en `pyproject.toml` y en `uv.lock`) y el de importación es `lr_contracts` (el que se escribe en `import`).

## Cómo se usa desde un servicio

El servicio lo declara como dependencia de ruta editable en su `pyproject.toml`, como ya hace edge-agent:

```toml
[project]
dependencies = ["lr-contracts"]

[tool.uv.sources]
lr-contracts = { path = "../../packages/contracts", editable = true }
```

Después: `uv lock --directory services/<servicio>` y, en el código, `import lr_contracts`.

## Cómo se ejecuta

Es una biblioteca: no tiene nada que ejecutar por sí sola.

## Cómo se prueba

Desde la raíz del repositorio:

```powershell
uv sync --directory packages/contracts          # crea .venv e instala dependencias
uv run --directory packages/contracts pytest    # pruebas con cobertura (mínimo 80 %)
uv run --directory packages/contracts mypy      # chequeo de tipos estricto
```

Si cambias `dependencies` o `version` en `pyproject.toml`, vuelve a generar los locks de este paquete y de los servicios que lo usan:

```powershell
uv lock --directory packages/contracts
uv lock --directory services/edge-agent
```

Si no lo haces, `uv sync --locked` falla en la CI.
