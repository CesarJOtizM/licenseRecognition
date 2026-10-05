# Edge agent (equipo local de la portería)

Programa que corre en el mini-PC de la portería. Captura video (webcam, cámara IP o archivo), lee las placas, decide si abre, acciona la puerta y guarda los eventos en local para sincronizarlos con la API cuando hay internet.

"Edge" significa que el procesamiento ocurre en el borde de la red, junto a la cámara, y no en la nube. Así la puerta abre en menos de 1,5 s y sigue funcionando sin internet.

## Estado

Solo el esqueleto del paquete y su configuración de calidad. En la fase 0, paso 2, se define el contrato `PlateRead`. El pipeline de visión llega en la fase 1.

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
