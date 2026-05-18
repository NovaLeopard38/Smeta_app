import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import (
    ADMIN_EMAIL,
    create_token,
    get_current_user,
    hash_password,
    user_to_dict,
    verify_password,
)
from database import get_db
from models import User
from schemas import AuthIn, RegisterIn

router = APIRouter()


@router.get("/")
def read_root():
    return {"message": "Приложение для смет работает!"}


@router.post("/auth/login")
def login(payload: AuthIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return {"access_token": create_token(user), "user": user_to_dict(user)}


@router.post("/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
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


@router.get("/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return user_to_dict(user)
