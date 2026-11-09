"""T26: fallo intencional autorizado, exclusivo de la rama de demostracion."""


def test_ci_detects_authorized_failure():
    observed = {"signal": "red"}
    assert observed["signal"] == "green"
