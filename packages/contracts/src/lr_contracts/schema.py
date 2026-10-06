"""Genera el JSON Schema del contrato `PlateRead`.

Uso: `python -m lr_contracts.schema schemas/plate_read.v1.schema.json`
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from lr_contracts.plate_read import PlateRead


def render_schema(model: type[BaseModel] = PlateRead) -> str:
    schema = model.model_json_schema(mode="serialization")
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_schema(path: Path) -> None:
    # newline="\n" keeps LF on Windows, matching .gitattributes and the snapshot test.
    path.write_text(render_schema(), encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Escribe el JSON Schema de PlateRead.")
    parser.add_argument("path", type=Path, help="archivo de salida")
    args = parser.parse_args(argv)
    write_schema(args.path)


if __name__ == "__main__":
    main()
