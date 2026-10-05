from importlib.metadata import version

import lr_contracts


def test_lr_contracts_se_instala_como_dependencia_declarada() -> None:
    assert version("lr-contracts") == lr_contracts.__version__


def test_lr_contracts_se_importa_desde_su_propio_paquete() -> None:
    assert lr_contracts.__file__ is not None
    assert "packages" in lr_contracts.__file__
    assert "contracts" in lr_contracts.__file__
