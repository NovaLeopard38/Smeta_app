import re

from fastapi import HTTPException

from config import DEFAULT_SECTIONS
from crud import (
    add_smeta_item,
    create_material,
    create_smeta,
    delete_smeta,
    delete_smeta_item,
    get_materials,
    get_smeta,
    get_smetas,
    normalize_search_text,
    update_smeta_item,
)
from models import Smeta
from utils.text_utils import (
    classify_catalog_item,
    default_section_for_type,
    normalize_quantity,
    summarize_characteristics,
    tokenize,
)
from utils.excel import (
    smeta_financials,
    smeta_to_dict,
)
from auth import normalized_owner_id, require_smeta_access

DEVICE_SYNONYMS = {
    "камера": ["камера", "камеры", "камеру", "камерой", "видеокамера", "видеокамеры", "видеокамеру"],
    "регистратор": [
        "регистратор",
        "регистратора",
        "регистраторы",
        "видеорегистратор",
        "видеорегистратора",
        "nvr",
        "dvr",
    ],
    "коммутатор": ["коммутатор", "коммутатора", "switch"],
    "турникет": ["турникет", "турникета"],
    "считыватель": ["считыватель", "считывателя"],
    "кнопка выхода": ["кнопка", "кнопки", "кнопка выхода", "выход"],
    "датчик": ["датчик", "датчика", "извещатель", "извещателя"],
    "блок питания": [
        "блок питания",
        "источник питания",
        "источник бесперебойного питания",
        "источника питания",
        "источника бесперебойного питания",
        "ибп",
    ],
    "видеосервер": ["видеосервер", "видеосервера", "сервер"],
    "жесткий диск": ["жд", "hdd", "диск", "жесткий диск", "жёсткий диск"],
    "автоматика ворот": ["ворота", "воротами", "автоматика ворот", "комплект управления воротами"],
    "контроллер скуд": ["контроллер", "скуд", "с2000-2"],
    "преобразователь": ["преобразователь", "rs-485", "rs-232", "ethernet"],
    "замок": ["замок", "электромагнитный замок"],
    "смк": ["смк", "сигнализатор магнитоконтактный"],
    "кронштейн": ["кронштейн", "кронштейна"],
    "кабель": ["кабель", "кабеля"],
    "короб": ["короб", "короба"],
    "гофротруба": ["гофротруба", "гофротрубы", "гофра"],
    "аренда вышки": ["аренда вышки", "вышка"],
}
SYSTEM_DEFINITIONS = {
    "Видеонаблюдение": {"камера", "регистратор", "видеосервер"},
    "СКУД": {
        "турникет",
        "считыватель",
        "кнопка выхода",
        "контроллер скуд",
        "преобразователь",
        "замок",
        "смк",
        "автоматика ворот",
    },
}
COMMISSIONING_TEMPLATE_NAMES = {
    "Видеонаблюдение": "Пусконаладка системы видеонаблюдения",
    "СКУД": "Пусконаладка системы СКУД",
}
WORK_TEMPLATE_NAMES = {
    "камера": "Монтаж камеры",
    "регистратор": "Монтаж видеорегистратора",
    "коммутатор": "Монтаж коммутатора",
    "турникет": "Монтаж турникета",
    "считыватель": "Монтаж считывателя",
    "кнопка выхода": "Монтаж кнопки выхода",
    "датчик": "Монтаж датчика",
    "блок питания": "Монтаж блока питания",
    "видеосервер": "Монтаж видеосервера",
    "жесткий диск": "Монтаж жесткого диска",
    "автоматика ворот": "Монтаж автоматики ворот",
    "контроллер скуд": "Монтаж контроллера СКУД",
    "преобразователь": "Монтаж преобразователя интерфейсов",
    "замок": "Монтаж электромагнитного замка",
    "смк": "Монтаж СМК",
    "кронштейн": "Монтаж кронштейна",
    "кабель": "Прокладка кабеля",
    "короб": "Монтаж короба",
    "гофротруба": "Прокладка гофротрубы",
    "аренда вышки": "Аренда вышки",
}


def smeta_context(db):
    smetas = get_smetas(db)
    return [
        {
            "id": smeta.id,
            "name": smeta.name,
            "total": smeta_to_dict(smeta)["total"],
            "items": [
                {
                    "id": item.id,
                    "item_type": item.item_type,
                    "section": item.section or "Оборудование",
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit": item.unit or "",
                    "unit_price": item.unit_price,
                }
                for item in smeta.items
            ],
        }
        for smeta in smetas[:20]
    ]


def smeta_equipment_summary(smeta):
    summary = {}
    for item in smeta.items:
        if (item.item_type or "") == "work" or (item.section or "") in {"Монтажные работы", "Пусконаладочные работы"}:
            continue
        kind = device_kind(item.name)
        if not kind:
            continue
        if kind not in summary:
            summary[kind] = {"quantity": 0, "items": []}
        summary[kind]["quantity"] += item.quantity or 0
        summary[kind]["items"].append(
            {
                "id": item.id,
                "name": item.name,
                "quantity": item.quantity or 0,
                "section": item.section or "",
            }
        )
    return summary


