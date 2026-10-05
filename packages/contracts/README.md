# Contratos compartidos (`lr-contracts`)

Paquete de Python con los contratos de los eventos que se intercambian los servicios. Por ejemplo, el evento `PlateRead` (una lectura de placa) lo produce el equipo local de la portería y lo consume la API; si los dos usan la misma clase, no pueden quedar desalineados.

Ver la decisión en el [ADR 0004](../../docs/decisiones/0004-paquete-de-contratos-compartido.md).

## Estado

Contiene la versión 1 del contrato `PlateRead` y su JSON Schema publicado.

## Estructura

```text
packages/contracts/
├── pyproject.toml        # dependencias (pydantic, uuid-utils) y configuración de pytest, coverage y mypy
├── uv.lock               # versiones exactas (se sube a git)
├── schemas/              # JSON Schema generado del contrato (se sube a git)
├── src/lr_contracts/
│   ├── plates.py         # normalize_plate, classify_plate y PlateKind
│   ├── plate_read.py     # modelo PlateRead, Source y new_event_id
│   ├── schema.py         # genera el JSON Schema
│   └── py.typed          # indica a mypy que el paquete trae tipos
└── tests/                # pruebas con pytest
```

## Contrato `PlateRead` (versión 1)

Un `PlateRead` es una lectura de placa: "en el carril `entrada-1`, a tal hora, se leyó `ABC123` con 93 % de confianza". Lo produce el pipeline de reconocimiento (o una cámara LPR que ya trae su propio reconocimiento) y lo consumen el motor de decisión, la bitácora y la API.

Es un modelo de Pydantic v2: al crearlo, Pydantic valida y convierte cada campo; si algo no cumple las reglas, lanza `ValidationError` y no se crea el objeto.

```python
from lr_contracts import PlateRead

read = PlateRead.model_validate(
    {
        "plate": "abc-123",
        "raw_text": "ABC-123",
        "confidence": 0.93,
        "captured_at": "2026-10-04T08:00:00-05:00",
        "lane_id": "entrada-1",
        "source": "pipeline",
    }
)
read.plate  # "ABC123"
read.plate_kind  # PlateKind.CAR
read.captured_at  # 2026-10-04 13:00:00+00:00 (mismo instante, en UTC)
read.model_dump_json()  # JSON listo para enviar o guardar
```

### Campos

| Campo | Tipo en JSON | Obligatorio al crear | Reglas |
|---|---|---|---|
| `schema_version` | entero | No (vale `1`) | Solo se acepta el entero `1`; `true` y `1.0` se rechazan. |
| `event_id` | texto (UUID) | No (se genera) | Debe ser un UUID versión 7. |
| `plate` | texto | Sí | Se guarda en mayúsculas y sin espacios ni guiones. Vacía tras normalizar se rechaza. |
| `raw_text` | texto | Sí | Texto tal como lo entregó el OCR o la cámara, sin cambios. Vacío o solo espacios se rechaza. |
| `plate_kind` | `car`, `motorcycle` o `unknown` | No (se calcula) | Se deriva siempre de `plate`. Si se envía y no coincide, se rechaza. |
| `confidence` | número | Sí | Entre 0 y 1, ambos incluidos. Se aceptan `0` y `1` enteros; se rechazan `NaN`, `true`/`false` y números en texto como `"0.5"`. |
| `captured_at` | texto (fecha ISO 8601) | Sí | Debe traer zona horaria; se guarda convertido a UTC. Se rechazan marcas de tiempo Unix como `1700000000`, también si llegan como texto. |
| `lane_id` | texto | Sí | Vacío o solo espacios se rechaza. |
| `source` | `pipeline` o `lpr_camera` | Sí | Quién produjo la lectura. |
| `photo` | texto o `null` | No (vale `null`) | Clave de la foto en el almacenamiento (por ejemplo `2026/10/04/x.jpg`), no la imagen. Vacío o solo espacios se rechaza. |

### Reglas generales

- **Inmutable:** una lectura no se puede modificar después de creada (`read.plate = "X"` lanza `ValidationError`). Si hace falta otra, se crea otra con `PlateRead.model_validate({**read.model_dump(exclude={"plate_kind"}), "plate": "ABC12D"})`; se excluye `plate_kind` para que se vuelva a calcular, porque el anterior contradiría la placa nueva. No uses `read.model_copy(update=...)`: Pydantic no valida los campos que cambia, así que podría quedar, por ejemplo, una placa de moto con `plate_kind` de carro.
- **Tipos estrictos:** los campos de texto (`plate`, `raw_text`, `lane_id`, `photo`) no aceptan bytes, y los números no se aceptan como texto ni como booleanos. Pydantic, por defecto, convierte esos valores en silencio; aquí se rechazan para que un error del productor no pase inadvertido.
- **Sin campos extra:** un campo que no esté en la tabla (por ejemplo `camera_id`) se rechaza. Así un error de escritura no pasa inadvertido.
- **Tipo de placa:** carro es `AAA999` (tres letras y tres dígitos) y moto es `AAA99A` (tres letras, dos dígitos y una letra). Cualquier otro formato queda como `unknown`, pero la lectura se acepta igual: puede ser una placa diplomática, antigua o un error del OCR que conviene registrar. Solo cuentan los dígitos ASCII `0` a `9`.
- **UUIDv7 en `event_id`:** un UUID es un identificador único; la versión 7 empieza con la fecha y hora, así que los eventos quedan ordenados por momento de creación. Sirve para no procesar dos veces el mismo evento si se reenvía.
- **Ida y vuelta por JSON:** `PlateRead.model_validate_json(read.model_dump_json())` devuelve una lectura igual a la original.

### JSON Schema

[`schemas/plate_read.v1.schema.json`](schemas/plate_read.v1.schema.json) describe el contrato en un formato estándar que entienden otros lenguajes (por ejemplo, la consola web en TypeScript). Describe el JSON que emite `model_dump_json()`, por eso todos los campos aparecen como requeridos.

El esquema describe la estructura, pero es menos exigente que el modelo. Hay reglas que solo aplica `PlateRead`: que `event_id` sea UUID versión 7, que `captured_at` traiga zona horaria (y no sea una marca Unix), que `plate`, `raw_text`, `lane_id` y `photo` no queden vacíos o en blanco, y que `plate_kind` coincida con `plate`. Un JSON que cumple el esquema todavía puede ser rechazado por el modelo; la validación definitiva es `PlateRead.model_validate_json(...)`.

Una prueba compara el archivo guardado con el que genera el modelo. Si cambias el modelo, esa prueba falla hasta que regeneres el archivo:

```powershell
uv run --directory packages/contracts python -m lr_contracts.schema schemas/plate_read.v1.schema.json
```

Revisa el diff del esquema antes de hacer commit: un cambio ahí es un cambio en el contrato. Si quita o cambia un campo existente, rompe a los consumidores y corresponde una versión nueva (`schema_version` 2 y un archivo `plate_read.v2.schema.json`). Actualizar Pydantic también puede cambiar el archivo generado; en ese caso basta con regenerarlo y revisar el diff.

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

Es una biblioteca. Lo único que se ejecuta es el generador del JSON Schema descrito arriba.

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
