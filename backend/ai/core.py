import json
import re
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from config import AI_AUDIT_LOG_PATH, read_settings, provider_headers
from utils.text_utils import compact_text, endpoint, parse_ai_object, http_error_detail


def append_ai_audit(event_type, payload):
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **payload,
    }
    try:
        AI_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AI_AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def log_ai_command(stage, user, prompt, payload=None, reply=None, results=None, selected_smeta_id=None, extra=None):
    append_ai_audit(
        "ai_command",
        {
            "stage": stage,
            "user": getattr(user, "email", None),
            "user_id": getattr(user, "id", None),
            "prompt": prompt,
            "payload": payload,
            "reply": reply,
            "results": results or [],
            "selected_smeta_id": selected_smeta_id,
            "extra": extra or {},
        },
    )


def simple_ai_assistant(prompt: str):
    text = prompt.lower()
    if "дорого" in text or "цена" in text:
        return "Рассмотрите более дешевые материалы или альтернативные поставщики."
    if "ошибка" in text or "провер" in text:
        return "Проверьте единицы измерения, дубли позиций и строки с нулевым количеством."
    return "Рассмотрите оптимизацию сметы: проверить единицы и объемы."


def call_ai_json(system_prompt, user_text):
    settings = read_settings()
    if not settings.get("model"):
        raise HTTPException(status_code=400, detail="Выберите модель AI в настройках")
    payload = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": compact_text(user_text)},
        ],
    }
    try:
        with httpx.Client(timeout=90) as client:
            response = client.post(
                endpoint(settings["base_url"], "chat/completions"),
                headers=provider_headers(settings),
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_detail(exc, "AI-провайдер отклонил запрос")) from exc

    content = response.json()["choices"][0]["message"]["content"]
    match = re.search(r"\[[\s\S]*\]", content)
    if not match:
        raise HTTPException(status_code=502, detail="AI не вернул JSON-массив материалов")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="AI вернул невалидный JSON") from exc


def call_ai_object(system_prompt, user_text):
    settings = read_settings()
    if not settings.get("model"):
        raise HTTPException(status_code=400, detail="Выберите модель AI в настройках")
    payload = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": compact_text(user_text, 16000)},
        ],
    }
    try:
        with httpx.Client(timeout=90) as client:
            response = client.post(
                endpoint(settings["base_url"], "chat/completions"),
                headers=provider_headers(settings),
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_detail(exc, "AI-провайдер отклонил запрос")) from exc

    content = response.json()["choices"][0]["message"]["content"]
    parsed = parse_ai_object(content)
    if parsed:
        return parsed
    return {"reply": content.strip(), "actions": []}
