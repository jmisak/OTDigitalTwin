def test_generate_suggestions_smoke():
    from app import generate_suggestions

    # Call with empty conversation history to exercise the quick-return path
    result = generate_suggestions([], [], "sample.yml")

    assert isinstance(result, str)
    assert len(result) > 0
