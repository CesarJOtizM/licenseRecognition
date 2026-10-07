"""Comprueba el sondeo de tests/conftest.py corriendo pytest en una carpeta temporal."""

from pathlib import Path

import pytest

CONFTEST = Path(__file__).with_name("conftest.py")
UNREACHABLE_URL = "postgresql+psycopg://porteria:porteria@127.0.0.1:1/porteria_test"

MARKED_TEST = """
import pytest

pytestmark = pytest.mark.db


def test_usa_la_base(db_engine):
    pass
"""


@pytest.fixture
def without_db(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    monkeypatch.setenv("TEST_DATABASE_URL", UNREACHABLE_URL)
    monkeypatch.delenv("API_TEST_REQUIRE_DB", raising=False)
    # pytester lee la salida en UTF-8; en Windows el subproceso escribiría en cp1252.
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makeini("[pytest]\nmarkers =\n    db: necesita PostgreSQL\n")
    return pytester


def test_sin_base_las_pruebas_db_se_saltan_con_motivo(without_db: pytest.Pytester) -> None:
    without_db.makepyfile(MARKED_TEST)

    result = without_db.runpytest_subprocess("-rs")

    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*PostgreSQL de pruebas no disponible*"])


def test_sin_base_y_con_api_test_require_db_la_sesion_falla(
    without_db: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_TEST_REQUIRE_DB", "1")
    without_db.makepyfile(MARKED_TEST)

    result = without_db.runpytest_subprocess()

    result.assert_outcomes(errors=1)
    assert result.ret != 0


def test_db_engine_exige_la_marca_db(without_db: pytest.Pytester) -> None:
    without_db.makepyfile("def test_sin_marca(db_engine):\n    pass\n")

    result = without_db.runpytest_subprocess()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*pytest.mark.db*"])
