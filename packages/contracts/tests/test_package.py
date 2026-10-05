from importlib.metadata import version

import lr_contracts


def test_el_paquete_expone_su_version() -> None:
    assert lr_contracts.__version__ == "0.1.0"


def test_la_version_coincide_con_la_del_paquete_instalado() -> None:
    assert lr_contracts.__version__ == version("lr-contracts")
