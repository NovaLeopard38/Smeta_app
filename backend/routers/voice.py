import base64
import hashlib
import hmac
import json
import struct
import time

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response as _FastResponse

from auth import get_current_user, require_admin_user
from config import read_settings, provider_headers
from database import engine
from models import User
from routers.leads import normalize_phone, _next_client_code
from schemas import CallEndIn, CallStartIn, CallTurnIn, TTSIn, VoiceDialogIn
from utils.text_utils import endpoint

router = APIRouter()

def _ensure_voice_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS voice_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_call_id TEXT UNIQUE,
                lead_id INTEGER,
                direction TEXT NOT NULL DEFAULT 'in',
                phone TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                duration_sec INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                recording_url TEXT,
                summary TEXT,
                category TEXT,
                manager_status TEXT DEFAULT 'new',
                raw_payload TEXT DEFAULT '{}'
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS voice_dialog_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                turn_no INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_turns_call ON voice_dialog_turns(call_id)")


_ensure_voice_schema()


def _site_get(key, default=""):
    with engine.begin() as conn:
        r = conn.exec_driver_sql("SELECT value FROM site_settings WHERE key = ?", (key,)).fetchone()
    return (r[0] if r and r[0] is not None else default)


def _tk_jwt(scope: str) -> str:
    """Сгенерировать JWT для Tinkoff VoiceKit, scope: tinkoff.cloud.stt / tinkoff.cloud.tts"""
    import time, base64, hmac, hashlib, json as _json
    api_key = _site_get("tinkoff_api_key").strip()
    secret = _site_get("tinkoff_secret_key").strip()
    if not api_key or not secret:
        raise HTTPException(status_code=400, detail="Tinkoff VoiceKit ключи не настроены (Админка → Настройки)")
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT", "kid": api_key}
    payload = {"iss": "test_issuer", "sub": "test_user", "aud": scope, "exp": now + 600}
    def b64url(d):
        return base64.urlsafe_b64encode(_json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()
    h = b64url(header); p = b64url(payload)
    try:
        secret_bytes = base64.urlsafe_b64decode(secret + "=" * (-len(secret) % 4))
    except Exception:
        secret_bytes = secret.encode()
    sig = hmac.new(secret_bytes, f"{h}.{p}".encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{h}.{p}.{sig_b64}"


def _tk_base():
    return (_site_get("tinkoff_endpoint") or "https://api.tinkoff.ai").rstrip("/")


def _tk_stt(audio_bytes: bytes, sample_rate: int = 8000, language: str = "ru-RU") -> str:
    """Распознать речь через VoiceKit. Возвращает текст."""
    jwt = _tk_jwt("tinkoff.cloud.stt")
    url = _tk_base() + "/v1/stt:recognize"
    import base64 as _b
    payload = {
        "config": {
            "encoding": "MPEG_AUDIO",  # принимаем mp3
            "sample_rate_hertz": sample_rate,
            "language_code": language,
            "max_alternatives": 1,
            "enable_automatic_punctuation": True,
        },
        "audio": {"content": _b.b64encode(audio_bytes).decode("ascii")},
    }
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(url, headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}, json=payload)
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Tinkoff STT HTTP {r.status_code}: {r.text[:500]}")
            data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Tinkoff STT network error: {e!r}")
    results = data.get("results") or []
    if not results:
        return ""
    alts = results[0].get("alternatives") or []
    if not alts:
        return ""
    return alts[0].get("transcript", "") or ""


def _tk_tts(text: str, voice: str = "", sample_rate: int = 8000, encoding: str = "LINEAR16") -> bytes:
    """Синтезировать речь. Возвращает аудио-байты (PCM 16-bit для LINEAR16)."""
    jwt = _tk_jwt("tinkoff.cloud.tts")
    url = _tk_base() + "/v1/tts:synthesize"
    payload = {
        "input": {"text": text},
        "audio_config": {
            "audio_encoding": encoding,         # LINEAR16 (raw PCM), MPEG_AUDIO (mp3), ALAW
            "sample_rate_hertz": sample_rate,
        },
        "voice": {"name": voice or _site_get("tinkoff_voice", "alyona")},
    }
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(url, headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}, json=payload)
            if r.status_code != 200:
                detail = f"Tinkoff TTS HTTP {r.status_code}: {r.text[:500]}"
                raise HTTPException(status_code=502, detail=detail)
            data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Tinkoff TTS network error: {e!r}")
    import base64 as _b
    return _b.b64decode(data.get("audio_content", ""))


