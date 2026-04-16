from backend.app.services.http_utils import read_json_path, summarize_text


def test_read_json_path_nested_list():
    payload = {"data": [{"embedding": [1, 2, 3]}]}

    assert read_json_path(payload, "$.data[0].embedding") == [1, 2, 3]


def test_summarize_text_truncates():
    assert summarize_text("abc" * 10, limit=5) == "abcab"

