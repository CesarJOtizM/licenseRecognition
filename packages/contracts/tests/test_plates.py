import pytest
from lr_contracts.plates import PlateKind, classify_plate, normalize_plate


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (" abc-123 ", "ABC123"),
        ("abc 12d", "ABC12D"),
        ("a\tb-c\n1 2 3", "ABC123"),
        (" - ", ""),
    ],
)
def test_normalizar_placa_quita_espacios_y_guiones_y_pasa_a_mayusculas(
    text: str, expected: str
) -> None:
    assert normalize_plate(text) == expected


@pytest.mark.parametrize(
    ("plate", "expected"),
    [
        ("ABC123", PlateKind.CAR),
        ("ABC12D", PlateKind.MOTORCYCLE),
        ("ABC12", PlateKind.UNKNOWN),
        ("R12345", PlateKind.UNKNOWN),
        ("CD1234", PlateKind.UNKNOWN),
        ("ABCD123", PlateKind.UNKNOWN),
        ("ABC1234", PlateKind.UNKNOWN),
        ("ABC123\n", PlateKind.UNKNOWN),
        ("ABC\u0661\u0662\u0663", PlateKind.UNKNOWN),
        ("ABC\u0661\u0662D", PlateKind.UNKNOWN),
    ],
)
def test_clasificar_placa_segun_el_formato(plate: str, expected: PlateKind) -> None:
    assert classify_plate(plate) is expected


def test_los_tipos_de_placa_se_serializan_en_minusculas() -> None:
    assert [kind.value for kind in PlateKind] == ["car", "motorcycle", "unknown"]
