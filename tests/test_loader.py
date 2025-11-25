import os

from engine.loader import load_persona, validate_persona


def test_load_persona_and_validate():
    # Use a shipped persona file to avoid creating test fixtures
    persona_path = os.path.join(os.path.dirname(__file__), "..", "personas", "angela.yml")
    persona_path = os.path.abspath(persona_path)

    persona = load_persona(persona_path)

    assert isinstance(persona, dict)
    assert "persona_name" in persona
    assert "default_state" in persona

    is_valid, msg = validate_persona(persona)
    assert is_valid, msg