def is_equipment_smeta_item(item):
    if (item.item_type or "") == "work":
        return False
    if (item.section or "") in {"Монтажные работы", "Пусконаладочные работы"}:
        return False
    return bool(device_kind(item.name))


def answer_count_question(prompt, smeta):
    if not smeta:
        return None
    text_value = (prompt or "").lower()
    if not any(word in text_value for word in ["сколько", "количество", "скока"]):
        return None
    requested_kind = None
    for kind, terms in DEVICE_SYNONYMS.items():
        if any(term in text_value for term in terms):
            requested_kind = kind
            break
    if not requested_kind:
        return None
    summary = smeta_equipment_summary(smeta)
    data = summary.get(requested_kind, {"quantity": 0, "items": []})
    item_text = "; ".join(f"{item['name']} x{item['quantity']:g}" for item in data["items"])
    synonym_note = ""
    if requested_kind == "камера":
        synonym_note = " Камера и видеокамера считаются одним типом."
    elif requested_kind == "регистратор":
        synonym_note = " Регистратор и видеорегистратор считаются одним типом."
    return f"{requested_kind.capitalize()}: {data['quantity']:g} шт.{synonym_note}" + (
        f" Позиции: {item_text}." if item_text else ""
    )


def device_kind(name):
    text_value = (name or "").lower()
    for kind, words in DEVICE_SYNONYMS.items():
        if any(word in text_value for word in words):
            return kind
    tokens = tokenize(name)
    return tokens[0] if tokens else ""


def find_work_price(db, equipment_name):
    kind = device_kind(equipment_name)
    search_terms = DEVICE_SYNONYMS.get(kind, [kind]) if kind else []
    candidate_by_id = {}
    for term in search_terms:
        for work in get_materials(db, term, "work", 80):
            candidate_by_id[work.id] = work
    candidates = list(candidate_by_id.values())
    install_words = ["монтаж", "установка", "прокладка", "подключение"]

    def score(work):
        name = (work.name or "").lower()
        value = 0
        if any(term in name for term in search_terms):
            value += 50
        if any(word in name for word in install_words):
            value += 30
        if name.startswith("монтаж"):
            value += 20
        if "демонтаж" in name:
            value -= 60
        return value

    candidates = sorted(candidates, key=lambda work: (-score(work), work.price or 0))
    if candidates and score(candidates[0]) > 0:
        return candidates[0], kind
    return None, kind


def work_item_data_for_equipment(db, equipment_name, equipment_quantity=1, equipment_names=None):
    work, kind = find_work_price(db, equipment_name)
    quantity = normalize_quantity(equipment_quantity)
    related_names = equipment_names or equipment_name
    if work:
        return {
            "item_type": "work",
            "section": "Монтажные работы",
            "name": work.name,
            "characteristics": f"Для: {related_names}",
            "unit": work.unit or "шт",
            "quantity": quantity,
            "unit_price": work.price,
            "source": work.source or "База работ",
        }, kind, True
    fallback_name = WORK_TEMPLATE_NAMES.get(kind, f"Монтаж {kind or equipment_name}")
    return {
        "item_type": "work",
        "section": "Монтажные работы",
        "name": fallback_name,
        "characteristics": f"Цена не найдена. Для: {related_names}",
        "unit": "шт",
        "quantity": quantity,
        "unit_price": 0,
        "source": "Нет цены в базе работ",
    }, kind, False


def remember_work_price_from_smeta(db, work_item):
    if not work_item or (work_item.unit_price or 0) <= 0:
        return None
    kind = work_kind(work_item)
    name = WORK_TEMPLATE_NAMES.get(kind, work_item.name or f"Монтаж {kind}")
    if not name:
        return None
    existing, _ = find_work_price(db, name)
    if existing:
        existing.price = float(work_item.unit_price or 0)
        existing.unit = work_item.unit or existing.unit or "шт"
        existing.source = work_item.source or existing.source or "Из сметы"
        if work_item.characteristics and not existing.characteristics:
            existing.characteristics = work_item.characteristics
        db.commit()
        db.refresh(existing)
        return existing
    return create_material(
        db,
        name,
        work_item.unit or "шт",
        float(work_item.unit_price or 0),
        work_item.source or "Из сметы",
        work_item.characteristics or "",
        "work",
    )


def is_commissioning_item(item):
    text_value = f"{item.name or ''} {item.characteristics or ''}".lower()
    return (item.section or "") == "Пусконаладочные работы" or "пусконалад" in text_value


def detected_system_names(equipment_by_kind):
    systems = []
    kinds = set(equipment_by_kind.keys())
    for system_name, system_kinds in SYSTEM_DEFINITIONS.items():
        if kinds & system_kinds:
            systems.append(system_name)
    return systems


def commissioning_system_from_item(item):
    text_value = f"{item.name or ''} {item.characteristics or ''}".lower()
    if any(word in text_value for word in ["видеонаб", "камера", "видеокамера", "регистратор", "видеосервер"]):
        return "Видеонаблюдение"
    if any(word in text_value for word in ["скуд", "считыватель", "контроллер", "замок", "смк", "турникет"]):
        return "СКУД"
    return ""


