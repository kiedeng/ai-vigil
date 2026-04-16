from __future__ import annotations

import json
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from ..models import Check, GoldenCase, GoldenRun, GoldenSet, SampleAsset
from .ai_evaluator import evaluate_response
from .check_runner import execute_check
from .http_utils import read_json_path


def _json_or_none(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _stringify_observed(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def observed_output(check_type: str, response_summary: str | None) -> str:
    document = _json_or_none(response_summary)
    if isinstance(document, dict):
        if check_type in {"model_llm_chat", "model_vision_chat"}:
            content = (document.get("choices") or [{}])[0].get("message", {}).get("content")
            return _stringify_observed(content)
        if check_type == "model_llm_completion":
            content = (document.get("choices") or [{}])[0].get("text")
            return _stringify_observed(content)
    return response_summary or ""


def _type_matches(value: Any, expected: str) -> bool:
    mapping = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    target = mapping.get(expected)
    return isinstance(value, target) if target else True


def _validate_simple_schema(document: Any, schema: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not schema:
        return failures
    required = schema.get("required", [])
    if required and not isinstance(document, dict):
        return ["JSON schema requires an object response"]
    for key in required:
        if key not in document:
            failures.append(f"Missing required key: {key}")
    properties = schema.get("properties", {})
    if isinstance(document, dict) and isinstance(properties, dict):
        for key, rule in properties.items():
            if key in document and isinstance(rule, dict) and not _type_matches(document[key], rule.get("type", "")):
                failures.append(f"Key {key} type mismatch: expected {rule.get('type')}")
    return failures


def _run_error(status: str, outcome_error: str | None, rule_result: dict[str, Any], ai_result: dict[str, Any]) -> str | None:
    if status == "success":
        return None
    if outcome_error:
        return outcome_error
    if ai_result.get("enabled") and ai_result.get("reason"):
        return str(ai_result.get("reason"))
    failures = rule_result.get("failures") or []
    return "; ".join(failures) if failures else None


def validate_expected(response_text: str | None, expected: dict[str, Any]) -> dict[str, Any]:
    text = response_text or ""
    failures: list[str] = []
    contains = expected.get("contains")
    if isinstance(contains, str):
        contains = [contains]
    for item in contains or []:
        if item not in text:
            failures.append(f"Missing text: {item}")
    not_contains = expected.get("not_contains")
    if isinstance(not_contains, str):
        not_contains = [not_contains]
    for item in not_contains or []:
        if item in text:
            failures.append(f"Forbidden text found: {item}")
    if regex := expected.get("regex"):
        if not re.search(str(regex), text, flags=re.S):
            failures.append(f"Regex not matched: {regex}")

    document = _json_or_none(text)
    if json_path := expected.get("json_path"):
        try:
            value = read_json_path(document, str(json_path))
            if "json_path_equals" in expected and value != expected["json_path_equals"]:
                failures.append(f"JSONPath {json_path} value {value!r} != {expected['json_path_equals']!r}")
        except Exception as exc:
            failures.append(f"JSONPath {json_path} not found: {exc}")
    if schema := expected.get("json_schema"):
        failures.extend(_validate_simple_schema(document, schema))
    passed = not failures
    return {"passed": passed, "failures": failures, "checked": bool(expected)}


async def run_golden_case(db: Session, golden_set: GoldenSet, case: GoldenCase) -> GoldenRun:
    started = time.perf_counter()
    input_config = dict(case.input_config or {})
    expected_config = dict(case.expected_config or {})
    if case.sample_asset_id and "file_path" not in input_config:
        asset = db.query(SampleAsset).filter(SampleAsset.id == case.sample_asset_id).first()
        if asset:
            input_config["file_path"] = asset.file_path
            input_config["content_type"] = asset.content_type

    probe = Check(
        name=f"{golden_set.name}/{case.name}",
        type=golden_set.check_type,
        enabled=True,
        interval_seconds=300,
        timeout_seconds=int(input_config.get("timeout_seconds", golden_set.evaluator_config.get("timeout_seconds", 30))),
        failure_threshold=1,
        new_api_instance_id=golden_set.new_api_instance_id,
        model_name=golden_set.model_name,
        request_config=input_config,
        validation_config={},
        ai_config={},
    )
    outcome = await execute_check(db, probe)
    observed = observed_output(golden_set.check_type, outcome.response_summary)
    rule_result = validate_expected(observed, expected_config)
    ai_result: dict[str, Any] = {"enabled": False, "passed": False}
    status = "success" if outcome.ok and rule_result["passed"] else "failure"

    ai_expectation = expected_config.get("ai_expectation")
    use_ai = bool(ai_expectation) and (
        golden_set.evaluator_config.get("always_ai") or not rule_result["passed"]
    )
    if outcome.ok and use_ai:
        ai_result = await evaluate_response(
            db,
            expectation=str(ai_expectation),
            response_text=observed,
            evaluator_config=golden_set.evaluator_config or {},
            prompt_id=golden_set.evaluator_prompt_id,
        )
        if ai_result.get("passed"):
            status = "success"
        else:
            status = "failure"

    if not outcome.ok:
        status = "failure"

    duration_ms = int((time.perf_counter() - started) * 1000)
    run = GoldenRun(
        golden_set_id=golden_set.id,
        case_id=case.id,
        status=status,
        duration_ms=duration_ms,
        response_summary=observed,
        error=_run_error(status, outcome.error, rule_result, ai_result),
        score=ai_result.get("score") if ai_result.get("enabled") else (1.0 if status == "success" else 0.0),
        confidence=ai_result.get("confidence") if ai_result.get("enabled") else None,
        rule_result=rule_result,
        ai_result=ai_result,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


async def run_golden_set(db: Session, golden_set: GoldenSet) -> list[GoldenRun]:
    runs = []
    for case in golden_set.cases:
        if case.enabled:
            runs.append(await run_golden_case(db, golden_set, case))
    return runs
