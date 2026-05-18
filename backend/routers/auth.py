"""
Authentication router: login, register, me.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from deps import get_db, get_current_user
from models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthIn(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class RegisterIn(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


@router.post("/login")
def login(payload: AuthIn, db: Session = Depends(get_db)):
    from app import verify_password, create_token, user_to_dict
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return {"access_token": create_token(user), "user": user_to_dict(user)}


@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    from app import ADMIN_EMAIL, hash_password, create_token, user_to_dict
    email = payload.email.strip().lower()
    if email == ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Этот email зарезервирован для администратора")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Пользователь уже существует")
    user = User(email=email, password_hash=hash_password(payload.password), is_admin=0)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user), "user": user_to_dict(user)}


@router.get("/me")
def auth_me(user: User = Depends(get_current_user)):
    from app import user_to_dict
    return user_to_dict(user)
