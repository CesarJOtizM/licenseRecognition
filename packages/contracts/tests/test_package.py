from importlib.metadata import version

import lr_contracts
from lr_contracts import plate_read


def test_el_paquete_expone_su_version() -> None:
    assert lr_contracts.__version__ == "0.1.0"


def test_la_version_coincide_con_la_del_paquete_instalado() -> None:
    assert lr_contracts.__version__ == version("lr-contracts")


def test_el_paquete_exporta_el_contrato_desde_la_raiz() -> None:
    assert lr_contracts.__all__ == [
        "PlateKind",
        "PlateRead",
        "Source",
        "__version__",
        "classify_plate",
        "new_event_id",
        "normalize_plate",
    ]
    assert lr_contracts.PlateRead is plate_read.PlateRead
    assert lr_contracts.classify_plate("ABC123") is lr_contracts.PlateKind.CAR