def find_commissioning_price(db, system_name=None):
    candidates = []
    system_queries = []
    if system_name:
        system_queries = [system_name, COMMISSIONING_TEMPLATE_NAMES.get(system_name, "")]
    for query in ["пусконаладочные работы", "пусконаладка", "пнр", *system_queries]:
        candidates.extend(get_materials(db, query, "work", 20))
    system_terms = {
        "Видеонаблюдение": ["видеонаб", "камера", "видеокамера", "регистратор"],
        "СКУД": ["скуд", "считыватель", "контроллер", "замок"],
    }.get(system_name, [])

    def score(work):
        name = (work.name or "").lower()
        characteristics = (work.characteristics or "").lower()
        text_value = f"{name} {characteristics}"
        has_commissioning_word = "пусконалад" in text_value or "пнр" in text_value
        if not has_commissioning_word:
            return -100
        if system_terms and not any(term in text_value for term in system_terms):
            return -100
        value = 0
        if has_commissioning_word:
            value += 80
        if name.startswith("пусконалад"):
            value += 30
        if "работ" in text_value:
            value += 10
        if system_terms and any(term in text_value for term in system_terms):
            value += 60
        return value

    candidates = sorted({work.id: work for work in candidates}.values(), key=lambda work: (-score(work), work.price or 0))
    if candidates and score(candidates[0]) > 0:
        return candidates[0]
    return None


def find_work_price_by_query(db, query_text, required_terms=None):
    required_terms = required_terms or []
    candidates = get_materials(db, query_text, "work", 80)

    def score(work):
        name = (work.name or "").lower()
        characteristics = (work.characteristics or "").lower()
        text_value = f"{name} {characteristics}"
        value = 0
        if query_text and query_text.lower() in text_value:
            value += 80
        if any(term in text_value for term in required_terms):
            value += 70
        if name.startswith("настройка") or name.startswith("пусконалад"):
            value += 20
        if "доступ" in text_value:
            value += 25
        if "удален" in text_value:
            value += 25
        if "монтаж" in text_value:
            value -= 10
        return value

    candidates = sorted({work.id: work for work in candidates}.values(), key=lambda work: (-score(work), work.price or 0))
    if candidates and score(candidates[0]) > 0:
        return candidates[0]
    return None


def remember_commissioning_price_from_smeta(db, commissioning_item, system_name=None):
    if not commissioning_item or (commissioning_item.unit_price or 0) <= 0:
        return None
    existing = find_commissioning_price(db, system_name)
    name = COMMISSIONING_TEMPLATE_NAMES.get(system_name) or commissioning_item.name or "Пусконаладочные работы"
    if existing:
        existing.price = float(commissioning_item.unit_price or 0)
        existing.unit = commissioning_item.unit or existing.unit or "компл"
        existing.source = commissioning_item.source or existing.source or "Из сметы"
        if commissioning_item.characteristics and not existing.characteristics:
            existing.characteristics = commissioning_item.characteristics
        db.commit()
        db.refresh(existing)
        return existing
    return create_material(
        db,
        name,
        commissioning_item.unit or "компл",
        float(commissioning_item.unit_price or 0),
        commissioning_item.source or "Из сметы",
        commissioning_item.characteristics or "",
        "work",
    )


def ensure_commissioning_for_smeta(db, smeta_id, smeta, equipment_by_kind):
    systems = detected_system_names(equipment_by_kind)
    if not systems:
        systems = []

    results = []
    commissioning_items = [item for item in smeta.items if is_commissioning_item(item)]
    items_by_system = {}
    generic_items = []
    for item in commissioning_items:
        system_name = commissioning_system_from_item(item)
        if system_name:
            items_by_system.setdefault(system_name, []).append(item)
        else:
            generic_items.append(item)

    for system_name in systems:
        existing_items = items_by_system.get(system_name) or []
        primary = existing_items[0] if existing_items else (generic_items.pop(0) if generic_items else None)
        template = find_commissioning_price(db, system_name)
        primary_name = (primary.name or "").lower() if primary else ""
        primary_is_commissioning = "пусконалад" in primary_name or "пнр" in primary_name
        remembered = remember_commissioning_price_from_smeta(db, primary, system_name) if primary and primary_is_commissioning else None
        primary_name_has_system = any(
            term in primary_name
            for term in {
                "Видеонаблюдение": ["видеонаб", "камера", "видеокамера", "регистратор"],
                "СКУД": ["скуд", "считыватель", "контроллер", "замок"],
            }.get(system_name, [])
        )
        name = (
            primary.name
            if primary and commissioning_system_from_item(primary) and primary_is_commissioning and primary_name_has_system
            else (remembered.name if remembered else (template.name if template else COMMISSIONING_TEMPLATE_NAMES[system_name]))
        )
        unit = primary.unit if primary and primary.unit else (remembered.unit if remembered else (template.unit if template else "компл"))
        unit_price = (
            primary.unit_price
            if primary and primary_is_commissioning and (primary.unit_price or 0) > 0
            else (remembered.price if remembered else (template.price if template else 0))
        )
        source = (
            primary.source
            if primary and primary.source
            else (remembered.source if remembered else (template.source if template else "Нет цены в базе работ"))
        )
        item_data = {
            "item_type": "work",
            "section": "Пусконаладочные работы",
            "name": name,
            "characteristics": f"Система: {system_name}",
            "unit": unit,
            "quantity": 1,
            "unit_price": unit_price,
            "source": source,
        }
        if primary:
            update_smeta_item(
                db,
                smeta_id,
                primary.id,
                item_data,
            )
            results.append(f"Пусконаладка «{system_name}» уже есть, цена {unit_price}")
        else:
            add_smeta_item(db, smeta_id, item_data)
            results.append(f"Добавил пусконаладку «{system_name}» по {unit_price}")

        for duplicate in existing_items[1:]:
            delete_smeta_item(db, smeta_id, duplicate.id)
            results.append(f"Удалил дублирующую пусконаладку «{duplicate.name}»")

    for item in generic_items:
        if (item.unit_price or 0) <= 0:
            delete_smeta_item(db, smeta_id, item.id)
            results.append(f"Удалил лишнюю общую пусконаладку «{item.name}»")

    return results


