from backend.app.models import ModelRule
from backend.app.services.new_api import match_rule


def test_match_rule_by_priority_and_glob():
    rules = [
        ModelRule(name="fallback", pattern="*", match_type="glob", check_type="model_custom_http", priority=100),
        ModelRule(name="deepseek", pattern="deepseek*", match_type="glob", check_type="model_llm_chat", priority=10),
    ]

    rule = match_rule("deepseek-chat", rules)

    assert rule is not None
    assert rule.name == "deepseek"


def test_match_rule_exact():
    rules = [
        ModelRule(name="bge", pattern="bge-large-zh", match_type="exact", check_type="model_embedding", priority=10)
    ]

    rule = match_rule("bge-large-zh", rules)

    assert rule is not None
    assert rule.check_type == "model_embedding"
