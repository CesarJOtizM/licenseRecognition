"""Hook commit-msg: elimina los trailers de atribución a agentes de IA.

Algunas herramientas agregan solas líneas como
`Co-authored-by: Cursor <cursoragent@cursor.com>` al mensaje del commit.
La convención del proyecto es que los mensajes no lleven atribución de IA.
"""

import re
import sys
from pathlib import Path

PATRON = re.compile(r"^Co-authored-by:\s*Cursor\b.*$", re.IGNORECASE)


def limpiar(mensaje: str) -> str:
    lineas = [linea for linea in mensaje.splitlines() if not PATRON.match(linea)]
    return "\n".join(lineas).rstrip() + "\n"


def main() -> int:
    archivo = Path(sys.argv[1])
    original = archivo.read_text(encoding="utf-8")
    limpio = limpiar(original)
    if limpio != original:
        archivo.write_text(limpio, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
