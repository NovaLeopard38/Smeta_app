
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import Smeta, SmetaAccess, SmetaRevision, User
from crud import get_smeta, create_smeta_revision

AUTH_SECRET = os.getenv("AUTH_SECRET", "local-smeta-secret-change-me")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_password(password, salt=None):
    salt_bytes = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 200000)
    return f"pbkdf2${b64url(salt_bytes)}${b64url(digest)}"


def verify_password(password, stored_hash):
    try:
        _, salt_value, digest_value = (stored_hash or "").split("$", 2)
        expected = b64url_decode(digest_value)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b64url_decode(salt_value), 200000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_token(user):
    payload = {"sub": user.id, "email": user.email, "is_admin": bool(user.is_admin), "exp": int(time.time()) + 60 * 60 * 24 * 14}
    body = b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = b64url(hmac.HMAC(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_token(token):
    try:
        body, signature = token.split(".", 1)
        expected = b64url(hmac.HMAC(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(b64url_decode(body))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def normalized_owner_id(smeta):
    try:
        return int(getattr(smeta, "owner_id", None) or 0) or None
    except (TypeError, ValueError):
        return None


def user_to_dict(user):
    created_at = getattr(user, "created_at", None)
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": bool(user.is_admin),
        "created_at": created_at.isoformat() if created_at else None,
    }


def get_current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Сессия истекла")
    user = db.query(User).filter(User.id == int(payload.get("sub") or 0)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def require_admin_user(user):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Только для администратора")
    return user


def smeta_permission(db, smeta_id, user):
    smeta = get_smeta(db, smeta_id)
    if not smeta:
        return None, ""
    if user.is_admin or normalized_owner_id(smeta) == user.id:
        return smeta, "owner"
    access = (
        db.query(SmetaAccess)
        .filter(SmetaAccess.smeta_id == smeta_id, SmetaAccess.user_id == user.id)
        .first()
    )
    return smeta, (access.permission if access else "")


def require_smeta_access(db, smeta_id, user, write=False):
    smeta, permission = smeta_permission(db, smeta_id, user)
    if not smeta:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    if permission == "owner" or (permission == "edit") or (permission == "view" and not write):
        return smeta
    raise HTTPException(status_code=403, detail="Нет доступа к смете")


def ensure_admin_user():
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        import warnings
        warnings.warn("ADMIN_EMAIL/ADMIN_PASSWORD not set -- skipping admin user creation.")
        return
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin:
            admin = User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), is_admin=1)
            db.add(admin)
            db.commit()
            db.refresh(admin)
        elif not verify_password(ADMIN_PASSWORD, admin.password_hash):
            admin.password_hash = hash_password(ADMIN_PASSWORD)
            admin.is_admin = 1
            db.commit()
            db.refresh(admin)
        db.execute(text("UPDATE smetas SET owner_id = :owner_id WHERE owner_id IS NULL"), {"owner_id": admin.id})
        db.commit()
    finally:
        db.close()


def ensure_revision_seed():
    db = SessionLocal()
    try:
        smetas = db.query(Smeta).order_by(Smeta.id.asc()).all()
        for smeta in smetas:
            existing = db.query(SmetaRevision).filter(SmetaRevision.smeta_id == smeta.id).first()
            if not existing:
                create_smeta_revision(db, smeta, "seed")
    finally:
        db.close()
