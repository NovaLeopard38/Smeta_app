"""
Shared dependencies for FastAPI routers.
Database session, current user, admin check, etc.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from models import User, SmetaAccess


def get_db():
    """Yield a database session."""
    from app import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Extract and validate current user from Bearer token."""
    from app import decode_token
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
    """Raise 403 if user is not admin."""
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Только для администратора")
    return user
