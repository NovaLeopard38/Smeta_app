"""
Admin router: user management, access control.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from deps import get_db, get_current_user, require_admin_user
from models import User, Smeta, SmetaAccess

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def admin_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin_user(user)
    from app import user_to_dict
    rows = db.query(User).order_by(User.id.desc()).all()
    return [user_to_dict(row) for row in rows]


@router.patch("/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    from app import ADMIN_EMAIL, user_to_dict
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target.email == ADMIN_EMAIL and not bool(payload.get("is_admin", True)):
        raise HTTPException(status_code=400, detail="Скрытого администратора нельзя разжаловать")
    if "is_admin" in payload:
        target.is_admin = 1 if bool(payload.get("is_admin")) else 0
    db.commit()
    db.refresh(target)
    return user_to_dict(target)


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    from app import ADMIN_EMAIL
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target.email == ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Скрытого администратора удалить нельзя")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if admin:
        db.execute(text("UPDATE smetas SET owner_id = :owner_id WHERE owner_id = :target_id"),
                   {"owner_id": admin.id, "target_id": target.id})
    db.query(SmetaAccess).filter(SmetaAccess.user_id == target.id).delete(synchronize_session=False)
    db.delete(target)
    db.commit()
    return {"status": "ok"}


@router.get("/smetas/{smeta_id}/access")
def admin_smeta_access(
    smeta_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    from app import get_smeta, smeta_to_dict
    from crud import get_smeta
    smeta = get_smeta(db, smeta_id)
    if not smeta:
        raise HTTPException(status_code=404, detail="Смета не найдена")
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


@router.delete("/smetas/{smeta_id}/access/{user_id}")
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
        raise HTTPException(status_code=404, detail="Доступ не найден")
    db.delete(access)
    db.commit()
    return {"status": "ok"}


@router.get("/users/{user_id}/smetas")
def admin_user_smetas(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    from app import user_to_dict, smeta_to_dict, normalized_owner_id, normalized_parent_id
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
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