def work_matches_equipment(work_item, equipment):
    kind = device_kind(equipment.name)
    if not kind:
        return False
    terms = DEVICE_SYNONYMS.get(kind, [kind])
    haystack = f"{work_item.name or ''} {work_item.characteristics or ''}".lower()
    if any(term in haystack for term in terms):
        return True
    return (equipment.name or "").lower() in haystack


def work_kind(item):
    text_value = f"{item.name or ''} {item.characteristics or ''}".lower()
    for kind, terms in DEVICE_SYNONYMS.items():
        if any(term in text_value for term in terms):
            return kind
    return device_kind(item.name)


def has_matching_work(items, equipment):
    equipment_kind = device_kind(equipment.name)
    for item in items:
        if (item.section or "") != "Монтажные работы":
            continue
        name = (item.name or "").lower()
        if work_kind(item) == equipment_kind:
            return True
        if work_matches_equipment(item, equipment) and any(
            word in name for word in ["монтаж", "установка", "прокладка", "подключение"]
        ):
            return True
    return False


def validate_and_fix_smeta(db, smeta_id):
    smeta = get_smeta(db, smeta_id)
    if not smeta:
        return None, ["Смета не найдена"]
    results = []
    equipment_items = [item for item in smeta.items if is_equipment_smeta_item(item)]
    work_items = [item for item in smeta.items if (item.section or "") == "Монтажные работы"]

    summary = smeta_equipment_summary(smeta)
    if summary:
        counts = ", ".join(f"{kind}: {data['quantity']:g}" for kind, data in summary.items())
        results.append(f"Оборудование по всей смете: {counts}")

    equipment_by_kind = {}
    for equipment in equipment_items:
        kind = device_kind(equipment.name)
        if not kind:
            continue
        bucket = equipment_by_kind.setdefault(kind, {"quantity": 0, "items": []})
        bucket["quantity"] += equipment.quantity or 0
        bucket["items"].append(equipment)

    for kind, data_by_kind in equipment_by_kind.items():
        quantity = data_by_kind["quantity"] or 1
        sample_equipment = data_by_kind["items"][0]
        item_data, _, found_price = work_item_data_for_equipment(
            db,
            sample_equipment.name,
            quantity,
            ", ".join(item.name for item in data_by_kind["items"]),
        )
        matching_items = [item for item in work_items if work_kind(item) == kind]

        if matching_items:
            primary = matching_items[0]
            if not found_price and (primary.unit_price or 0) > 0:
                remembered = remember_work_price_from_smeta(db, primary)
                item_data["name"] = remembered.name if remembered else item_data["name"]
                item_data["unit"] = remembered.unit if remembered else (primary.unit or item_data["unit"])
                item_data["unit_price"] = remembered.price if remembered else primary.unit_price
                item_data["source"] = remembered.source if remembered else (primary.source or "Ручная цена")
                if remembered:
                    results.append(f"Сохранил «{remembered.name}» в базе работ по цене {remembered.price}")
            update_data = {
                "item_type": "work",
                "section": "Монтажные работы",
                "name": item_data["name"],
                "characteristics": item_data["characteristics"],
                "unit": item_data["unit"],
                "quantity": item_data["quantity"],
                "unit_price": item_data["unit_price"],
                "source": item_data["source"],
            }
            update_smeta_item(db, smeta_id, primary.id, update_data)
            for duplicate in matching_items[1:]:
                delete_smeta_item(db, smeta_id, duplicate.id)
                results.append(f"Удалил дублирующий монтаж «{duplicate.name}»")
            price_text = update_data["unit_price"]
            results.append(f"Привёл монтаж типа «{kind}» к количеству {quantity:g} по цене {price_text}")
        else:
            if found_price:
                results.append(
                    f"Добавил «{item_data['name']}» для типа «{kind}» количеством {quantity:g} по {item_data['unit_price']}"
                )
            else:
                results.append(f"Добавил монтаж типа «{kind}» количеством {quantity:g} с ценой 0")
            add_smeta_item(db, smeta_id, item_data)

    smeta = get_smeta(db, smeta_id)
    results.extend(ensure_commissioning_for_smeta(db, smeta_id, smeta, equipment_by_kind))
    return get_smeta(db, smeta_id), results or ["Ошибок не найдено"]


