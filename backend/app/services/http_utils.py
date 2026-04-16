from typing import Any


def summarize_text(value: str | bytes | None, limit: int = 2000) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = text.strip()
    return text[:limit] if len(text) > limit else text


def read_json_path(document: Any, path: str) -> Any:
    if not path or path == "$":
        return document
    parts = path[2:].split(".") if path.startswith("$.") else path.split(".")
    current = document
    for part in parts:
        if not part:
            continue
        if "[" in part and part.endswith("]"):
            field, index_text = part[:-1].split("[", 1)
            if field:
                current = current[field]
            current = current[int(index_text)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            current = getattr(current, part)
    return current


def body_from_config(request_config: dict[str, Any]) -> dict[str, Any]:
    body_type = request_config.get("body_type", "json")
    if body_type == "json":
        body = request_config.get("json_body", request_config.get("body"))
        return {"json": body} if body is not None else {}
    if body_type == "form":
        body = request_config.get("form_body", request_config.get("body"))
        return {"data": body} if body is not None else {}
    if body_type == "raw":
        body = request_config.get("raw_body", request_config.get("body"))
        return {"content": body} if body is not None else {}
    return {}
