from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..models import Check, CheckRun, CheckState
from .ai_evaluator import evaluate_response
from .alerts import process_alerts
from .http_utils import body_from_config, read_json_path, summarize_text
from .new_api_instances import auth_headers, resolve_instance


TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\xe2\x9d\xb3\x00\x00\x00\x00IEND\xaeB`\x82"
)
TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lV9m6wAAAABJRU5ErkJggg=="
)


@dataclass
class CheckOutcome:
    ok: bool
    response_status_code: int | None = None
    response_summary: str | None = None
    error: str | None = None
    ai_result: dict[str, Any] = field(default_factory=dict)


def _check_new_api_url(db: Session, check: Check, path: str) -> str:
    base = resolve_instance(db, check.new_api_instance_id).base_url.rstrip("/")
    return f"{base}{path}"


def _check_headers(db: Session, check: Check, content_type: str | None = "application/json") -> dict[str, str]:
    return auth_headers(resolve_instance(db, check.new_api_instance_id), content_type)


def _validate_response(
    status_code: int,
    text: str,
    json_body: Any,
    validation_config: dict[str, Any],
    elapsed_ms: int,
) -> str | None:
    expected = validation_config.get("expected_status_codes") or validation_config.get("expected_status")
    if expected is None:
        expected = [200]
    elif isinstance(expected, int):
        expected = [expected]
    if status_code not in expected:
        return f"Unexpected status code {status_code}; expected {expected}"

    max_latency = validation_config.get("max_latency_ms")
    if max_latency and elapsed_ms > int(max_latency):
        return f"Latency {elapsed_ms}ms exceeded max_latency_ms={max_latency}"

    contains = validation_config.get("contains")
    if contains and contains not in text:
        return f"Response does not contain required text: {contains}"

    json_path = validation_config.get("json_path")
    if json_path:
        try:
            value = read_json_path(json_body, json_path)
        except Exception as exc:
            return f"JSONPath {json_path} not found: {exc}"
        expected_value = validation_config.get("json_path_equals")
        if expected_value is not None and value != expected_value:
            return f"JSONPath {json_path} value {value!r} != {expected_value!r}"
    return None


def _model_required(check: Check) -> str | None:
    return check.model_name or None


def _merge_payload(default_payload: dict[str, Any], request_config: dict[str, Any]) -> dict[str, Any]:
    payload = {**default_payload}
    payload.update(request_config.get("payload", {}))
    return payload


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "".join(parts).strip()
    return str(value).strip()


def _extract_chat_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    for value in (
        message.get("content"),
        message.get("reasoning_content"),
        message.get("reasoning"),
        choice.get("text"),
        choice.get("delta", {}).get("content") if isinstance(choice.get("delta"), dict) else None,
    ):
        text = _extract_text(value)
        if text:
            return text
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        return json.dumps(tool_calls, ensure_ascii=False)
    return ""


def _json_summary(response: httpx.Response) -> tuple[str | None, Any]:
    summary = summarize_text(response.text)
    try:
        return summary, response.json()
    except ValueError:
        return summary, None


def _wav_bytes() -> bytes:
    sample_rate = 16_000
    sample_count = int(sample_rate * 0.2)
    pcm = b"\x00\x00" * sample_count
    data_size = len(pcm)
    header = (
        b"RIFF"
        + (36 + data_size).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + sample_rate.to_bytes(4, "little")
        + (sample_rate * 2).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + data_size.to_bytes(4, "little")
    )
    return header + pcm


async def _run_llm_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    payload = _merge_payload({
        "model": model,
        "messages": [{"role": "user", "content": request_config.get("prompt", "Reply with OK only.")}],
        "temperature": 0,
        "max_tokens": 128,
    }, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/chat/completions"), headers=_check_headers(db, check), json=payload)
    summary, data = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    content = _extract_chat_content(data)
    if not content:
        return CheckOutcome(False, response.status_code, summary, "LLM response content is empty")
    return CheckOutcome(True, response.status_code, summary)


async def _run_completion_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    payload = _merge_payload({
        "model": model,
        "prompt": request_config.get("prompt", "Reply with OK only."),
        "temperature": 0,
        "max_tokens": 64,
    }, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/completions"), headers=_check_headers(db, check), json=payload)
    summary, data = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    content = (data or {}).get("choices", [{}])[0].get("text")
    if not content:
        return CheckOutcome(False, response.status_code, summary, "Completion response text is empty")
    return CheckOutcome(True, response.status_code, summary)


async def _run_vision_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    payload = _merge_payload({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request_config.get("prompt", "Describe this image in one short word.")},
                    {"type": "image_url", "image_url": {"url": request_config.get("image_url", TINY_PNG_DATA_URL)}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 128,
    }, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/chat/completions"), headers=_check_headers(db, check), json=payload)
    summary, data = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    content = _extract_chat_content(data)
    if not content:
        return CheckOutcome(False, response.status_code, summary, "Vision response content is empty")
    return CheckOutcome(True, response.status_code, summary)


async def _run_embedding_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    payload = _merge_payload({"model": model, "input": request_config.get("input", "health check")}, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/embeddings"), headers=_check_headers(db, check), json=payload)
    summary, data = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    embedding = (data or {}).get("data", [{}])[0].get("embedding")
    if not isinstance(embedding, list) or not embedding:
        return CheckOutcome(False, response.status_code, summary, "Embedding vector is empty")
    return CheckOutcome(True, response.status_code, summary)


async def _run_rerank_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    endpoint = request_config.get("endpoint", "/v1/rerank")
    payload = _merge_payload({
        "model": model,
        "query": request_config.get("query", "health check"),
        "documents": request_config.get("documents", ["service is healthy", "service is unavailable"]),
    }, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, endpoint), headers=_check_headers(db, check), json=payload)
    summary, data = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    results = (data or {}).get("results") or (data or {}).get("data")
    if not isinstance(results, list) or not results:
        return CheckOutcome(False, response.status_code, summary, "Rerank response results are empty")
    return CheckOutcome(True, response.status_code, summary)


async def _run_audio_file_check(db: Session, check: Check, endpoint: str) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    data = {"model": model, "response_format": request_config.get("response_format", "json")}
    if language := request_config.get("language"):
        data["language"] = str(language)
    data.update(request_config.get("form", {}))
    file_path = request_config.get("file_path")
    if file_path:
        path = Path(str(file_path)).expanduser()
        file_name = path.name
        file_bytes = path.read_bytes()
    else:
        file_name = "health.wav"
        file_bytes = _wav_bytes()
    files = {"file": (file_name, file_bytes, request_config.get("content_type", "audio/wav"))}
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, endpoint), headers=_check_headers(db, check, None), data=data, files=files)
    summary, body = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    if isinstance(body, dict):
        if "text" not in body:
            return CheckOutcome(False, response.status_code, summary, "Audio response has no text field")
        if request_config.get("require_text") and not body.get("text"):
            return CheckOutcome(False, response.status_code, summary, "Audio response text is empty")
    elif not response.text:
        return CheckOutcome(False, response.status_code, summary, "Audio response body is empty")
    return CheckOutcome(True, response.status_code, summary)


async def _run_audio_speech_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    payload = _merge_payload({
        "model": model,
        "input": request_config.get("input", "health check"),
        "voice": request_config.get("voice", "alloy"),
    }, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/audio/speech"), headers=_check_headers(db, check), json=payload)
    content_type = response.headers.get("content-type", "")
    summary = f"content-type={content_type}; bytes={len(response.content)}"
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summarize_text(response.text) or summary, f"new-api returned {response.status_code}")
    if not response.content:
        return CheckOutcome(False, response.status_code, summary, "Speech response audio is empty")
    return CheckOutcome(True, response.status_code, summary)


async def _run_image_generation_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    payload = _merge_payload({
        "model": model,
        "prompt": request_config.get("prompt", "A simple green circle icon on a white background"),
        "n": 1,
        "size": request_config.get("size", "512x512"),
    }, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/images/generations"), headers=_check_headers(db, check), json=payload)
    summary, data = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    item = ((data or {}).get("data") or [{}])[0]
    if not item.get("url") and not item.get("b64_json"):
        return CheckOutcome(False, response.status_code, summary, "Image generation response has no image")
    return CheckOutcome(True, response.status_code, summary)


async def _run_image_edit_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    data = {
        "model": model,
        "prompt": request_config.get("prompt", "Make the image brighter"),
        "n": str(request_config.get("n", 1)),
        "size": request_config.get("size", "512x512"),
    }
    data.update(request_config.get("form", {}))
    files = {"image": ("health.png", TINY_PNG, "image/png")}
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/images/edits"), headers=_check_headers(db, check, None), data=data, files=files)
    summary, body = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    item = ((body or {}).get("data") or [{}])[0]
    if not item.get("url") and not item.get("b64_json"):
        return CheckOutcome(False, response.status_code, summary, "Image edit response has no image")
    return CheckOutcome(True, response.status_code, summary)


async def _run_moderation_check(db: Session, check: Check) -> CheckOutcome:
    model = _model_required(check)
    if not model:
        return CheckOutcome(ok=False, error="model_name is required")
    request_config = check.request_config or {}
    payload = _merge_payload({
        "model": model,
        "input": request_config.get("input", "This is a harmless health check message."),
    }, request_config)
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.post(_check_new_api_url(db, check, "/v1/moderations"), headers=_check_headers(db, check), json=payload)
    summary, data = _json_summary(response)
    if response.status_code >= 400:
        return CheckOutcome(False, response.status_code, summary, f"new-api returned {response.status_code}")
    results = (data or {}).get("results")
    if not isinstance(results, list) or not results:
        return CheckOutcome(False, response.status_code, summary, "Moderation results are empty")
    return CheckOutcome(True, response.status_code, summary)


async def _evaluate_with_ai(db: Session, check: Check, response_text: str) -> dict[str, Any]:
    expectation = check.ai_config.get("expectation") or check.validation_config.get("ai_expectation")
    if not expectation:
        return {"enabled": False, "passed": True, "reason": "AI evaluation is not configured"}
    evaluator_config = {**(check.ai_config or {})}
    if check.new_api_instance_id and not evaluator_config.get("new_api_instance_id"):
        evaluator_config["new_api_instance_id"] = check.new_api_instance_id
    result = await evaluate_response(
        db,
        expectation=expectation,
        response_text=response_text,
        evaluator_config=evaluator_config,
        prompt_id=check.ai_config.get("prompt_id"),
    )
    return {"enabled": True, **result}


async def _run_http_check(db: Session, check: Check) -> CheckOutcome:
    request_config = check.request_config or {}
    method = request_config.get("method", "GET").upper()
    url = request_config.get("url")
    if not url:
        return CheckOutcome(ok=False, error="request_config.url is required")
    headers = request_config.get("headers", {})
    params = request_config.get("query", {})
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
        response = await client.request(method, url, headers=headers, params=params, **body_from_config(request_config))
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    text = response.text
    summary = summarize_text(text)
    json_body: Any = None
    try:
        json_body = response.json()
    except ValueError:
        pass
    validation_error = _validate_response(
        response.status_code, text, json_body, check.validation_config or {}, elapsed_ms
    )
    if validation_error:
        return CheckOutcome(False, response.status_code, summary, validation_error)

    ai_enabled = check.type == "http_content_ai" or bool(check.ai_config.get("enabled"))
    ai_result: dict[str, Any] = {}
    if ai_enabled:
        try:
            ai_result = await _evaluate_with_ai(db, check, text)
        except Exception as exc:
            return CheckOutcome(False, response.status_code, summary, f"AI evaluator failed: {exc}")
        if not ai_result.get("passed", False):
            return CheckOutcome(False, response.status_code, summary, ai_result.get("reason"), ai_result)
    return CheckOutcome(True, response.status_code, summary, ai_result=ai_result)


async def execute_check(db: Session, check: Check) -> CheckOutcome:
    try:
        if check.type == "model_llm_chat":
            return await _run_llm_check(db, check)
        if check.type == "model_llm_completion":
            return await _run_completion_check(db, check)
        if check.type == "model_vision_chat":
            return await _run_vision_check(db, check)
        if check.type == "model_embedding":
            return await _run_embedding_check(db, check)
        if check.type == "model_rerank":
            return await _run_rerank_check(db, check)
        if check.type == "model_audio_transcription":
            return await _run_audio_file_check(db, check, "/v1/audio/transcriptions")
        if check.type == "model_audio_translation":
            return await _run_audio_file_check(db, check, "/v1/audio/translations")
        if check.type == "model_audio_speech":
            return await _run_audio_speech_check(db, check)
        if check.type == "model_image_generation":
            return await _run_image_generation_check(db, check)
        if check.type == "model_image_edit":
            return await _run_image_edit_check(db, check)
        if check.type == "model_moderation":
            return await _run_moderation_check(db, check)
        if check.type in {"model_custom_http", "http_health", "http_content_ai"}:
            return await _run_http_check(db, check)
        return CheckOutcome(False, error=f"Unsupported check type: {check.type}")
    except Exception as exc:
        return CheckOutcome(False, error=str(exc))


async def run_check_once(
    db: Session,
    check: Check,
    run_mode: str = "manual",
    notify: bool = True,
) -> CheckRun:
    started = time.perf_counter()
    outcome = await execute_check(db, check)

    duration_ms = int((time.perf_counter() - started) * 1000)
    run = CheckRun(
        check_id=check.id,
        status="success" if outcome.ok else "failure",
        run_mode=run_mode,
        duration_ms=duration_ms,
        response_status_code=outcome.response_status_code,
        response_summary=outcome.response_summary,
        error=outcome.error,
        ai_result=outcome.ai_result,
    )
    db.add(run)
    db.flush()

    state = check.state or CheckState(
        check_id=check.id,
        status="unknown",
        consecutive_failures=0,
        alert_open=False,
    )
    if check.state is None:
        db.add(state)
    current_failures = state.consecutive_failures or 0
    state.status = run.status
    state.last_run_id = run.id
    if run.status == "success":
        state.consecutive_failures = 0
        state.last_success_at = datetime.utcnow()
    else:
        state.consecutive_failures = current_failures + 1
        state.last_failure_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    db.refresh(state)

    if notify and run_mode != "test":
        await process_alerts(db, check, run, state)
    db.refresh(run)
    return run