def add_installation_works_for_smeta(db, smeta_id):
    smeta = get_smeta(db, smeta_id)
    if not smeta:
        return None, ["Смета не найдена"]
    results = []
    equipment_items = [item for item in smeta.items if is_equipment_smeta_item(item)]
    if not equipment_items:
        return smeta, ["В смете нет оборудования, для которого можно добавить монтаж"]

    for equipment in equipment_items:
        if has_matching_work(smeta.items, equipment):
            results.append(f"Монтаж для «{equipment.name}» уже есть")
            continue
        work, kind = find_work_price(db, equipment.name)
        quantity = equipment.quantity or 1
        if work:
            item_data = {
                "item_type": "work",
                "section": "Монтажные работы",
                "name": work.name,
                "characteristics": f"Для: {equipment.name}",
                "unit": work.unit or "шт",
                "quantity": quantity,
                "unit_price": work.price,
                "source": work.source or "База работ",
            }
            add_smeta_item(db, smeta_id, item_data)
            results.append(f"Добавил «{work.name}» для «{equipment.name}» по {work.price}")
        else:
            fallback_name = f"Монтаж {kind or equipment.name}"
            item_data = {
                "item_type": "work",
                "section": "Монтажные работы",
                "name": fallback_name,
                "characteristics": f"Цена не найдена. Для: {equipment.name}",
                "unit": equipment.unit or "шт",
                "quantity": quantity,
                "unit_price": 0,
                "source": "Нет цены в базе работ",
            }
            add_smeta_item(db, smeta_id, item_data)
            results.append(f"Добавил «{fallback_name}» с ценой 0")
    return get_smeta(db, smeta_id), results


def should_auto_add_installation(prompt):
    text_value = (prompt or "").lower()
    return (
        any(word in text_value for word in ["монтаж", "установлено", "установить", "установка"])
        and any(word in text_value for word in ["кажд", "устрой", "оборуд", "позици"])
    )


def should_validate_smeta(prompt):
    text_value = (prompt or "").lower()
    return "смет" in text_value and any(word in text_value for word in ["проверь", "исправ", "почин", "провер"])


def looks_like_new_smeta_request(prompt):
    text_value = normalize_search_text(prompt or "")
    if not text_value:
        return False
    negative_words = [
        "проверь",
        "проверить",
        "исправ",
        "почин",
        "удали",
        "откати",
        "посмотри",
        "посмотреть",
        "сравни",
        "сравнить",
    ]
    if any(word in text_value for word in negative_words):
        return False
    creation_words = [
        "создай",
        "создать",
        "создайте",
        "сделай",
        "сделать",
        "нужно",
        "надо",
        "требуется",
        "хочу",
        "установ",
        "смонтир",
        "подобрать",
        "рассчитать",
        "собери",
        "собрать",
        "спроектир",
    ]
    project_words = [
        "смет",
        "объект",
        "видеонаб",
        "камер",
        "видеокамер",
        "регистрат",
        "nvr",
        "dvr",
        "скуд",
        "считывател",
        "контроллер",
        "замок",
        "турникет",
        "ибп",
        "жд",
        "hdd",
        "жестк",
        "кабель",
        "монтаж",
        "пусконалад",
    ]
    has_creation = any(word in text_value for word in creation_words)
    has_project = any(word in text_value for word in project_words)
    return has_creation and has_project


def looks_like_extend_smeta_request(prompt):
    text_value = normalize_search_text(prompt or "")
    if not text_value:
        return False
    negative_words = [
        "проверь",
        "проверить",
        "исправ",
        "почин",
        "удали",
        "откати",
        "посмотри",
        "посмотреть",
        "сравни",
        "сравнить",
        "создай",
        "создать",
        "создайте",
    ]
    if any(word in text_value for word in negative_words):
        return False
    add_words = [
        "добавь",
        "добавить",
        "дополни",
        "дополнить",
        "ещё",
        "еще",
        "плюс",
        "впиши",
        "вставь",
        "увеличь",
        "увеличить",
        "докинь",
    ]
    project_words = [
        "камер",
        "видеокамер",
        "регистрат",
        "видеонаб",
        "nvr",
        "dvr",
        "скуд",
        "считывател",
        "контроллер",
        "замок",
        "турникет",
        "ибп",
        "жд",
        "hdd",
        "кабель",
        "монтаж",
        "пусконалад",
        "коммутатор",
    ]
    return any(word in text_value for word in add_words) and any(word in text_value for word in project_words)


def auto_smeta_prefix(user):
    local_part = str(getattr(user, "email", "") or "dboy").split("@", 1)[0] or "dboy"
    safe = re.sub(r"[^0-9a-zA-Zа-яА-Я]+", "_", local_part).strip("_").lower()
    return safe or "dboy"


