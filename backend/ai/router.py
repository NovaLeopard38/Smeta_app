import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ai.core import (
    append_ai_audit,
    call_ai_object,
    log_ai_command,
    simple_ai_assistant,
)
from ai.smeta_builder import (
    add_installation_works_for_smeta,
    answer_count_question,
    auto_build_project_smeta,
    execute_ai_actions,
    find_work_price,
    infer_smeta_name,
    looks_like_extend_smeta_request,
    looks_like_new_smeta_request,
    resolve_ai_smeta_name,
    should_auto_add_installation,
    should_create_smeta,
    should_validate_smeta,
    smeta_equipment_summary,
    validate_and_fix_smeta,
)
from auth import get_current_user, require_admin_user, require_smeta_access
from config import (
    merged_ai_system_prompt,
    provider_headers,
    public_settings,
    read_settings,
    write_settings,
    DEFAULT_SECTIONS,
    _load_rules,
)
from crud import (
    create_smeta,
    create_smeta_revision,
    get_smeta,
    get_visible_smetas,
    normalize_search_text,
)
from database import engine, get_db
from models import User
from schemas import AiCommandIn, AiSettingsIn, PublicChatIn
from utils.excel import smeta_to_dict
from utils.text_utils import compact_text, endpoint, http_error_detail, normalize_model, normalize_phone, next_client_code

router = APIRouter()

_PUBLIC_CHAT_RL = {}          # phone -> [timestamps]
_PUBLIC_CHAT_WINDOW = 60      # seconds
_PUBLIC_CHAT_LIMIT  = 10      # messages per window


def _rate_limit(key: str) -> bool:
    import time
    now = time.time()
    tracker = _PUBLIC_CHAT_RL.setdefault(key, [])
    tracker[:] = [t for t in tracker if now - t < _PUBLIC_CHAT_WINDOW]
    if len(tracker) >= _PUBLIC_CHAT_LIMIT:
        return False
    tracker.append(now)
    return True



# VSB_BACKEND_RESTORE_V1

# VSB_BACKEND_MEHIST_V1

# VSB_SITE_SETTINGS_V1



@router.get("/settings/ai")
def get_ai_settings(user: User = Depends(get_current_user)):
    require_admin_user(user)
    return public_settings(read_settings())


@router.post("/settings/ai")
def save_ai_settings(payload: AiSettingsIn, user: User = Depends(get_current_user)):
    require_admin_user(user)
    current = read_settings()
    settings = {
        "base_url": payload.base_url.strip().rstrip("/") or "https://api.vsegpt.ru/v1",
        "api_key": payload.api_key.strip() or current.get("api_key", ""),
        "model": payload.model.strip(),
        "assistant_prompt": payload.assistant_prompt.strip(),
    }
    write_settings(settings)
    return public_settings(settings)


@router.get("/settings/ai/models")
def get_ai_models(user: User = Depends(get_current_user)):
    require_admin_user(user)
    settings = read_settings()
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(endpoint(settings["base_url"], "models"), headers=provider_headers(settings))
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_detail(exc, "Не удалось получить список моделей")) from exc

    data = response.json()
    models = data.get("data", data if isinstance(data, list) else [])
    return {"models": [normalize_model(model) for model in models if isinstance(model, dict)]}


