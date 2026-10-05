import edge_agent


def test_el_paquete_expone_su_version() -> None:
    assert edge_agent.__version__ == "0.1.0"