def next_auto_smeta_name(db, user):
    prefix = auto_smeta_prefix(user)
    pattern = f"{prefix}_auto_%"
    existing_names = [
        name[0]
        for name in db.query(Smeta.name).filter(Smeta.name.like(pattern)).all()
        if name and name[0]
    ]
    highest = 0
    prefix_token = f"{prefix}_auto_"
    for existing in existing_names:
        suffix = existing[len(prefix_token) :]
        match = re.match(r"(\d+)", suffix)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}_auto_{highest + 1}"


def prompt_requests_named_smeta(prompt):
    text_value = normalize_search_text(prompt or "")
    if not text_value:
        return False
    explicit_markers = [
        "назови",
        "назвать",
        "название",
        "под названием",
        "с названием",
        "имя сметы",
        "как назвать",
        "именуй",
    ]
    return any(marker in text_value for marker in explicit_markers)


def resolve_ai_smeta_name(db, prompt, raw_name, user):
    fallback_name = str(getattr(user, "email", "") or "Новая смета").split("@", 1)[0] or "Новая смета"
    candidate = sanitize_smeta_name(raw_name or "", prompt, user)
    if prompt_requests_named_smeta(prompt) and candidate and candidate != fallback_name:
        return candidate
    return next_auto_smeta_name(db, user)


def smeta_has_ip_cameras(db, smeta_id):
    smeta = get_smeta(db, smeta_id)
    if not smeta:
        return False
    for item in getattr(smeta, "items", []) or []:
        if item.item_type and item.item_type != "equipment":
            continue
        name_text = normalize_search_text(item.name or "")
        characteristics_text = normalize_search_text(item.characteristics or "")
        if "ip" in name_text and ("камер" in name_text or "видеокамер" in name_text):
            return True
        if "ip" in characteristics_text and ("камер" in characteristics_text or "видеокамер" in characteristics_text):
            return True
    return False


def auto_build_project_smeta(db, smeta_id, prompt, user=None):
    text_value = (prompt or "").lower()
    results = []
    requests = []
    ip_context = "ip" in text_value or "ип" in text_value or smeta_has_ip_cameras(db, smeta_id)

    def add_request(query, quantity, label):
        requests.append({"query": query, "quantity": quantity, "label": label})

    def quantity_before(pattern, default=1):
        match = re.search(rf"(?:(\d+)\s*[xх]\s*)?(?:{pattern})", text_value)
        if match and match.group(1):
            return normalize_quantity(match.group(1))
        match = re.search(rf"(?:{pattern})\s*(\d+)\s*[xх]?", text_value)
        if match and match.group(1):
            return normalize_quantity(match.group(1))
        return default

    camera_match = re.search(r"(?:(\d+)\s*)?(?:ip|ип)?\s*(?:камер[аы]?|видеокамер[аы]?)", text_value)
    if camera_match:
        camera_qty = normalize_quantity(camera_match.group(1) or 1)
        camera_query = "ip камера"
        mp_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:mp|мп|vg)", text_value)
        if mp_match:
            camera_query += f" {mp_match.group(1).replace(',', '.')} мп"
        add_request(camera_query, camera_qty, "камер")

    recorder_match = re.search(r"(?:(\d+)\s*)?(?:видеорегистратор|регистратор|nvr|dvr)", text_value)
    if recorder_match:
        recorder_qty = normalize_quantity(recorder_match.group(1) or 1)
        recorder_query = "ip видеорегистратор" if ip_context else "видеорегистратор"
        if "poe" in text_value or "пое" in text_value:
            recorder_query += " poe"
        add_request(recorder_query, recorder_qty, "видеорегистратора")

    hdd_match = re.search(r"(?:жд|hdd|жестк[а-я ]*диск[а-я ]*)(?:\s*(\d+(?:[.,]\d+)?))?\s*(?:тб|tb)", text_value)
    if hdd_match or any(term in text_value for term in ["жд", "hdd", "жесткий диск", "жёсткий диск"]):
        size_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:тб|tb)", text_value)
        hdd_query = "жесткий диск"
        if size_match:
            hdd_query += f" {size_match.group(1).replace(',', '.')} тб"
        add_request(hdd_query, 1, "жесткого диска")

    cable_match = re.search(r"(?:кабель|кабел[ья])\s*(\d+(?:[.,]\d+)?)?\s*(?:м|метр[а-я]*)?", text_value)
    cable_qty_match = cable_match.group(1) if cable_match else None
    if not cable_qty_match:
        cable_qty_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:м|метр[а-я]*)\s*(?:кабель|кабел[ья])", text_value)
        cable_qty_match = cable_qty_match.group(1) if cable_qty_match else None
    if cable_match or any(term in text_value for term in ["кабель", "кабеля", "кабелем"]):
        cable_qty = normalize_quantity(cable_qty_match or 1)
        cable_query = "кабель"
        if "витая пара" in text_value or "utp" in text_value:
            cable_query = "кабель витая пара"
        elif "силов" in text_value:
            cable_query = "кабель силовой"
        elif "гофр" in text_value:
            cable_query = "гофротруба"
        add_request(cable_query, cable_qty, "кабеля")

    ups_match = re.search(
        r"(?:(\d+)\s*)?(?:ибп|ups|источник(?:а|ов)?\s+бесперебойного\s+питания|источн[а-я ]*питани[яе]|блок питания)",
        text_value,
    )
    if ups_match or any(term in text_value for term in ["ибп", "ups", "источник бесперебойного питания", "блок питания"]):
        ups_qty = normalize_quantity(ups_match.group(1) or 1) if ups_match else 1
        add_request("ибп", ups_qty, "ИБП")

    switch_match = re.search(r"(?:коммутатор|switch)(?:\s*(\d+)\s*порто?)?", text_value)
    if switch_match or any(term in text_value for term in ["коммутатор", "switch"]):
        switch_qty = normalize_quantity(1)
        switch_query = "коммутатор"
        ports_match = re.search(r"(\d+)\s*порто", text_value)
        if ports_match:
            switch_query += f" {ports_match.group(1)} порт"
        if "poe" in text_value or "пое" in text_value:
            switch_query += " poe"
        add_request(switch_query, switch_qty, "коммутатора")

    controller_terms = r"(?:c2000-2|с2000-2|контроллер(?:а|ов|ы)?(?:\s+скуд)?|скуд)"
    if re.search(controller_terms, text_value):
        controller_qty = quantity_before(controller_terms, 1)
        add_request("c2000-2", controller_qty, "контроллера СКУД")

    reader_terms = r"(?:считывател[ьяеи]?|ридер[аы]?|reader[а-я ]*)"
    if re.search(reader_terms, text_value):
        reader_qty = quantity_before(reader_terms, 1)
        add_request("считыватель", reader_qty, "считывателя")

    lock_terms = r"(?:замок[а-я ]*|электромагнитн[а-я ]*замок[а-я ]*)"
    if re.search(lock_terms, text_value):
        lock_qty = quantity_before(lock_terms, 1)
        add_request("замок", lock_qty, "замка")

    exit_button_terms = r"(?:кнопк[а-я ]*выход[а-я ]*|выход)"
    if re.search(exit_button_terms, text_value) and "кнопк" in text_value:
        button_qty = quantity_before(exit_button_terms, 1)
        add_request("кнопка выхода", button_qty, "кнопки выхода")

    seen = set()
    for request in requests:
        key = (request["query"], request["quantity"])
        if key in seen:
            continue
        seen.add(key)
        materials = get_materials(db, request["query"], "equipment", 10)
        material = materials[0] if materials else None
        if material:
            item_data = {
                "item_type": material.item_type or "equipment",
                "section": default_section_for_type(material.item_type or "equipment"),
                "name": material.name,
                "characteristics": summarize_characteristics(material.characteristics or ""),
                "unit": material.unit or "",
                "quantity": request["quantity"],
                "unit_price": material.price,
                "source": material.source or "База материалов",
            }
            add_smeta_item(db, smeta_id, item_data)
            results.append(f"Добавил {request['label']} «{material.name}» x{request['quantity']}")
        else:
            item_data = {
                "item_type": "equipment",
                "section": "Оборудование",
                "name": request["query"],
                "characteristics": "Цена не найдена в базе.",
                "unit": "шт",
                "quantity": request["quantity"],
                "unit_price": 0,
                "source": "Нет цены в базе",
            }
            add_smeta_item(db, smeta_id, item_data)
            results.append(f"Добавил {request['label']} «{request['query']}» x{request['quantity']} с ценой 0")

    if requests:
        validate_and_fix_smeta(db, smeta_id)
    return results


