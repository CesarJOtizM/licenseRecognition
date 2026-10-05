# Edge agent (equipo local de la portería)

Programa que corre en el mini-PC de la portería. Captura video (webcam, cámara IP o archivo), lee las placas, decide si abre, acciona la puerta y guarda los eventos en local para sincronizarlos con la API cuando hay internet.

"Edge" significa que el procesamiento ocurre en el borde de la red, junto a la cámara, y no en la nube. Así la puerta abre en menos de 1,5 s y sigue funcionando sin internet.

## Estado

Solo el esqueleto del paquete, su configuración de calidad y la dependencia del paquete de contratos. En la fase 0, paso 2, se define el contrato `PlateRead`. El pipeline de visión llega en la fase 1.

## Dependencia de `lr-contracts`

Los eventos que produce este servicio (como `PlateRead`) se definen en [`packages/contracts`](../../packages/contracts/), no aquí. edge-agent lo declara en `pyproject.toml` como dependencia de ruta editable (`[tool.uv.sources]`), así que se importa como cualquier paquete instalado: `import lr_contracts`. Ver el [ADR 0004](../../docs/decisiones/0004-paquete-de-contratos-compartido.md).

- Un cambio en el código de `packages/contracts` se ve aquí sin reinstalar nada.
- Un cambio en las dependencias o la versión de `packages/contracts` obliga a correr `uv lock --directory services/edge-agent`; si no, `uv sync --locked` falla.
- `tests/test_contracts_dependency.py` comprueba que el paquete está instalado y viene de `packages/contracts`.

## Estructura

```text
services/edge-agent/
├── pyproject.toml      # dependencias y configuración de pytest, coverage y mypy
├── uv.lock             # versiones exactas (se sube a git)
├── src/edge_agent/     # código del paquete
└── tests/              # pruebas con pytest
```

Se usa el layout `src/`: el código vive en `src/edge_agent` y no directamente en la raíz del servicio. Así las pruebas importan el paquete instalado y no los archivos sueltos, y se detecta si algo falta en el empaquetado.

## Cómo se ejecuta

Todavía no hay nada que ejecutar.

## Cómo se prueba

Desde la raíz del repositorio:

```powershell
uv sync --directory services/edge-agent          # crea .venv e instala dependencias
uv run --directory services/edge-agent pytest    # pruebas con cobertura (mínimo 80 %)
uv run --directory services/edge-agent mypy      # chequeo de tipos estricto
```
