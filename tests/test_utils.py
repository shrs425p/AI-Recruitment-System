from src.common import clean_json_response


def test_clean_json_response_accepts_plain_json():
    assert clean_json_response('{"name": "Ada", "score": 98}') == {"name": "Ada", "score": 98}


def test_clean_json_response_strips_markdown_fence():
    text = """```json
    {"ok": true, "items": [1, 2]}
    ```"""
    assert clean_json_response(text) == {"ok": True, "items": [1, 2]}


def test_clean_json_response_extracts_json_from_text():
    assert clean_json_response('Here is the result: {"ok": true}') == {"ok": True}


def test_clean_json_response_repairs_trailing_commas():
    raw = """```JSON
    {
      "name": "Bob",
      "skills": ["Python", "Flask",],
      "experience": 5,
    }
    ```"""
    assert clean_json_response(raw) == {
        "name": "Bob",
        "skills": ["Python", "Flask"],
        "experience": 5,
    }
