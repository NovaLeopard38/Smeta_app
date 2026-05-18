import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth import (
    ADMIN_EMAIL,
    get_current_user,
    normalized_owner_id,
    require_admin_user,
    user_to_dict,
)
from database import engine, get_db
from models import Smeta, SmetaAccess, User
from crud import get_smeta
from schemas import CallStatusIn
from utils.excel import normalized_parent_id, smeta_to_dict

router = APIRouter()


@router.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
    if target.email == ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="\u0421\u043a\u0440\u044b\u0442\u043e\u0433\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0430 \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u043d\u0435\u043b\u044c\u0437\u044f")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="\u041d\u0435\u043b\u044c\u0437\u044f \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0441\u0430\u043c\u043e\u0433\u043e \u0441\u0435\u0431\u044f")
    admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if admin:
        db.execute(text("UPDATE smetas SET owner_id = :owner_id WHERE owner_id = :target_id"), {"owner_id": admin.id, "target_id": target.id})
    db.query(SmetaAccess).filter(SmetaAccess.user_id == target.id).delete(synchronize_session=False)
    db.delete(target)
    db.commit()
    return {"status": "ok"}


@router.get("/admin/users")
def admin_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin_user(user)
    rows = db.query(User).order_by(User.id.desc()).all()
    return [user_to_dict(row) for row in rows]


@router.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
    if target.email == ADMIN_EMAIL and not bool(payload.get("is_admin", True)):
        raise HTTPException(status_code=400, detail="\u0421\u043a\u0440\u044b\u0442\u043e\u0433\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0430 \u043d\u0435\u043b\u044c\u0437\u044f \u0440\u0430\u0437\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c")
    if "is_admin" in payload:
        target.is_admin = 1 if bool(payload.get("is_admin")) else 0
    db.commit()
    db.refresh(target)
    return user_to_dict(target)