@router.post("/ai/recommend")
def ai_recommend(prompt: str = Query(...)):
    settings = read_settings()
    if settings.get("api_key") and settings.get("model"):
        payload = {
            "model": settings["model"],
            "messages": [
                {
                    "role": "system",
                    "content": "Ты помощник сметчика. Отвечай кратко, практично и по-русски.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    endpoint(settings["base_url"], "chat/completions"),
                    headers=provider_headers(settings),
                    json=payload,
                )
                response.raise_for_status()
            recommendation = response.json()["choices"][0]["message"]["content"]
            append_ai_audit(
                "ai_recommend",
                {
                    "prompt": prompt,
                    "provider": settings.get("base_url"),
                    "model": settings.get("model"),
                    "recommendation": recommendation,
                    "mode": "provider",
                },
            )
            return {"recommendation": recommendation}
        except httpx.HTTPError as exc:
            append_ai_audit(
                "ai_recommend",
                {
                    "prompt": prompt,
                    "provider": settings.get("base_url"),
                    "model": settings.get("model"),
                    "error": str(exc),
                    "mode": "provider_error",
                },
            )
            raise HTTPException(status_code=502, detail=http_error_detail(exc, "AI-провайдер отклонил запрос")) from exc
        except (KeyError, IndexError) as exc:
            append_ai_audit(
                "ai_recommend",
                {
                    "prompt": prompt,
                    "provider": settings.get("base_url"),
                    "model": settings.get("model"),
                    "error": str(exc),
                    "mode": "provider_bad_payload",
                },
            )
            raise HTTPException(status_code=502, detail=f"AI-провайдер не ответил корректно: {exc}") from exc
    recommendation = simple_ai_assistant(prompt)
    append_ai_audit(
        "ai_recommend",
        {
            "prompt": prompt,
            "provider": "fallback",
            "model": None,
            "recommendation": recommendation,
            "mode": "local_fallback",
        },
    )
    return {"recommendation": recommendation}


@router.post("/ai/command")
def ai_command(payload: AiCommandIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    selected = get_smeta(db, payload.smeta_id) if payload.smeta_id else None
    new_smeta_request = looks_like_new_smeta_request(payload.prompt)
    if new_smeta_request:
        inferred_name = infer_smeta_name(payload.prompt, "", user)
        name = resolve_ai_smeta_name(db, payload.prompt, inferred_name, user)
        smeta = create_smeta(db, name, {"owner_id": user.id} if user else None)
        build_results = auto_build_project_smeta(db, smeta.id, payload.prompt, user)
        create_smeta_revision(db, get_smeta(db, smeta.id), "create")
        log_ai_command(
            "auto_create",
            user,
            payload.prompt,
            payload=payload.model_dump(),
            reply=f"Создал смету «{name}».",
            results=[f"Создал смету «{name}»", *build_results],
            selected_smeta_id=smeta.id,
            extra={"created_name": name},
        )
        return {
            "reply": f"Создал смету «{name}».",
            "results": [f"Создал смету «{name}»", *build_results],
            "selected_smeta_id": smeta.id,
            "smetas": [smeta_to_dict(smeta) for smeta in get_visible_smetas(db, user)],
        }
    if payload.smeta_id:
        require_smeta_access(db, payload.smeta_id, user)
    if payload.smeta_id and looks_like_extend_smeta_request(payload.prompt):
        require_smeta_access(db, payload.smeta_id, user, write=True)
        smeta = get_smeta(db, payload.smeta_id)
        if not smeta:
            raise HTTPException(status_code=404, detail="Смета не найдена")
        results = auto_build_project_smeta(db, payload.smeta_id, payload.prompt, user)
        create_smeta_revision(db, get_smeta(db, payload.smeta_id), "add item")
        log_ai_command(
            "auto_extend",
            user,
            payload.prompt,
            payload=payload.model_dump(),
            reply="Дополнил смету по вашему запросу.",
            results=results,
            selected_smeta_id=payload.smeta_id,
            extra={"base_smeta_id": payload.smeta_id},
        )
        return {
            "reply": "Дополнил смету по вашему запросу.",
            "results": results,
            "selected_smeta_id": payload.smeta_id,
            "smetas": [smeta_to_dict(smeta) for smeta in get_visible_smetas(db, user)],
        }
    count_answer = answer_count_question(payload.prompt, selected)
    if count_answer:
        log_ai_command(
            "count_question",
            user,
            payload.prompt,
            payload=payload.model_dump(),
            reply=count_answer,
            results=[],
            selected_smeta_id=payload.smeta_id,
        )
        return {
            "reply": count_answer,
            "results": [],
            "selected_smeta_id": payload.smeta_id,
            "smetas": [smeta_to_dict(smeta) for smeta in get_visible_smetas(db, user)],
        }

    if payload.smeta_id and should_validate_smeta(payload.prompt):
        require_smeta_access(db, payload.smeta_id, user, write=True)
        smeta, results = validate_and_fix_smeta(db, payload.smeta_id)
        log_ai_command(
            "validate_smeta",
            user,
            payload.prompt,
            payload=payload.model_dump(),
            reply="Проверил смету по всей структуре: оборудование, монтажные работы и цены из базы.",
            results=results,
            selected_smeta_id=payload.smeta_id,
        )
        return {
            "reply": "Проверил смету по всей структуре: оборудование, монтажные работы и цены из базы.",
            "results": results,
            "selected_smeta_id": payload.smeta_id,
            "smetas": [smeta_to_dict(smeta) for smeta in get_visible_smetas(db, user)],
        }

    if payload.smeta_id and should_auto_add_installation(payload.prompt):
        require_smeta_access(db, payload.smeta_id, user, write=True)
        smeta, results = add_installation_works_for_smeta(db, payload.smeta_id)
        log_ai_command(
            "auto_installation",
            user,
            payload.prompt,
            payload=payload.model_dump(),
            reply="Проверил оборудование в смете и добавил монтажные работы из базы. Если цена не найдена, поставил 0.",
            results=results,
            selected_smeta_id=payload.smeta_id,
        )
        return {
            "reply": "Проверил оборудование в смете и добавил монтажные работы из базы. Если цена не найдена, поставил 0.",
            "results": results,
            "selected_smeta_id": payload.smeta_id,
            "smetas": [smeta_to_dict(smeta) for smeta in get_visible_smetas(db, user)],
        }

    settings = read_settings()
    system_prompt = "\n\n".join(
        [
            merged_ai_system_prompt(settings),
            (
                "Ты управляешь сметным приложением. Верни только JSON-объект без markdown: "
                '{"reply":"короткий ответ пользователю","actions":[...]} . '
                "Разрешенные actions: "
                "create_smeta {name}; delete_smeta {smeta_id}; "
                "add_item {smeta_id, section, name, characteristics, unit, quantity, unit_price, source}; "
                "update_item {smeta_id, item_id, section, name, characteristics, unit, quantity, unit_price, source}; "
                "delete_item {smeta_id, item_id}. "
                f"Допустимые разделы: {', '.join(DEFAULT_SECTIONS)}. "
                "У тебя есть доступ к контексту smetas и work_price_examples в JSON ниже. "
                "Если пользователь просит взять цены из базы, используй work_price_examples. "
                "Если не нашел цену работы, добавь позицию с unit_price 0. "
                "Для вопросов количества используй selected_smeta_equipment_summary. "
                "Синонимы обязательны: камера=видеокамера, регистратор=видеорегистратор/NVR/DVR. "
                "Считай оборудование по всей выбранной смете, а не только по одному разделу. "
                "Если пользователь просит удалить, меняй или удаляй только явно указанную смету или позицию. "
                "Не придумывай цены, если пользователь их не дал."
            ),
        ]
    )
    equipment_names = [
        item.name
        for item in (selected.items if selected else [])
        if (item.section or "") == "Оборудование" or (item.item_type or "") == "equipment"
    ]
    work_examples = []
    for name in equipment_names[:20]:
        work, kind = find_work_price(db, name)
        work_examples.append(
            {
                "equipment": name,
                "kind": kind,
                "work": work.name if work else None,
                "unit": work.unit if work else "шт",
                "price": work.price if work else 0,
                "source": work.source if work else "not_found",
            }
        )
    context = {
        "selected_smeta_id": payload.smeta_id,
        "smetas": [
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
            for smeta in get_visible_smetas(db, user)[:20]
        ],
        "selected_smeta_equipment_summary": smeta_equipment_summary(selected) if selected else {},
        "synonyms": {
            "камера": ["камера", "видеокамера"],
            "регистратор": ["регистратор", "видеорегистратор", "NVR", "DVR"],
        },
        "work_price_examples": work_examples,
        "user_request": payload.prompt,
    }
    decision = call_ai_object(system_prompt, json.dumps(context, ensure_ascii=False))
    actions = decision.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    if not actions and should_create_smeta(payload.prompt):
        actions = [{
            "action": "create_smeta",
            "name": infer_smeta_name(payload.prompt, decision.get("reply") or "", user),
        }]
    selected_smeta_id, results = execute_ai_actions(db, actions, payload.smeta_id, user, payload.prompt)
    log_ai_command(
        "llm_actions",
        user,
        payload.prompt,
        payload=payload.model_dump(),
        reply=decision.get("reply") or "Готово.",
        results=results,
        selected_smeta_id=selected_smeta_id,
        extra={
            "decision": decision,
            "actions": actions,
            "used_fallback_create": bool(not actions and should_create_smeta(payload.prompt)),
        },
    )
    return {
        "reply": decision.get("reply") or "Готово.",
        "results": results,
        "selected_smeta_id": selected_smeta_id,
        "smetas": [smeta_to_dict(smeta) for smeta in get_visible_smetas(db, user)],
    }


@router.post("/ai/public/chat")
def public_ai_chat(body: PublicChatIn):
    # # VSB_AI_PROACTIVE_V1
    phone = normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Сначала введите телефон")
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Пустой запрос")
    if len(msg) > 2000:
        raise HTTPException(status_code=400, detail="Запрос слишком длинный")
    if not _rate_limit(phone):
        raise HTTPException(status_code=429, detail="Слишком много запросов, подождите минуту")

    # Ensure lead exists
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT id, client_code FROM leads WHERE phone = ?", (phone,)).fetchone()
        if not row:
            code = next_client_code(conn)
            conn.exec_driver_sql(
                "INSERT INTO leads (phone, client_code, source_first) VALUES (?, ?, ?)",
                (phone, code, "ai-chat"),
            )
            lead_id = conn.exec_driver_sql("SELECT last_insert_rowid()").fetchone()[0]
        else:
            lead_id, code = row
        conn.exec_driver_sql("UPDATE leads SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (lead_id,))

    # ── Pull recent chat history (last 12 messages) for context continuity ──
    with engine.begin() as conn:
        history_rows = conn.exec_driver_sql(
            "SELECT role, content FROM chat_messages WHERE lead_id = ? ORDER BY id DESC LIMIT 12",
            (lead_id,),
        ).fetchall()
    history_rows = list(reversed(history_rows))  # chronological

    # ── Build catalog context: cheapest items per key category ──
    def _take_cheapest(db, pred_sql, limit=3):
        sql = f"SELECT name, price, COALESCE(unit, '') FROM materials WHERE price > 0 AND ({pred_sql}) ORDER BY price ASC LIMIT {limit}"
        return db.exec_driver_sql(sql).fetchall()

    catalog_lines = []
    with engine.begin() as conn:
        groups = [
            # # VSB_AI_FEATURES_V1
            # ── Feature-aware groups (на основе характеристик из БД) ──
            ("Камеры со слотом SD-карты",
             "name LIKE 'Видеокамер%' AND (lower(characteristics) LIKE '%microsd%' OR lower(characteristics) LIKE '%слот%карт%' OR lower(characteristics) LIKE '%sd-карт%' OR lower(characteristics) LIKE '%sdhc%' OR lower(characteristics) LIKE '%sd card%')"),
            ("Камеры с микрофоном / аудио",
             "name LIKE 'Видеокамер%' AND (lower(characteristics) LIKE '%микрофон%' OR lower(characteristics) LIKE '%аудио%' OR lower(name) LIKE '%mic%')"),
            ("Камеры ColorVu / цветная ночь",
             "name LIKE 'Видеокамер%' AND (lower(characteristics) LIKE '%colorvu%' OR lower(characteristics) LIKE '%цветн%ноч%' OR lower(characteristics) LIKE '%полноцветн%')"),
            ("Камеры с обогревом / морозостойкие",
             "name LIKE 'Видеокамер%' AND (lower(characteristics) LIKE '%обогрев%' OR lower(characteristics) LIKE '%подогрев%' OR lower(characteristics) LIKE '%-50%')"),
            ("Камеры с WDR (контровой свет)",
             "name LIKE 'Видеокамер%' AND lower(characteristics) LIKE '%wdr%'"),
            ("Камеры с PoE",
             "name LIKE 'Видеокамер%' AND (lower(characteristics) LIKE '%poe%' OR lower(name) LIKE '%poe%')"),
            ("Камеры с тревожными входами / I-O",
             "name LIKE 'Видеокамер%' AND (lower(characteristics) LIKE '%тревожн%вход%' OR lower(characteristics) LIKE '%alarm in%')"),
            ("Камеры с большой ИК-подсветкой (≥30 м)",
             "name LIKE 'Видеокамер%' AND (lower(characteristics) LIKE '%до 30м%' OR lower(characteristics) LIKE '%до 40м%' OR lower(characteristics) LIKE '%до 50м%' OR lower(characteristics) LIKE '%до 60м%' OR lower(characteristics) LIKE '%до 80м%')"),
            ("Видеокамеры IP (от дешёвых)",
             "name LIKE 'Видеокамер%' AND lower(name) LIKE '%ip%'"),
            ("Видеокамеры AHD",
             "name LIKE 'Видеокамер%' AND (lower(name) LIKE '%ahd%' OR lower(characteristics) LIKE '%ahd%')"),
            ("Регистраторы IP",
             "(name LIKE 'IP-видеорегистратор%' OR name LIKE 'IP видеорегистратор%')"),
            ("Регистраторы AHD/гибрид",
             "(name LIKE 'AHD-видеорегистратор%' OR name LIKE 'Цифровой%видеорегистратор%')"),
            ("PoE-коммутаторы",
             "name LIKE 'Коммутатор%' AND (lower(name) LIKE '%poe%' OR lower(characteristics) LIKE '%poe%')"),
            ("Кабель UTP (витая пара)",
             "name LIKE 'Кабель%' AND (lower(name) LIKE '%utp%' OR lower(name) LIKE '%u5e%' OR lower(name) LIKE '%4x2%' OR lower(characteristics) LIKE '%итая%')"),
            ("Блоки питания",
             "name LIKE 'Блок питания%'"),
            ("Жёсткие диски",
             "lower(name) LIKE 'hdd%' OR name LIKE '%Жёстк%' OR name LIKE '%жёстк%' OR name LIKE '%Жестк%' OR name LIKE '%жестк%' OR lower(name) LIKE '%seagate%'"),
            ("Считыватели СКУД",
             "name LIKE 'Считыватель%'"),
            ("Электромагнитные замки",
             "name LIKE 'Электромагнитн%замок%'"),
            ("Извещатели охранные",
             "name LIKE 'Извещатель%' OR name LIKE 'Датчик%'"),
        ]
        for label, pred in groups:
            rows = _take_cheapest(conn, pred, limit=3)
            if rows:
                catalog_lines.append(f"  {label}:")
                for r in rows:
                    nm = (r[0] or "")[:70]
                    pr = f"{r[1]:.0f}".replace(".0", "")
                    catalog_lines.append(f"    – {nm} · {pr} ₽" + (f" / {r[2]}" if r[2] else ""))

    catalog_context = "\n".join(catalog_lines)
    works_context = (
        "Стандартные работы по системе видеонаблюдения (фиксированные ставки):\n"
        "  – Монтаж камеры — 2500 ₽/шт\n"
        "  – Монтаж и ПНР видеорегистратора — 3500 ₽/шт\n"
        "  – Монтаж PoE-коммутатора — 1700 ₽/шт\n"
        "  – Прокладка кабеля — 120 ₽/м (норма ~15 м на камеру)\n"
        "  – Настройка удалённого доступа — 2600 ₽\n"
        "  – Монтаж точки СКУД — 4500 ₽/комплект\n"
        "  – Монтаж и ПНР ОС/ОТС — 3500 ₽/извещатель"
    )

    # ── System prompt: proactive ──
    settings = read_settings()
    if body.mode == "support":
        system = (
            "Ты — оператор техподдержки ВСБ39, интегратора систем безопасности в Калининграде. "
            "Отвечай по-русски, дружелюбно, коротко (3-6 предложений), по делу. "
            "Темы: видеонаблюдение, СКУД, ОС/ОТС, обслуживание, ремонт. "
            "Если вопрос требует выезда или сложного расчёта — посоветуй оставить заявку через форму на сайте."
        )
    else:
        system = (
            "Ты — AI-консультант сметчика ВСБ39 (интегратор систем безопасности в Калининграде). "
            "Главное правило: ОТВЕЧАЙ КОНКРЕТНО, С ЦИФРАМИ ИЗ КАТАЛОГА. Не уходи в общие фразы и не задавай "
            "более одного уточняющего вопроса подряд.\n\n"
            "Алгоритм ответа:\n"
            "1. Если клиент спрашивает цену/расчёт — СРАЗУ собери базовое предложение из каталога (ниже) "
            "с реальными ₽ и кратким обоснованием. Используй САМЫЕ ДЕШЁВЫЕ позиции категории как «стартовый "
            "вариант» и обозначь это: «базовый вариант на старте».\n"
            "2. По умолчанию для видеонаблюдения предлагай ip-систему: ip-камера + ip-NVR + PoE-коммутатор + "
            "UTP-кабель ~15 м/камера + работы по таблице ниже. Покажи итог.\n"
            "3. ТОЛЬКО ПОСЛЕ итоговой цифры можно задать ОДИН уточняющий вопрос — например, нужен ли AHD "
            "вместо IP, или другой бюджет, или нужны ли спецфункции (ColorVu, ИК, поворотные).\n"
            "4. Если клиент потом отвечает односложно («да», «нет», «дороже», «дешевле») — продолжай тот же "
            "расчёт с учётом этого ответа, не начинай разговор заново.\n"
            "5. Никогда не пиши «нужно уточнить, какие именно...» без предложения. Сначала вариант, потом "
            "вопрос.\n"
            "6. Округляй цифры до сотен ₽. Используй формат «N × цена ₽ = сумма ₽», в конце «ИТОГО: X ₽».\n"
            "7. Не выдумывай позиции и цены, которых нет в каталоге ниже.\n"
            "7b. ТЕХНОЛОГИЯ КАМЕРЫ И NVR ДОЛЖНЫ СОВПАДАТЬ. AHD/TVI/CVI/CVBS-камеры РАБОТАЮТ ТОЛЬКО с AHD/DVR/гибридными видеорегистраторами. IP-камеры (в названии «IP-…» или с PoE/ONVIF) — ТОЛЬКО с IP-NVR (название «IP-видеорегистратор» / «NVR»). НИКОГДА не комбинируй AHD-камеру с IP-NVR или наоборот — система просто не заработает. «IP67» в характеристиках — это степень защиты, НЕ IP-протокол. # VSB_TECH_MATCH_RULE_V1\n"
            "7a. КАТЕГОРИЧЕСКИ запрещено выдумывать ФУНКЦИИ товара (SD-карта, PoE, ColorVu, WDR, аудио, микрофон, ИК-подсветка дальше N метров, обогрев, антивандальность, мегапиксельность и т.д.). Если пользователь спрашивает про конкретную функцию — ищи в соответствующей фиче-группе каталога ниже. Если в фиче-группе пусто или такой группы нет — отвечай: «В нашем каталоге не нашёл камер с такой функцией. Уточните у менеджера +7 (4012) 55-55-55 — может быть, привезём под заказ». НЕ обещай, что у первой попавшейся камеры есть запрошенная функция.\n"
            "8. Соблюдай правила подбора из руководства ниже. Если каталог не закрывает требуемую позицию (например, нет ИК-извещателей у поставщика Optimus) — честно скажи об этом и предложи позвонить.\n\n"
            "═══ РУКОВОДСТВО ПО ПОДБОРУ (внутренний документ ВСБ39) ═══\n" + _load_rules() + "\n\n"
            "Каталог (актуальные цены, выборка):\n" + catalog_context + "\n\n" + works_context
        )
    if settings.get("assistant_prompt"):
        system = settings["assistant_prompt"] + "\n\n" + system

    # ── Cart context (current) ──
    cart_text = ""
    if isinstance(body.cart, list) and body.cart:
        lines = []
        total = 0.0
        for i, it in enumerate(body.cart[:80], 1):
            try:
                n  = str(it.get("n", ""))[:80]
                u  = str(it.get("u", "шт"))
                q  = float(it.get("q", 0) or 0)
                p  = float(it.get("p", 0) or 0)
                s  = p * q
                total += s
                lines.append(f"{i}. {n} · {q:g} {u} × {p:g} ₽ = {s:g} ₽")
            except Exception:
                pass
        if lines:
            cart_text = "\n\nТекущая смета клиента:\n" + "\n".join(lines) + f"\nИТОГО: {total:g} ₽"

    # ── Save user message immediately ──
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO chat_messages (lead_id, role, content) VALUES (?, 'user', ?)",
            (lead_id, msg),
        )

    # ── Compose messages: system + history + current ──
    messages = [{"role": "system", "content": system}]
    # Limit history to LAST 10 messages, skipping the just-saved user one if present
    for role, content in history_rows[-10:]:
        messages.append({"role": role if role in ("user","assistant") else "user", "content": content[:1500]})
    messages.append({"role": "user", "content": msg + cart_text})

    # ── Call AI ──
    try:
        if not settings.get("api_key"):
            answer = "AI ассистент пока не настроен. Свяжитесь с менеджером: +7 (4012) 55-55-55"
        else:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    endpoint(settings["base_url"], "chat/completions"),
                    headers=provider_headers(settings),
                    json={
                        "model": "openai/gpt-4o-mini",
                        "messages": messages,
                        "max_tokens": 800,
                        "temperature": 0.5,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                answer = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                if not answer:
                    answer = "Не удалось получить ответ от AI. Попробуйте переформулировать."
    except httpx.HTTPError as e:
        answer = f"Ошибка обращения к AI: {e}"
    except Exception as e:
        answer = f"Ошибка: {e}"

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO chat_messages (lead_id, role, content) VALUES (?, 'assistant', ?)",
            (lead_id, answer[:6000]),
        )

    return {
        "client_code": code,
        "answer": answer,
    }

