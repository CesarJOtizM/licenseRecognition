import json
from pathlib import Path

from lr_contracts.plate_read import PlateRead
from lr_contracts.schema import main, render_schema
from pydantic import ConfigDict

SNAPSHOT = Path(__file__).parents[1] / "schemas" / "plate_read.v1.schema.json"
REGENERATE = (
    "uv run --directory packages/contracts python -m lr_contracts.schema "
    "schemas/plate_read.v1.schema.json"
)


def test_el_esquema_guardado_coincide_con_el_modelo() -> None:
    assert SNAPSHOT.read_text(encoding="utf-8") == render_schema(), (
        f"El esquema guardado está desactualizado. Regenéralo con: {REGENERATE}"
    )


def test_el_esquema_guardado_usa_finales_de_linea_lf() -> None:
    assert b"\r" not in SNAPSHOT.read_bytes()


def test_el_esquema_prohibe_campos_adicionales() -> None:
    schema = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False


def test_el_esquema_marca_como_requeridos_todos_los_campos_emitidos() -> None:
    schema = json.loads(render_schema())
    assert sorted(schema["required"]) == sorted(PlateRead.model_fields)


def test_un_cambio_en_el_modelo_cambia_el_esquema() -> None:
    class PlateReadWithCamera(PlateRead):
        model_config = ConfigDict(title="PlateRead")

        camera_id: str

    drifted = render_schema(PlateReadWithCamera)
    assert "camera_id" in json.loads(drifted)["properties"]
    assert drifted != SNAPSHOT.read_text(encoding="utf-8")


def test_main_escribe_el_esquema_con_finales_lf(tmp_path: Path) -> None:
    target = tmp_path / "plate_read.schema.json"
    main([str(target)])
    assert target.read_bytes() == render_schema().encode("utf-8")
    assert b"\r" not in target.read_bytes()