@router.get("/admin/smetas/{smeta_id}/access")
def admin_smeta_access(
    smeta_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    smeta = get_smeta(db, smeta_id)
    if not smeta:
        raise HTTPException(status_code=404, detail="\u0421\u043c\u0435\u0442\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430")
    rows = (
        db.query(SmetaAccess, User)
        .join(User, User.id == SmetaAccess.user_id)
        .filter(SmetaAccess.smeta_id == smeta_id)
        .order_by(User.email.asc())
        .all()
    )
    return {
        "smeta": smeta_to_dict(smeta),
        "access": [
            {
                "id": access.id,
                "user_id": user_row.id,
                "email": user_row.email,
                "permission": access.permission,
                "is_admin": bool(user_row.is_admin),
            }
            for access, user_row in rows
        ],
    }


@router.get("/admin/users/{user_id}/smetas")
def admin_user_smetas(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
    access_rows = db.query(SmetaAccess).filter(SmetaAccess.user_id == user_id).all()
    access_map = {row.smeta_id: row.permission for row in access_rows}
    smetas = db.query(Smeta).order_by(Smeta.id.desc()).all()
    rows = []
    for smeta in smetas:
        owner_id = normalized_owner_id(smeta)
        permission = "owner" if owner_id == target.id else access_map.get(smeta.id)
        if not permission and not target.is_admin:
            continue
        if target.is_admin and not permission:
            permission = "admin"
        if permission:
            rows.append(
                {
                    "id": smeta.id,
                    "name": smeta.name,
                    "permission": permission,
                    "total": smeta_to_dict(smeta)["total"],
                    "parent_id": normalized_parent_id(smeta),
                }
            )
    return {"user": user_to_dict(target), "smetas": rows}


@router.delete("/admin/smetas/{smeta_id}/access/{user_id}")
def admin_revoke_access(
    smeta_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    access = (
        db.query(SmetaAccess)
        .filter(SmetaAccess.smeta_id == smeta_id, SmetaAccess.user_id == user_id)
        .first()
    )
    if not access:
        raise HTTPException(status_code=404, detail="\u0414\u043e\u0441\u0442\u0443\u043f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
    db.delete(access)
    db.commit()
    return {"status": "ok"}


@router.get("/admin/leads")
def admin_leads(user: User = Depends(get_current_user)):
    require_admin_user(user)
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("""
            SELECT l.id, l.client_code, l.phone, l.created_at, l.last_seen, l.source_first,
                   (SELECT COUNT(*) FROM quotes q WHERE q.lead_id = l.id) AS qcount,
                   (SELECT MAX(total)  FROM quotes q WHERE q.lead_id = l.id) AS maxtotal
            FROM leads l ORDER BY l.last_seen DESC
        """).fetchall()
    return [
        {"id": r[0], "client_code": r[1], "phone": r[2],
         "created_at": str(r[3]) if r[3] else None,
         "last_seen": str(r[4]) if r[4] else None,
         "source_first": r[5] or "", "quotes_count": r[6] or 0,
         "max_total": float(r[7] or 0)}
        for r in rows
    ]


@router.get("/admin/leads/{lead_id}/quotes")
def admin_lead_quotes(lead_id: int, user: User = Depends(get_current_user)):
    require_admin_user(user)
    with engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT id, kind, no, payload, meta, total, created_at FROM quotes WHERE lead_id = ? ORDER BY created_at DESC",
            (lead_id,)
        ).fetchall()
        chat = conn.exec_driver_sql(
            "SELECT role, content, created_at FROM chat_messages WHERE lead_id = ? ORDER BY created_at",
            (lead_id,)
        ).fetchall()
    result = {
        "quotes": [{
            "id": r[0], "kind": r[1], "no": r[2],
            "payload": json.loads(r[3] or "[]"),
            "meta":    json.loads(r[4] or "{}"),
            "total":   float(r[5] or 0),
            "created_at": str(r[6]) if r[6] else None,
        } for r in rows],
        "chat": [{"role": r[0], "content": r[1], "at": str(r[2])} for r in chat],
    }
    return result


@router.get("/admin/voice/calls")
def admin_voice_calls(user: User = Depends(get_current_user)):
    require_admin_user(user)
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("""
            SELECT v.id, v.provider_call_id, l.client_code, v.phone, v.direction, v.started_at, v.duration_sec,
                   v.status, v.summary, v.category, v.manager_status, v.recording_url
              FROM voice_calls v LEFT JOIN leads l ON l.id = v.lead_id
             ORDER BY v.started_at DESC LIMIT 200
        """).fetchall()
    return [{
        "id": r[0], "provider_call_id": r[1], "client_code": r[2] or "",
        "phone": r[3], "direction": r[4], "started_at": str(r[5]) if r[5] else None,
        "duration_sec": r[6] or 0, "status": r[7], "summary": r[8] or "",
        "category": r[9] or "", "manager_status": r[10] or "new",
        "recording_url": r[11] or "",
    } for r in rows]


@router.get("/admin/voice/calls/{call_id}")
def admin_voice_call_detail(call_id: int, user: User = Depends(get_current_user)):
    require_admin_user(user)
    with engine.begin() as conn:
        cr = conn.exec_driver_sql("SELECT * FROM voice_calls WHERE id = ?", (call_id,)).fetchone()
        if not cr:
            raise HTTPException(status_code=404, detail="Not found")
        cols = ["id", "provider_call_id", "lead_id", "direction", "phone", "started_at", "ended_at",
                "duration_sec", "status", "recording_url", "summary", "category", "manager_status", "raw_payload"]
        call = dict(zip(cols, cr))
        for k in ("started_at", "ended_at"):
            if call.get(k) is not None:
                call[k] = str(call[k])
        turns = conn.exec_driver_sql(
            "SELECT turn_no, role, text, created_at FROM voice_dialog_turns WHERE call_id = ? ORDER BY turn_no",
            (call_id,)
        ).fetchall()
    return {
        "call": call,
        "turns": [{"turn_no": r[0], "role": r[1], "text": r[2], "at": str(r[3])} for r in turns],
    }


@router.patch("/admin/voice/calls/{call_id}/status")
def admin_voice_call_status(call_id: int, body: CallStatusIn, user: User = Depends(get_current_user)):
    require_admin_user(user)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE voice_calls SET manager_status = ? WHERE id = ?",
            (body.manager_status[:20], call_id)
        )
    return {"status": "ok"}
