
import json
import re


def strip_code_fences(text_value):
    text_value = (text_value or "").strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text_value, flags=re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return text_value


def extract_balanced_json_object(text_value):
    text_value = text_value or ""
    start = text_value.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text_value)):
        char = text_value[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text_value[start : index + 1]
    return None


def escape_json_control_chars(text_value):
    text_value = text_value or ""
    result = []
    in_string = False
    escaped = False
    for char in text_value:
        if in_string:
            if escaped:
                result.append(char)
                escaped = False
                continue
            if char == "\\":
                result.append(char)
                escaped = True
                continue
            if char == '"':
                result.append(char)
                in_string = False
                continue
            if char == "\n":
                result.append("\\n")
                continue
            if char == "\r":
                result.append("\\r")
                continue
            if char == "\t":
                result.append("\\t")
                continue
        else:
            if char == '"':
                in_string = True
        result.append(char)
    return "".join(result)


def parse_ai_object(content):
    if isinstance(content, dict):
        content.setdefault("reply", "")
        content.setdefault("actions", [])
        return content
    if not isinstance(content, str):
        return None
    candidates = []
    stripped = strip_code_fences(content)
    candidates.append(stripped)
    balanced = extract_balanced_json_object(stripped)
    if balanced and balanced not in candidates:
        candidates.append(balanced)
    for candidate in candidates:
        for variant in (candidate, escape_json_control_chars(candidate)):
            try:
                data = json.loads(variant)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                data.setdefault("reply", "")
                data.setdefault("actions", [])
                return data
    return None


def endpoint(base_url, path):
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def extract_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        numbers = re.findall(r"\d+(?:[.,]\d+)?", value)
        return float(numbers[0].replace(",", ".")) if numbers else None
    return None


def extract_strict_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        text_value = value.strip().replace("\u00a0", " ")
        text_value = re.sub(r"\s+", "", text_value)
        text_value = text_value.replace("₽", "").replace("руб.", "").replace("руб", "")
        text_value = text_value.replace(",", ".")
        if re.fullmatch(r"\d+(?:\.\d+)?", text_value):
            number = float(text_value)
            return number if number > 0 else None
    return None


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def compact_text(text, limit=12000):
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[Текст обрезан приложением из-за лимита модели]"


def summarize_characteristics(text_value, max_lines=3, line_length=95):
    parts = [part.strip(" .;") for part in re.split(r"[.;]\s+", text_value or "") if part.strip()]
    if not parts:
        return ""
    lines = []
    for part in parts:
        if len(part) > line_length:
            part = part[: line_length - 1].rstrip() + "\u2026"
        lines.append(part)
        if len(lines) >= max_lines:
            break
    return "\n".join(lines)


def normalize_quantity(value):
    try:
        quantity = int(round(float(value or 1)))
    except (TypeError, ValueError):
        quantity = 1
    return max(quantity, 1)


def is_numeric_price(value):
    price = extract_strict_price(value)
    return price is not None and price > 0


def normalize_label(value):
    return clean_text(value).lower().replace("\n", " ")


def get_nested(data, paths):
    for path in paths:
        value = data
        for part in path:
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is not None:
            return value
    return None


def normalize_model(model):
    input_price = get_nested(
        model,
        [
            ("pricing", "prompt"),
            ("pricing", "input"),
            ("price", "prompt"),
            ("metadata", "prompt_price"),
            ("metadata", "input_price"),
        ],
    )
    output_price = get_nested(
        model,
        [
            ("pricing", "completion"),
            ("pricing", "output"),
            ("price", "completion"),
            ("metadata", "completion_price"),
            ("metadata", "output_price"),
        ],
    )
    return {
        "id": model.get("id") or model.get("name"),
        "name": model.get("name") or model.get("id"),
        "input_price": extract_price(input_price),
        "output_price": extract_price(output_price),
        "raw_pricing": model.get("pricing") or model.get("price") or model.get("metadata", {}),
    }


def tokenize(text_value):
    return [
        token
        for token in re.findall(r"[a-zа-яё0-9]+", (text_value or "").lower())
        if len(token) >= 3
    ]


def classify_catalog_item(name, source=""):
    text_value = f"{name} {source}".lower()
    name_value = (name or "").lower().strip()
    work_starts = (
        "монтаж ",
        "демонтаж ",
        "прокладка ",
        "установка ",
        "настройка ",
        "подключение ",
        "пусконаладка ",
        "пусконаладочные ",
        "обслуживание ",
    )
    if "работ" in (source or "").lower() or name_value.startswith(work_starts):
        return "work"
    return "equipment"


def default_section_for_type(item_type):
    return "Монтажные работы" if item_type == "work" else "Оборудование"


def http_error_detail(exc, fallback):
    response = getattr(exc, "response", None)
    if response is None:
        return f"{fallback}: {exc}"
    try:
        data = response.json()
        detail = data.get("error", data.get("detail", data))
        if isinstance(detail, dict):
            detail = detail.get("message", json.dumps(detail, ensure_ascii=False))
    except (ValueError, AttributeError):
        detail = response.text
    return f"{fallback}: HTTP {response.status_code}. {str(detail)[:600]}"
