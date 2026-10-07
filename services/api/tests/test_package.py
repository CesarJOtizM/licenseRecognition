import porteria_api


def test_el_paquete_expone_su_version() -> None:
    assert porteria_api.__version__ == "0.1.0"