def should_create_smeta(prompt):
    return looks_like_new_smeta_request(prompt)


def infer_smeta_name(prompt, reply, user=None):
    text_sources = [prompt or ""]
    fallback_name = str(getattr(user, "email", "") or "Новая смета").split("@", 1)[0] or "Новая смета"
    patterns = [
        r"смет[ауеы]?\s*(?:создан[аоы]?|готов[аоы]?|назов[иите]?|под названием)\s*[«\"']?([^\\n\\r\"'«»]+)",
        r"создай(?:те)?\s+смет[ауеы]?\s*(?:на|для)?\s*[«\"']?([^\\n\\r\"'«»]+)",
        r"смет[ауеы]?\s*(?:на|для)\s*[«\"']?([^\\n\\r\"'«»]+)",
    ]
    project_words = [
        "камер",
        "видеокамер",
        "регистрат",
        "видеонаб",
        "nvr",
        "dvr",
        "скуд",
        "считывател",
        "контроллер",
        "замок",
        "турникет",
        "ибп",
        "жд",
        "hdd",
        "кабель",
        "монтаж",
        "пусконалад",
        "коммутатор",
    ]

    def looks_like_title(candidate):
        normalized = normalize_search_text(candidate)
        if not normalized:
            return False
        if len(candidate.split()) > 8:
            return False
        if candidate.count(",") >= 1:
            return False
        if any(char.isdigit() for char in candidate) and any(word in normalized for word in project_words):
            return False
        if any(word in normalized for word in project_words):
            return False
        return True

    for text in text_sources:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                name = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;\"'«»")
                if name and name.lower() not in {"без названия", "без имени", "новая", "новую", "новая смета", "смета"} and looks_like_title(name):
                    return name[:80]
    return fallback_name