# # VSB_TTS_FALLBACK_V1


def _vsegpt_tts(text: str, voice: str = "", encoding: str = "MPEG_AUDIO", sample_rate: int = 16000) -> bytes:
    """Синтез через ВсеГПТ (OpenAI tts-1 / vosk-tts). Возвращает MP3 (или wav для vosk)."""
    settings = read_settings()
    if not settings.get("api_key"):
        raise HTTPException(status_code=400, detail="ВсеГПТ API-ключ не настроен")
    model = (_site_get("tts_model") or "tts-1").strip()
    if not voice:
        voice = (_site_get("tts_voice") or "alloy").strip()
    fmt = "mp3" if encoding == "MPEG_AUDIO" else ("wav" if encoding == "LINEAR16" else "mp3")
    payload = {
        "model": model,
        "input": text[:4000],
        "voice": voice,
        "response_format": fmt,
    }
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                endpoint(settings["base_url"], "audio/speech"),
                headers=provider_headers(settings),
                json=payload,
            )
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail=f"ВсеГПТ TTS HTTP {r.status_code}: {r.text[:500]}")
            return r.content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ВсеГПТ TTS error: {e!r}")


def _tts_dispatch(text: str, voice: str = "", encoding: str = "MPEG_AUDIO", sample_rate: int = 8000) -> bytes:
    """Точка единого синтеза. По умолчанию через ВсеГПТ (работает у всех)."""
    provider = (_site_get("tts_provider") or "vsegpt").strip().lower()
    if provider == "tinkoff":
        try:
            return _tk_tts(text, voice=voice, encoding=encoding, sample_rate=sample_rate)
        except HTTPException as e:
            # Auto-fallback на ВсеГПТ если Tinkoff TTS не доступен
            if e.status_code == 502 and ("403" in (e.detail or "") or "denied" in (e.detail or "").lower()):
                pass  # fall through to vsegpt
            else:
                raise
    # ВсеГПТ
    return _vsegpt_tts(text, voice=voice, encoding=encoding, sample_rate=sample_rate)


# ── Endpoints ──


_VOICE_SYSTEM_PROMPT = (
    "Ты — оператор компании ВСБ39 (системы безопасности в Калининграде) на телефоне. "
    "Говоришь по-русски, ВЕЖЛИВО и КРАТКО — максимум 2 коротких предложения за реплику. "
    "Звонят клиенты в нерабочее время или по запросу обратного звонка. "
    "Твоя цель за 3-5 реплик: понять (1) что нужно — видеонаблюдение / СКУД / охранная сигнализация / "
    "ремонт-обслуживание / другое; (2) тип и размер объекта (если уместно). "
    "Не давай конкретных цен — для этого утром перезвонит менеджер. "
    "Когда соберёшь достаточно, скажи: 'Спасибо, передам менеджеру, перезвоним вам в рабочее время. До свидания.' "
    "И в этой реплике добавь в самом конце технический маркер [HANGUP]. "
    "Если клиент злится / просит человека / сложный вопрос — сразу: 'Передам срочно менеджеру.' и [HANGUP]. "
    "НЕ обещай и не выдумывай факты о компании."
)


def _call_voice_ai(turns):
    """turns: list of {role, text}. Возвращает (текст_ответа, hangup_bool)."""
    settings = read_settings()
    if not settings.get("api_key"):
        return ("AI не настроен. До свидания.", True)
    messages = [{"role": "system", "content": _VOICE_SYSTEM_PROMPT}]
    for t in turns:
        role = "user" if t["role"] == "user" else "assistant"
        messages.append({"role": role, "content": t["text"][:1500]})
    try:
        with httpx.Client(timeout=20) as client:
            r = client.post(
                endpoint(settings["base_url"], "chat/completions"),
                headers=provider_headers(settings),
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": 200,
                    "temperature": 0.4,
                },
            )
            r.raise_for_status()
            txt = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    except Exception as e:
        return (f"Извините, технический сбой. Передам менеджеру. До свидания.", True)
    hangup = "[HANGUP]" in txt
    txt = txt.replace("[HANGUP]", "").strip()
    return (txt or "До свидания.", hangup)


