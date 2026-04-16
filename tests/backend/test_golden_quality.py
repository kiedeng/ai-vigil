from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.services.ai_evaluator import render_prompt
from backend.app.services.analytics import trend_summary
from backend.app.services.golden import observed_output, validate_expected


def test_render_prompt_allows_literal_json_braces():
    template = (
        'Return JSON only: {"passed": boolean, "confidence": number}.\n'
        "Expectation: {expectation}\nObserved output: {response_text}"
    )

    rendered = render_prompt(template, "must be ok", '{"status":"ok"}')

    assert '{"passed": boolean, "confidence": number}' in rendered
    assert "Expectation: must be ok" in rendered
    assert 'Observed output: {"status":"ok"}' in rendered


def test_validate_expected_supports_text_jsonpath_and_schema():
    result = validate_expected(
        '{"status":"ok","data":{}}',
        {
            "contains": "ok",
            "json_path": "$.status",
            "json_path_equals": "ok",
            "json_schema": {
                "required": ["status", "data"],
                "properties": {"status": {"type": "string"}, "data": {"type": "object"}},
            },
        },
    )

    assert result["passed"] is True
    assert result["failures"] == []


def test_observed_output_extracts_llm_message_content():
    summary = (
        '{"choices":[{"message":{"content":"{\\"status\\":\\"ok\\",\\"task\\":\\"golden\\"}"}}]}'
    )

    result = validate_expected(
        observed_output("model_llm_chat", summary),
        {"json_path": "$.status", "json_path_equals": "ok"},
    )

    assert result["passed"] is True


def test_trend_summary_empty_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_factory()
    try:
        result = trend_summary(db)
    finally:
        db.close()

    assert result["windows"]["1h"]["availability"] == 0.0
    assert result["golden"]["pass_rate"] == 0.0
