
import json
import os
from pathlib import Path

from fastapi import HTTPException

SETTINGS_PATH = Path(__file__).with_name("settings.json")
AI_AUDIT_LOG_PATH = Path(__file__).with_name("logs") / "assistant_audit.jsonl"

DEFAULT_SECTIONS = [
    "Оборудование",
    "Монтажные работы",
    "Пусконаладочные работы",
    "Кабельные линии",
    "Материалы и расходники",
    "Доставка и логистика",
    "Проектирование",
    "Прочее",
]

# # VSB_RULES_INJECT_V1
_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.md")


def _load_rules():
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def read_settings():
    defaults = {
        "base_url": "https://api.vsegpt.ru/v1",
        "api_key": "",
        "model": "",
        "assistant_prompt": (
            "Ты встроенный ассистент сметчика. Отвечай кратко, по-русски и по делу. "
            "Работай как практик по сметам: смотри на смету целиком, а не на один раздел, "
            "связывай оборудование, монтаж и пусконаладку по смыслу устройства и системы. "
            "Если видишь регистратор, видеорегистратор, NVR или DVR, предлагай монтаж и пусконаладку "
            "системы видеонаблюдения, а при необходимости настройку удаленного доступа. "
            "Если видишь СКУД-оборудование, связывай его с монтажом и пусконаладкой СКУД. "
            "Не придумывай цены, не дублируй позиции без необходимости и не теряй количество. "
            "Если данных не хватает, задай один короткий уточняющий вопрос. "
            "Если пользователь просит проверить, исправить или пересчитать смету, проверь всю смету целиком."
        ),
    }
    if not SETTINGS_PATH.exists():
        return defaults
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defaults
    return {**defaults, **data}


def write_settings(settings):
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def merged_ai_system_prompt(settings):
    prompt = (settings.get("assistant_prompt") or "").strip()
    return prompt or (
        "Ты встроенный ассистент сметчика. Отвечай кратко, по-русски и по делу. "
        "Если пользователь просит проверить смету, смотри на нее целиком. "
        "Не придумывай цены и не дублируй позиции без необходимости."
    )


def public_settings(settings):
    api_key = settings.get("api_key", "")
    masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 12 else bool(api_key)
    return {
        "base_url": settings.get("base_url", ""),
        "model": settings.get("model", ""),
        "has_api_key": bool(api_key),
        "masked_api_key": masked_key,
        "assistant_prompt": settings.get("assistant_prompt", ""),
    }


def provider_headers(settings):
    if not settings.get("api_key"):
        raise HTTPException(status_code=400, detail="Сначала сохраните API-ключ в настройках")
    return {"Authorization": f"Bearer {settings['api_key']}", "Content-Type": "application/json"}
