from __future__ import annotations

import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..models import EvaluatorPrompt
from .new_api_instances import auth_headers, resolve_instance
from .settings import effective_settings


DEFAULT_EVALUATOR_PROMPT = (
    "You are a strict monitoring evaluator. Judge whether the observed output satisfies the expectation.\n"
    "Return JSON only with this shape: "
    "{\"passed\": boolean, \"confidence\": number, \"score\": number, \"reason\": string}.\n"
    "Expectation: {expectation}\nObserved output: {response_text}"
)


def get_active_prompt(db: Session, prompt_id: int | None = None) -> EvaluatorPrompt | None:
    query = db.query(EvaluatorPrompt)
    if prompt_id:
        return query.filter(EvaluatorPrompt.id == prompt_id).first()
    return (
        query.filter(EvaluatorPrompt.name == "default", EvaluatorPrompt.active.is_(True))
        .order_by(EvaluatorPrompt.version.desc())
        .first()
    )


def render_prompt(template: str, expectation: str, response_text: str) -> str:
    return template.replace("{expectation}", expectation).replace("{response_text}", response_text[:6000])


def parse_evaluator_json(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(content[start : end + 1])
        else:
            raise
    if not isinstance(parsed, dict):
        raise ValueError("Evaluator output is not a JSON object")
    return parsed


async def evaluate_response(
    db: Session,
    expectation: str,
    response_text: str,
    evaluator_config: dict[str, Any] | None = None,
    prompt_id: int | None = None,
) -> dict[str, Any]:
    evaluator_config = evaluator_config or {}
    settings = effective_settings(db)
    model = evaluator_config.get("evaluator_model") or settings["evaluator_model"]
    instance = resolve_instance(db, evaluator_config.get("new_api_instance_id"))
    prompt_row = get_active_prompt(db, prompt_id)
    prompt_template = evaluator_config.get("prompt_template") or (
        prompt_row.prompt_template if prompt_row else DEFAULT_EVALUATOR_PROMPT
    )
    headers = auth_headers(instance)
    base = instance.base_url.rstrip("/")

    try:
        prompt = render_prompt(prompt_template, expectation, response_text)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": evaluator_config.get("temperature", 0),
            "max_tokens": evaluator_config.get("max_tokens", 512),
        }
        async with httpx.AsyncClient(timeout=evaluator_config.get("timeout_seconds", 30)) as client:
            response = await client.post(f"{base}/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
        content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = parse_evaluator_json(content)
        confidence = float(parsed.get("confidence", 0))
        score = float(parsed.get("score", 1 if parsed.get("passed") else 0))
        passed = bool(parsed.get("passed")) and confidence >= float(evaluator_config.get("min_confidence", 0))
        return {
            "enabled": True,
            "status": "success",
            "passed": passed,
            "confidence": confidence,
            "score": score,
            "reason": str(parsed.get("reason", "")),
            "model": model,
            "instance_id": instance.id,
            "instance_name": instance.name,
            "prompt_id": prompt_row.id if prompt_row else None,
            "prompt_version": prompt_row.version if prompt_row else None,
            "raw": content[:2000],
        }
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:1000] if exc.response is not None else ""
        return {
            "enabled": True,
            "status": "evaluator_http_error",
            "passed": False,
            "confidence": 0,
            "score": 0,
            "reason": f"Evaluator HTTP error: {exc.response.status_code}; {body}",
            "model": model,
            "instance_id": instance.id,
            "instance_name": instance.name,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "status": "evaluator_error",
            "passed": False,
            "confidence": 0,
            "score": 0,
            "reason": str(exc),
            "model": model,
            "instance_id": instance.id,
            "instance_name": instance.name,
        }
