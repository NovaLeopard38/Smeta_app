import json

from fastapi import APIRouter, HTTPException, Query

from database import engine
from schemas import LeadIn, QuoteIn
from utils.text_utils import normalize_phone, next_client_code

router = APIRouter()


def _ensure_leads_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL UNIQUE,
                client_code TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_first TEXT DEFAULT '',
                notes TEXT DEFAULT ''
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                no TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '[]',
                meta TEXT NOT NULL DEFAULT '{}',
                total REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


_ensure_leads_schema()


def _next_client_code(conn) -> str:
    """K-NNNNNN sequential by max(id)+1. Delegates to utils.text_utils.next_client_code."""
    return next_client_code(conn)


def _next_quote_no(conn, lead_id: int, kind: str) -> str:
    row = conn.exec_driver_sql(
        "SELECT COUNT(*) FROM quotes WHERE lead_id = ? AND kind = ?",
        (lead_id, kind),
    ).fetchone()
    prefix = {"kp": "КП", "smeta": "СМ", "callback": "ЗВ"}.get(kind, "Q")
    return f"{prefix}-{(row[0] or 0) + 1:04d}"


@router.post("/leads")
def create_or_get_lead(payload: LeadIn):
    phone = normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    with engine.begin() as conn:
        row = conn.exec_driver_sql(
            "SELECT id, client_code FROM leads WHERE phone = ?", (phone,)
        ).fetchone()
        if row:
            conn.exec_driver_sql(
                "UPDATE leads SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (row[0],)
            )
            return {"id": row[0], "client_code": row[1], "phone": phone, "is_new": False}
        code = _next_client_code(conn)
        conn.exec_driver_sql(
            "INSERT INTO leads (phone, client_code, source_first) VALUES (?, ?, ?)",
            (phone, code, (payload.source or '')[:120]),
        )
        new_id = conn.exec_driver_sql("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": new_id, "client_code": code, "phone": phone, "is_new": True}


@router.post("/leads/quote")
def save_quote(body: QuoteIn):
    phone = normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    if body.kind not in ("smeta", "kp", "callback"):
        raise HTTPException(status_code=400, detail="kind must be smeta|kp|callback")
    with engine.begin() as conn:
        row = conn.exec_driver_sql(
            "SELECT id, client_code FROM leads WHERE phone = ?", (phone,)
        ).fetchone()
        if row:
            lead_id, code = row
            conn.exec_driver_sql(
                "UPDATE leads SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (lead_id,)
            )
        else:
            code = _next_client_code(conn)
            conn.exec_driver_sql(
                "INSERT INTO leads (phone, client_code, source_first) VALUES (?, ?, ?)",
                (phone, code, (body.source or '')[:120]),
            )
            lead_id = conn.exec_driver_sql("SELECT last_insert_rowid()").fetchone()[0]
        no = _next_quote_no(conn, lead_id, body.kind)
        conn.exec_driver_sql(
            "INSERT INTO quotes (lead_id, kind, no, payload, meta, total) VALUES (?, ?, ?, ?, ?, ?)",
            (lead_id, body.kind, no, json.dumps(body.payload, ensure_ascii=False),
             json.dumps(body.meta or {}, ensure_ascii=False), float(body.total or 0)),
        )
        q_id = conn.exec_driver_sql("SELECT last_insert_rowid()").fetchone()[0]
    return {
        "lead_id": lead_id,
        "client_code": code,
        "quote_id": q_id,
        "quote_no": no,
        "kind": body.kind,
    }


@router.get("/leads/me/history")
def my_history(
    phone: str = Query(...),
    client_code: str = Query(default=""),
):
    """Public history fetch -- phone + client_code (recommended) for protection."""
    p = normalize_phone(phone)
    if not p:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    with engine.begin() as conn:
        lead = conn.exec_driver_sql(
            "SELECT id, client_code, created_at FROM leads WHERE phone = ?", (p,)
        ).fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="История по этому номеру не найдена")
        lead_id, code, registered = lead
        if client_code and client_code.strip().upper() != (code or "").upper():
            raise HTTPException(status_code=403, detail="Клиентский код не совпадает с номером")
        quotes = conn.exec_driver_sql(
            "SELECT id, kind, no, payload, meta, total, created_at FROM quotes "
            "WHERE lead_id = ? ORDER BY id DESC", (lead_id,)
        ).fetchall()
        chat = conn.exec_driver_sql(
            "SELECT role, content, created_at FROM chat_messages WHERE lead_id = ? ORDER BY id",
            (lead_id,)
        ).fetchall()
        conn.exec_driver_sql("UPDATE leads SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (lead_id,))
    return {
        "client_code": code,
        "registered_at": str(registered) if registered else None,
        "quotes": [{
            "id": r[0], "kind": r[1], "no": r[2],
            "payload": json.loads(r[3] or "[]"),
            "meta": json.loads(r[4] or "{}"),
            "total": float(r[5] or 0),
            "created_at": str(r[6]) if r[6] else None,
        } for r in quotes],
        "chat": [{"role": r[0], "content": r[1], "at": str(r[2])} for r in chat],
    }


@router.get("/leads/quote/restore")
def restore_quote(
    phone: str = Query(...),
    quote_no: str = Query(default=""),
    client_code: str = Query(default=""),
):
    p = normalize_phone(phone)
    if not p:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    with engine.begin() as conn:
        lead = conn.exec_driver_sql(
            "SELECT id, client_code FROM leads WHERE phone = ?", (p,)
        ).fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="По этому номеру заявок не найдено")
        lead_id, code = lead
        if client_code and client_code.strip().upper() != (code or "").upper():
            raise HTTPException(status_code=403, detail="Клиентский код не совпадает с номером телефона")
        if quote_no:
            row = conn.exec_driver_sql(
                "SELECT id, kind, no, payload, meta, total, created_at FROM quotes "
                "WHERE lead_id = ? AND upper(no) = upper(?) ORDER BY id DESC LIMIT 1",
                (lead_id, quote_no.strip()),
            ).fetchone()
        else:
            row = conn.exec_driver_sql(
                "SELECT id, kind, no, payload, meta, total, created_at FROM quotes "
                "WHERE lead_id = ? AND kind IN ('smeta','kp') ORDER BY id DESC LIMIT 1",
                (lead_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Смета не найдена")
    return {
        "client_code": code,
        "quote": {
            "id": row[0],
            "kind": row[1],
            "no": row[2],
            "payload": json.loads(row[3] or "[]"),
            "meta": json.loads(row[4] or "{}"),
            "total": float(row[5] or 0),
            "created_at": str(row[6]) if row[6] else None,
        },
    }
