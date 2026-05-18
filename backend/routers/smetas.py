import json
from io import BytesIO
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from ai.smeta_builder import (
    is_equipment_smeta_item,
    smeta_equipment_summary,
    validate_and_fix_smeta,
)
from auth import (
    decode_token,
    get_current_user,
    normalized_owner_id,
    require_smeta_access,
)
from crud import (
    add_smeta_item,
    clone_smeta,
    create_smeta,
    create_smeta_revision,
    delete_smeta,
    delete_smeta_item,
    get_material,
    get_smeta,
    get_smeta_revisions,
    get_visible_smetas,
    restore_smeta_revision,
    update_smeta,
    update_smeta_item,
)
from database import get_db
from models import SmetaAccess, User
from schemas import ShareIn, SmetaIn, SmetaItemIn
from utils.excel import (
    build_smeta_print_html,
    build_smeta_workbook,
    parse_section_adjustments,
    safe_filename,
    smeta_check_issues,
    smeta_to_dict,
)
from utils.text_utils import (
    classify_catalog_item,
    default_section_for_type,
    normalize_quantity,
    summarize_characteristics,
)

router = APIRouter()


@router.get("/smetas")
def read_smetas(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [smeta_to_dict(smeta) for smeta in get_visible_smetas(db, user)]


@router.post("/smetas")
def create_smeta_endpoint(payload: SmetaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.model_dump()
    name = data.pop("name").strip()
    data["tax_mode"] = data.get("tax_mode") if data.get("tax_mode") in {"none", "vat_added", "vat_included"} else "none"
    data["section_adjustments"] = json.dumps(
        parse_section_adjustments(data.get("section_adjustments", {})),
        ensure_ascii=False,
    )
    smeta = create_smeta(
        db,
        name,
        {
            **{key: (value if key in {"tax_rate", "parent_id"} else str(value).strip()) for key, value in data.items()},
            "owner_id": user.id,
        },
    )
    create_smeta_revision(db, get_smeta(db, smeta.id), "create")
    return smeta_to_dict(get_smeta(db, smeta.id))


@router.patch("/smetas/{smeta_id}")
def update_smeta_endpoint(
    smeta_id: int,
    payload: SmetaIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_smeta_access(db, smeta_id, user, write=True)
    raw_data = payload.model_dump()
    raw_data["tax_mode"] = raw_data.get("tax_mode") if raw_data.get("tax_mode") in {"none", "vat_added", "vat_included"} else "none"
    raw_data["section_adjustments"] = json.dumps(
        parse_section_adjustments(raw_data.get("section_adjustments", {})),
        ensure_ascii=False,
    )
    data = {key: (value if key in {"tax_rate"} else str(value).strip()) for key, value in raw_data.items()}
    data["name"] = data["name"] or "Без названия"
    smeta = update_smeta(db, smeta_id, data)
    if not smeta:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    create_smeta_revision(db, get_smeta(db, smeta_id), "update")
    return smeta_to_dict(get_smeta(db, smeta_id))


@router.post("/smetas/{smeta_id}/branch")
def branch_smeta_endpoint(smeta_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    source = require_smeta_access(db, smeta_id, user)
    branch = clone_smeta(db, smeta_id, f"{source.name} - вариант")
    branch.owner_id = user.id
    db.commit()
    create_smeta_revision(db, get_smeta(db, branch.id), "branch")
    return smeta_to_dict(get_smeta(db, branch.id))


@router.delete("/smetas/{smeta_id}")
def delete_smeta_endpoint(smeta_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    smeta = require_smeta_access(db, smeta_id, user, write=True)
    if not user.is_admin and normalized_owner_id(smeta) != user.id:
        raise HTTPException(status_code=403, detail="Удалять может только владелец")
    if not delete_smeta(db, smeta_id):
        raise HTTPException(status_code=404, detail="Смета не найдена")
    return {"status": "ok"}


@router.get("/smetas/{smeta_id}")
def read_smeta(smeta_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    smeta = require_smeta_access(db, smeta_id, user)
    return smeta_to_dict(smeta)


@router.post("/smetas/{smeta_id}/share")
def share_smeta(
    smeta_id: int,
    payload: ShareIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    smeta = require_smeta_access(db, smeta_id, user, write=True)
    if not user.is_admin and normalized_owner_id(smeta) != user.id:
        raise HTTPException(status_code=403, detail="Делиться может только владелец")
    permission = payload.permission if payload.permission in {"view", "edit"} else "view"
    target_email = payload.email.strip().lower()
    target = db.query(User).filter(User.email == target_email).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    access = (
        db.query(SmetaAccess)
        .filter(SmetaAccess.smeta_id == smeta_id, SmetaAccess.user_id == target.id)
        .first()
    )
    if access:
        access.permission = permission
    else:
        db.add(SmetaAccess(smeta_id=smeta_id, user_id=target.id, permission=permission))
    db.commit()
    return {"status": "ok", "email": target.email, "permission": permission}


@router.get("/smetas/{smeta_id}/revisions")
def list_smeta_revisions_endpoint(
    smeta_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_smeta_access(db, smeta_id, user)
    revisions = get_smeta_revisions(db, smeta_id)
    return [
        {
            "id": revision.id,
            "smeta_id": revision.smeta_id,
            "label": revision.label or "",
            "created_at": revision.created_at.isoformat() if revision.created_at else None,
        }
        for revision in revisions
    ]


@router.post("/smetas/{smeta_id}/revisions/{revision_id}/restore")
def restore_smeta_revision_endpoint(
    smeta_id: int,
    revision_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_smeta_access(db, smeta_id, user, write=True)
    smeta = restore_smeta_revision(db, smeta_id, revision_id)
    if not smeta:
        raise HTTPException(status_code=404, detail="Версия не найдена")
    create_smeta_revision(db, smeta, "restore")
    return smeta_to_dict(get_smeta(db, smeta_id))


@router.post("/smetas/{smeta_id}/check")
def check_smeta_endpoint(smeta_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_smeta_access(db, smeta_id, user, write=True)
    smeta, results = validate_and_fix_smeta(db, smeta_id)
    if not smeta:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    refreshed = get_smeta(db, smeta_id)
    return {
        "smeta": smeta_to_dict(refreshed),
        "results": results,
        "issues": smeta_check_issues(refreshed),
        "summary": smeta_equipment_summary(refreshed),
    }


@router.get("/smetas/{smeta_id}/export.xlsx")
def export_smeta_xlsx(smeta_id: int, token: str = Query(default=""), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    user = db.query(User).filter(User.id == int(payload.get("sub") or 0)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    smeta = require_smeta_access(db, smeta_id, user)
    workbook = build_smeta_workbook(smeta)
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    filename = quote(f"{safe_filename(smeta.name)}.xlsx")
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/smetas/{smeta_id}/print", response_class=HTMLResponse)
def print_smeta(smeta_id: int, token: str = Query(default=""), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    user = db.query(User).filter(User.id == int(payload.get("sub") or 0)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    smeta = require_smeta_access(db, smeta_id, user)
    return HTMLResponse(build_smeta_print_html(smeta))


@router.post("/smetas/{smeta_id}/items")
def create_smeta_item_endpoint(
    smeta_id: int,
    payload: SmetaItemIn,
    material_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    smeta = require_smeta_access(db, smeta_id, user, write=True)

    item_data = payload.model_dump()
    if material_id is not None:
        material = get_material(db, material_id)
        if not material:
            raise HTTPException(status_code=404, detail="Материал не найден")
        material_type = material.item_type or classify_catalog_item(material.name, material.source)
        item_data["quantity"] = normalize_quantity(item_data.get("quantity", 1))
        item_data.update(
            {
                "item_type": material_type,
                "section": default_section_for_type(material_type),
                "name": material.name,
                "characteristics": summarize_characteristics(material.characteristics or ""),
                "unit": material.unit or "",
                "unit_price": material.price,
                "source": material.source or "",
            }
        )

    added_item = add_smeta_item(db, smeta_id, item_data)
    if is_equipment_smeta_item(added_item):
        validate_and_fix_smeta(db, smeta_id)
    create_smeta_revision(db, get_smeta(db, smeta_id), "add item")
    return smeta_to_dict(get_smeta(db, smeta_id))


@router.delete("/smetas/{smeta_id}/items/{item_id}")
def delete_smeta_item_endpoint(
    smeta_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_smeta_access(db, smeta_id, user, write=True)
    if not delete_smeta_item(db, smeta_id, item_id):
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    create_smeta_revision(db, get_smeta(db, smeta_id), "delete item")
    return smeta_to_dict(get_smeta(db, smeta_id))


@router.patch("/smetas/{smeta_id}/items/{item_id}")
def update_smeta_item_endpoint(
    smeta_id: int,
    item_id: int,
    payload: SmetaItemIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_smeta_access(db, smeta_id, user, write=True)
    data = payload.model_dump()
    data["quantity"] = normalize_quantity(data["quantity"])
    item = update_smeta_item(db, smeta_id, item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    if is_equipment_smeta_item(item):
        validate_and_fix_smeta(db, smeta_id)
    create_smeta_revision(db, get_smeta(db, smeta_id), "update item")
    return smeta_to_dict(get_smeta(db, smeta_id))