def _ensure_lead(conn, phone):
    p = normalize_phone(phone)
    if not p:
        return (None, None)
    row = conn.exec_driver_sql("SELECT id, client_code FROM leads WHERE phone = ?", (p,)).fetchone()
    if row:
        conn.exec_driver_sql("UPDATE leads SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (row[0],))
        return (row[0], row[1])
    code = _next_client_code(conn)
    conn.exec_driver_sql(
        "INSERT INTO leads (phone, client_code, source_first) VALUES (?, ?, ?)",
        (p, code, "voice-call"),
    )
    return (conn.exec_driver_sql("SELECT last_insert_rowid()").fetchone()[0], code)



@router.post("/voice/stt")
async def voice_stt(
    file: UploadFile = File(...),
    sample_rate: int = Query(default=8000, ge=8000, le=48000),
    language: str = Query(default="ru-RU"),
):
    """Принять mp3-аудио, вернуть распознанный текст. Публичный для удобства провайдера."""
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(audio) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл больше 25 МБ — разбейте на части")
    text = _tk_stt(audio, sample_rate=sample_rate, language=language)
    return {"transcript": text}


@router.get("/voice/debug/jwt")
def voice_debug_jwt(user: User = Depends(get_current_user)):
    """Admin-only: вернуть JWT для TTS и его декодированные части — для отладки на jwt.io"""
    require_admin_user(user)
    api_key = _site_get("tinkoff_api_key").strip()
    secret = _site_get("tinkoff_secret_key").strip()
    info = {
        "api_key_set": bool(api_key),
        "api_key_len": len(api_key),
        "api_key_preview": (api_key[:6] + "..." + api_key[-4:]) if len(api_key) > 10 else api_key,
        "secret_set": bool(secret),
        "secret_len": len(secret),
        "endpoint_base": _tk_base(),
    }
    if not api_key or not secret:
        info["error"] = "Заполните оба ключа в админке"
        return info
    try:
        jwt_tts = _tk_jwt("tinkoff.cloud.tts")
        jwt_stt = _tk_jwt("tinkoff.cloud.stt")
        import json as _json, base64 as _b
        def _decode(t):
            parts = t.split(".")
            if len(parts) != 3: return {"raw": t}
            def b64d(s):
                pad = "=" * (-len(s) % 4)
                try:    return _json.loads(_b.urlsafe_b64decode(s + pad).decode())
                except: return {"raw": s}
            return {"header": b64d(parts[0]), "payload": b64d(parts[1]), "sig_first_8": parts[2][:8]}
        info["jwt_tts"] = jwt_tts
        info["jwt_tts_decoded"] = _decode(jwt_tts)
        info["jwt_stt_decoded"] = _decode(jwt_stt)
    except Exception as e:
        info["jwt_error"] = repr(e)
    return info


@router.post("/voice/tts")
def voice_tts(body: TTSIn):
    """Синтез речи. Возвращает audio как байты (Content-Type зависит от encoding)."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text пустой")
    if len(body.text) > 4000:
        raise HTTPException(status_code=400, detail="text > 4000 символов")
    audio = _tts_dispatch(body.text, voice=body.voice, sample_rate=body.sample_rate, encoding=body.encoding)
    ct = {"LINEAR16": "audio/wav", "MPEG_AUDIO": "audio/mpeg", "ALAW": "audio/x-alaw-basic"}.get(body.encoding, "application/octet-stream")
    # Для LINEAR16 нужна wav-обёртка, чтобы плееры понимали
    if body.encoding == "LINEAR16":
        import struct
        sr = body.sample_rate
        n = len(audio)
        header = (
            b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE" + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sr, sr*2, 2, 16)
            + b"data" + struct.pack("<I", n)
        )
        audio = header + audio
    return _FastResponse(content=audio, media_type=ct)


@router.post("/voice/dialog")
def voice_dialog(body: VoiceDialogIn):
    """Одна точка входа: текст или аудио клиента → AI ответ → TTS аудио + текст."""
    # Распознавание если пришло аудио
    if not body.transcript and body.audio_b64:
        import base64 as _b
        try:
            audio = _b.b64decode(body.audio_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="bad audio_b64")
        body.transcript = _tk_stt(audio, sample_rate=8000)

    # Ensure call started
    is_first = False
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT id FROM voice_calls WHERE provider_call_id = ?", (body.call_id,)).fetchone()
        if not row:
            is_first = True
            lead_id, _code = _ensure_lead(conn, body.caller_phone)
            conn.exec_driver_sql(
                "INSERT INTO voice_calls (provider_call_id, lead_id, direction, phone, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                (body.call_id, lead_id, body.direction, normalize_phone(body.caller_phone) or body.caller_phone),
            )

    if is_first and not body.transcript:
        # Начало звонка — выдаём приветствие, не вызывая GPT
        greeting = (
            "Здравствуйте! Вы дозвонились в ВСБ39. Сейчас нерабочее время — я AI-консультант. "
            "Расскажите, пожалуйста, что вас интересует?"
        )
        with engine.begin() as conn:
            cid = conn.exec_driver_sql("SELECT id FROM voice_calls WHERE provider_call_id = ?", (body.call_id,)).fetchone()[0]
            conn.exec_driver_sql(
                "INSERT INTO voice_dialog_turns (call_id, turn_no, role, text) VALUES (?, 1, 'assistant', ?)",
                (cid, greeting),
            )
        audio = _tts_dispatch(greeting, sample_rate=8000, encoding="MPEG_AUDIO")
        import base64 as _b
        return {"ai_text": greeting, "audio_mp3_b64": _b.b64encode(audio).decode(), "hangup": False}

    # Иначе — это очередная реплика; идём по логике /voice/call/turn
    res = voice_call_turn(CallTurnIn(call_id=body.call_id, transcript=body.transcript))
    audio = _tts_dispatch(res["ai_say"], sample_rate=8000, encoding="MPEG_AUDIO")
    import base64 as _b
    return {
        "ai_text": res["ai_say"],
        "audio_mp3_b64": _b.b64encode(audio).decode(),
        "hangup": res.get("hangup", False),
        "user_transcript": body.transcript,
    }


@router.post("/voice/call/start")
def voice_call_start(body: CallStartIn):
    """Провайдер шлёт когда трубка снята. Возвращаем фразу для TTS."""
    with engine.begin() as conn:
        lead_id, code = _ensure_lead(conn, body.caller_phone)
        # Idempotent: если call_id уже есть — возвращаем «продолжение»
        existing = conn.exec_driver_sql(
            "SELECT id FROM voice_calls WHERE provider_call_id = ?", (body.call_id,)
        ).fetchone()
        if existing:
            call_id = existing[0]
        else:
            conn.exec_driver_sql(
                "INSERT INTO voice_calls (provider_call_id, lead_id, direction, phone, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                (body.call_id, lead_id, body.direction, normalize_phone(body.caller_phone) or body.caller_phone),
            )
            call_id = conn.exec_driver_sql("SELECT last_insert_rowid()").fetchone()[0]

    # Первая реплика AI — не зовём GPT, говорим заранее заготовленную (быстрее)
    greeting = (
        "Здравствуйте! Вы дозвонились в ВСБ39 — системы безопасности Калининград. "
        "Сейчас нерабочее время, но я — AI-консультант, и постараюсь помочь. "
        "Расскажите, пожалуйста, что вас интересует?"
    )
    if body.direction == "out":
        greeting = (
            "Здравствуйте! Это ВСБ39, перезваниваем по вашей заявке с сайта. "
            "Подскажите, по какому вопросу обращались?"
        )

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO voice_dialog_turns (call_id, turn_no, role, text) VALUES (?, 1, 'assistant', ?)",
            (call_id, greeting),
        )
    return {"ai_say": greeting, "expect_input": True, "internal_call_id": call_id}


@router.post("/voice/call/turn")
def voice_call_turn(body: CallTurnIn):
    """После распознавания фразы клиента — генерируем ответ AI."""
    with engine.begin() as conn:
        row = conn.exec_driver_sql(
            "SELECT id FROM voice_calls WHERE provider_call_id = ?", (body.call_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Call not found")
        call_id = row[0]
        # Сохраняем фразу клиента
        next_turn = conn.exec_driver_sql(
            "SELECT IFNULL(MAX(turn_no), 0) + 1 FROM voice_dialog_turns WHERE call_id = ?", (call_id,)
        ).fetchone()[0]
        conn.exec_driver_sql(
            "INSERT INTO voice_dialog_turns (call_id, turn_no, role, text) VALUES (?, ?, 'user', ?)",
            (call_id, next_turn, (body.transcript or "")[:2000]),
        )
        # Берём всю историю для AI
        turns = [{"role": r[0], "text": r[1]} for r in conn.exec_driver_sql(
            "SELECT role, text FROM voice_dialog_turns WHERE call_id = ? ORDER BY turn_no",
            (call_id,)
        ).fetchall()]

    ai_say, hangup = _call_voice_ai(turns)
    # Если AI идёт на hangup — после 5 реплик клиента или сам решил
    user_turn_count = sum(1 for t in turns if t["role"] == "user")
    if user_turn_count >= 5:
        hangup = True

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO voice_dialog_turns (call_id, turn_no, role, text) VALUES (?, ?, 'assistant', ?)",
            (call_id, next_turn + 1, ai_say),
        )
    return {"ai_say": ai_say, "expect_input": not hangup, "hangup": hangup}


@router.post("/voice/call/end")
def voice_call_end(body: CallEndIn):
    """Звонок завершён. Финализация: summary + категория проблемы."""
    with engine.begin() as conn:
        row = conn.exec_driver_sql(
            "SELECT id FROM voice_calls WHERE provider_call_id = ?", (body.call_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Call not found")
        call_id = row[0]
        turns = [{"role": r[0], "text": r[1]} for r in conn.exec_driver_sql(
            "SELECT role, text FROM voice_dialog_turns WHERE call_id = ? ORDER BY turn_no",
            (call_id,)
        ).fetchall()]

    # Summary через GPT
    settings = read_settings()
    summary = ""
    category = "other"
    if settings.get("api_key") and turns:
        transcript_text = "\n".join(f"[{t['role']}] {t['text']}" for t in turns)
        try:
            with httpx.Client(timeout=20) as client:
                r = client.post(
                    endpoint(settings["base_url"], "chat/completions"),
                    headers=provider_headers(settings),
                    json={
                        "model": "openai/gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content":
                                "Ты ассистент, обрабатывающий запись звонка в компанию ВСБ39. "
                                "Дай ответ строго в формате двух строк:\n"
                                "SUMMARY: <одно предложение, что хочет клиент>\n"
                                "CATEGORY: <одно слово: видеонаблюдение | скуд | сигнализация | то | другое>"},
                            {"role": "user", "content": "Транскрипт:\n" + transcript_text}
                        ],
                        "max_tokens": 200,
                        "temperature": 0.2,
                    },
                )
                r.raise_for_status()
                ans = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                for line in ans.splitlines():
                    if line.upper().startswith("SUMMARY:"):
                        summary = line.split(":", 1)[1].strip()
                    elif line.upper().startswith("CATEGORY:"):
                        category = line.split(":", 1)[1].strip().lower()
        except Exception:
            pass

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE voice_calls SET ended_at = CURRENT_TIMESTAMP, duration_sec = ?, "
            "recording_url = ?, summary = ?, category = ?, status = 'done' "
            "WHERE id = ?",
            (int(body.duration_sec or 0), body.recording_url or "", summary, category, call_id),
        )
    return {"status": "ok", "summary": summary, "category": category}


# ── Admin ──