def sanitize_smeta_name(name, prompt=None, user=None):
    candidate = re.sub(r"\s+", " ", str(name or "")).strip(" .,:;\"'«»")
    if candidate:
        normalized = normalize_search_text(candidate)
        if len(candidate.split()) <= 8 and candidate.count(",") == 0:
            if not any(char.isdigit() for char in candidate):
                if not any(word in normalized for word in [
                    "камер",
                    "видеокамер",
                    "регистрат",
                    "видеонаб",
                    "nvr",
                    "dvr",
                    "скуд",
                    "считывател",
                    "контроллер",
                    "замок",
                    "турникет",
                    "ибп",
                    "жд",
                    "hdd",
                    "кабель",
                    "монтаж",
                    "пусконалад",
                    "коммутатор",
                ]):
                    return candidate[:80]
    inferred = infer_smeta_name(prompt or "", "", user)
    inferred = re.sub(r"\s+", " ", inferred).strip(" .,:;\"'«»")
    if inferred:
        return inferred[:80]
    return str(getattr(user, "email", "") or "Новая смета").split("@", 1)[0] or "Новая смета"


def execute_ai_actions(db, actions, fallback_smeta_id=None, user=None, prompt_text=""):
    results = []
    selected_smeta_id = fallback_smeta_id
    active_smeta_id = fallback_smeta_id
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = action.get("action")
        if not action_type:
            continue
        if action_type == "create_smeta":
            name = resolve_ai_smeta_name(db, prompt_text, action.get("name"), user)
            smeta = create_smeta(db, name, {"owner_id": user.id} if user else None)
            selected_smeta_id = smeta.id
            active_smeta_id = smeta.id
            results.append(f"Создал смету «{name}»")
            if prompt_text and looks_like_new_smeta_request(prompt_text):
                build_results = auto_build_project_smeta(db, smeta.id, prompt_text, user)
                results.extend(build_results)
        elif action_type == "delete_smeta":
            smeta_id = int(action.get("smeta_id") or active_smeta_id or selected_smeta_id or 0)
            smeta = get_smeta(db, smeta_id)
            if user:
                require_smeta_access(db, smeta_id, user, write=True)
                if not user.is_admin and smeta and normalized_owner_id(smeta) != user.id:
                    results.append("Не удалил смету: удалять может только владелец")
                    continue
            if smeta and delete_smeta(db, smeta_id):
                results.append(f"Удалил смету «{smeta.name}»")
                if selected_smeta_id == smeta_id:
                    selected_smeta_id = None
            else:
                results.append("Не удалил смету: она не найдена")
        elif action_type == "add_item":
            smeta_id = int(action.get("smeta_id") or active_smeta_id or selected_smeta_id or 0)
            if active_smeta_id and not fallback_smeta_id:
                smeta_id = active_smeta_id
            if user:
                require_smeta_access(db, smeta_id, user, write=True)
            if not get_smeta(db, smeta_id):
                results.append("Не добавил позицию: смета не найдена")
                continue
            item_data = {
                "item_type": str(action.get("item_type") or "manual"),
                "section": str(action.get("section") or "Прочее"),
                "name": str(action.get("name") or "").strip(),
                "characteristics": str(action.get("characteristics") or "").strip(),
                "unit": str(action.get("unit") or "").strip(),
                "quantity": normalize_quantity(action.get("quantity") or 1),
                "unit_price": float(action.get("unit_price") or action.get("price") or 0),
                "source": str(action.get("source") or "AI").strip(),
            }
            if not item_data["name"]:
                results.append("Не добавил позицию: нет названия")
                continue
            add_smeta_item(db, smeta_id, item_data)
            results.append(f"Добавил позицию «{item_data['name']}»")
        elif action_type == "update_item":
            smeta_id = int(action.get("smeta_id") or active_smeta_id or selected_smeta_id or 0)
            if active_smeta_id and not fallback_smeta_id:
                smeta_id = active_smeta_id
            item_id = int(action.get("item_id") or 0)
            if user:
                require_smeta_access(db, smeta_id, user, write=True)
            data = {
                key: action.get(key)
                for key in ["item_type", "section", "name", "characteristics", "unit", "quantity", "unit_price", "source"]
                if key in action
            }
            if "quantity" in data:
                data["quantity"] = normalize_quantity(data["quantity"])
            if "unit_price" in data:
                data["unit_price"] = float(data["unit_price"])
            if update_smeta_item(db, smeta_id, item_id, data):
                results.append(f"Обновил позицию #{item_id}")
            else:
                results.append("Не обновил позицию: она не найдена")
        elif action_type == "delete_item":
            smeta_id = int(action.get("smeta_id") or active_smeta_id or selected_smeta_id or 0)
            if active_smeta_id and not fallback_smeta_id:
                smeta_id = active_smeta_id
            item_id = int(action.get("item_id") or 0)
            if user:
                require_smeta_access(db, smeta_id, user, write=True)
            if delete_smeta_item(db, smeta_id, item_id):
                results.append(f"Удалил позицию #{item_id}")
            else:
                results.append("Не удалил позицию: она не найдена")
        elif action_type not in {"noop", "none"}:
            results.append(f"Пропустил неизвестное действие: {action_type}")
    return selected_smeta_id, results
