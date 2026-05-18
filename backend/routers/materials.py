import datetime
import re
import urllib.parse as _up_img
from typing import Optional

import httpx
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ai.core import call_ai_json
from auth import get_current_user, require_admin_user
from config import DEFAULT_SECTIONS, read_settings
from crud import (
    create_material,
    filter_materials,
    get_material,
    get_materials,
    normalize_search_text,
)
from database import get_db
from models import Material, User
from schemas import MaterialIn, MaterialUpdateIn, PriceImportResult
from utils.excel import (
    dataframe_to_text,
    extract_pdf_text,
    import_excel_by_guess,
    parse_excel_workbook,
    save_ai_materials,
    save_parsed_materials,
)
from utils.html_utils import html_to_text
from utils.text_utils import classify_catalog_item, endpoint

router = APIRouter()

MATERIAL_CATEGORY_TERMS = {
    "camera": ["камера", "видеокамера", "ip камера", "ahd камера"],
    "recorder": ["регистратор", "видеорегистратор", "nvr", "dvr"],
    "cable": ["кабель", "провод"],
    "network": ["коммутатор", "poe", "конвертер", "интерфейс"],
    "power": ["ибп", "блок питания", "аккумулятор", "резервирован"],
    "access": ["скуд", "считыватель", "замок", "контроллер", "с2000"],
    "storage": ["жесткий диск", "hdd", "жд", "накопитель"],
}


def material_to_dict(material):
    item_type = material.item_type or classify_catalog_item(material.name, material.source)
    return {
        "id": material.id,
        "item_type": item_type,
        "name": material.name,
        "characteristics": material.characteristics or "",
        "unit": material.unit or "",
        "price": material.price,
        "source": material.source or "",
        "image_url": getattr(material, "image_url", None) or "",
        "category": classify_catalog_item(material.name or "", material.source or ""),
        "last_update": material.last_update,
    }


def material_matches_category(material, category):
    terms = MATERIAL_CATEGORY_TERMS.get((category or "").strip().lower())
    if not terms:
        return True
    text_value = normalize_search_text(f"{material.name or ''} {material.source or ''}")
    return any(normalize_search_text(term) in text_value for term in terms)


def _extract_significant_tokens(query: str):
    """Split a product name into significant tokens for catalog search."""
    return [t for t in re.findall(r"[\w\-./]+", query, re.UNICODE) if not t.isdigit()][:4]


def _fetch_optimus_image(query: str) -> str:
    """Search optimus-cctv.ru (Beget hosting — bypass anti-bot with cookie)."""
    if not query.strip():
        return ""
    tokens = _extract_significant_tokens(query)
    # Optimus catalog search is sensitive to short codes — try multiple queries
    queries = []
    # Find model code like "RA-241E" or "P098"
    codes = re.findall(r"[A-Z]+[-]?\d+[A-Z0-9]*", query)
    if codes:
        queries.append(codes[0])
    queries.append(" ".join(tokens[:3]) or query[:60])
    queries.append(" ".join(tokens[:2]))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru,en;q=0.7",
    }
    cookies = {"beget": "begetok"}
    for q in queries:
        if not q.strip():
            continue
        url = "https://optimus-cctv.ru/catalog/?q=" + _up_img.quote(q)
        try:
            with httpx.Client(timeout=15, follow_redirects=True, headers=headers, cookies=cookies) as client:
                r = client.get(url)
                if r.status_code != 200 or len(r.text) < 5000:
                    continue
                html = r.text
        except Exception:
            continue
        # Product cards on optimus-cctv.ru use /images/prev/{hash}_s500x500.jpg
        m = re.search(r'<img[^>]+(?:src|data-src)="(/images/prev/[^"]+_s500x500\.(?:jpg|jpeg|png|webp))"', html, re.IGNORECASE)
        if not m:
            # Fall back to any product image
            m = re.search(r'<img[^>]+(?:src|data-src)="(/images/prev/[^"]+\.(?:jpg|jpeg|png|webp))"', html, re.IGNORECASE)
        if m:
            return "https://optimus-cctv.ru" + m.group(1)
    return ""


def _fetch_tinko_image(query: str) -> str:
    """Search tinko.ru by query, return first product image URL or ''. (Mostly fails — SPA.)"""
    if not query.strip():
        return ""
    tokens = _extract_significant_tokens(query)
    q = " ".join(tokens) or query[:60]
    url = "https://www.tinko.ru/catalog/?q=" + _up_img.quote(q)
    headers = {
        "User-Agent": "Mozilla/5.0 (VSB39 catalog image bot)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru,en;q=0.7",
    }
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            r.raise_for_status()
            html = r.text
    except Exception:
        return ""
    # Look for product card image patterns. tinko.ru typically uses <img ... src="/upload/...">
    # Try multiple patterns to be resilient
    patterns = [
        r'<a[^>]+class="[^"]*product[^"]*"[^>]*>\s*<img[^>]+src="([^"]+)"',
        r'<img[^>]+class="[^"]*product[^"]*"[^>]+src="([^"]+)"',
        r'<img[^>]+src="(/upload/iblock/[^"]+\.(?:jpg|jpeg|png|webp))"',
        r'data-src="(https?://[^"]+/upload/[^"]+\.(?:jpg|jpeg|png|webp))"',
        r'<img[^>]+src="(https?://[^"]+/upload/[^"]+\.(?:jpg|jpeg|png|webp))"',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            src_url = m.group(1)
            if src_url.startswith("/"):
                src_url = "https://www.tinko.ru" + src_url
            # Skip ui/spinner/placeholder icons
            if any(s in src_url.lower() for s in ("noimage", "no-image", "placeholder", "loader", "spinner")):
                continue
            return src_url
    return ""





# # VSB_IMG_OPTIMUS_V1 — dispatch image lookup by supplier


def _fetch_image_for_material(material) -> str:
    """Pick best image source based on Material.source / name."""
    name = (getattr(material, "name", "") or "").strip()
    src_field = (getattr(material, "source", "") or "").lower()
    # Optimus prices route to optimus-cctv.ru
    if "optimus" in src_field or "оптимус" in src_field or " el " in (" " + name.lower() + " "):
        img = _fetch_optimus_image(name)
        if img:
            return img
    # Anything else (or Optimus miss) — try tinko (best-effort)
    img = _fetch_tinko_image(name)
    if img:
        return img
    # Last resort — try optimus even if source isn't tagged (catches mis-labeled rows)
    return _fetch_optimus_image(name)



@router.get("/sections")
def read_sections():
    return {"sections": DEFAULT_SECTIONS}


@router.get("/materials")
def read_materials(
    q: str = Query(default=""),
    item_type: str = Query(default="all"),
    category: str = Query(default=""),
    technology: str = Query(default=""),
    megapixels: str = Query(default=""),
    price_to: Optional[float] = Query(default=None, ge=0),
    limit: int = Query(default=500, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    has_post_filters = bool(category or technology or megapixels or price_to is not None)
    if not has_post_filters:
        page, total = get_materials(db, q, item_type, limit=limit, offset=offset, return_total=True)
        return {
            "items": [material_to_dict(material) for material in page],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    fetch_limit = 50000
    rows = get_materials(db, q, item_type, limit=fetch_limit)
    rows = [material for material in rows if material_matches_category(material, category)]
    rows = filter_materials(rows, technology, megapixels, price_to)
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "items": [material_to_dict(material) for material in page],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


@router.post("/materials")
def create_material_endpoint(material: MaterialIn, db: Session = Depends(get_db)):
    created = create_material(
        db,
        material.name.strip(),
        material.unit.strip(),
        material.price,
        material.source.strip(),
        material.characteristics.strip(),
        material.item_type,
    )
    return material_to_dict(created)


# VSB_MATERIAL_CRUD_V1


@router.patch("/materials/{material_id}")
def update_material_endpoint(
    material_id: int,
    payload: MaterialUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    target = db.query(Material).filter(Material.id == material_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    data = payload.dict(exclude_unset=True)
    if "name" in data and data["name"]:
        target.name = data["name"].strip()
    if "item_type" in data and data["item_type"]:
        target.item_type = data["item_type"].strip()
    if "characteristics" in data:
        target.characteristics = (data["characteristics"] or "").strip()
    if "unit" in data:
        target.unit = (data["unit"] or "").strip()
    if "source" in data:
        target.source = (data["source"] or "").strip()
    if "price" in data and data["price"] is not None:
        target.price = float(data["price"])
    target.last_update = datetime.datetime.utcnow()
    db.commit()
    db.refresh(target)
    return material_to_dict(target)


@router.delete("/materials/{material_id}")
def delete_material_endpoint(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    target = db.query(Material).filter(Material.id == material_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    db.delete(target)
    db.commit()
    return {"status": "ok", "deleted": material_id}


@router.delete("/materials")
def clear_materials_endpoint(
    confirm: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    if confirm != "yes":
        raise HTTPException(status_code=400, detail="Подтвердите очистку каталога: ?confirm=yes")
    deleted = db.query(Material).delete()
    db.commit()
    return {"status": "ok", "deleted": int(deleted)}


@router.post("/materials/import")
async def import_materials(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Загрузите Excel-файл .xlsx или .xls")

    try:
        rows = parse_excel_workbook(file.file, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Не удалось прочитать Excel-файл") from exc

    imported, skipped = save_parsed_materials(db, rows)
    if imported == 0:
        raise HTTPException(
            status_code=422,
            detail="Не нашёл строки с названием и ценой. Проверьте, что в файле есть товарные строки и цены.",
        )
    return {"status": "ok", "imported": imported, "skipped": skipped}


@router.post("/materials/import-ai", response_model=PriceImportResult)
async def import_materials_with_ai(
    file: Optional[UploadFile] = File(default=None),
    url: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if not file and not url.strip():
        raise HTTPException(status_code=400, detail="Загрузите файл или укажите URL поставщика")

    source = url.strip() or (file.filename if file else "")
    text_content = ""
    excel_df = None

    if url.strip():
        try:
            async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
                response = await client.get(url.strip())
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=400, detail=f"Не удалось загрузить сайт поставщика: {exc}") from exc
        text_content = html_to_text(response.text)
    elif file.filename.lower().endswith((".xlsx", ".xls")):
        try:
            parsed_rows = parse_excel_workbook(file.file, source)
            if parsed_rows:
                imported, skipped = save_parsed_materials(db, parsed_rows)
                return {"status": "ok", "imported": imported, "skipped": skipped}
            file.file.seek(0)
            excel_df = pd.read_excel(file.file)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Не удалось прочитать Excel-файл") from exc
        text_content = dataframe_to_text(excel_df)
    elif file.filename.lower().endswith(".pdf"):
        text_content = await extract_pdf_text(file)
    else:
        raise HTTPException(status_code=400, detail="Поддерживаются Excel, PDF или URL поставщика")

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Не удалось получить текст прайса")

    system_prompt = (
        "Ты извлекаешь строительные материалы из прайсов поставщиков. "
        "Верни только JSON-массив без markdown. Каждый объект строго с полями: "
        "name, characteristics, unit, price, source. "
        "price должен быть числом, unit короткой единицей измерения. "
        "Не выдумывай позиции и пропускай строки без цены."
    )
    rows = call_ai_json(system_prompt, f"Источник: {source}\n\nПрайс:\n{text_content}")
    imported, skipped = save_ai_materials(db, rows, source)
    if imported == 0 and excel_df is not None:
        imported, skipped = import_excel_by_guess(db, excel_df, source)
    if imported == 0:
        parsed_count = len(rows) if isinstance(rows, list) else 0
        raise HTTPException(
            status_code=422,
            detail=(
                "AI обработал прайс, но не нашёл материалы с названием и ценой. "
                f"JSON-строк от AI: {parsed_count}, пропущено: {skipped}. "
                "Попробуйте другую модель или Excel с колонками Наименование/Цена."
            ),
        )
    return {"status": "ok", "imported": imported, "skipped": skipped}




# # VSB_BACKEND_V2 — tinko.ru image lookup


@router.post("/materials/{material_id}/fetch-image")
def fetch_material_image(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    target = db.query(Material).filter(Material.id == material_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    img = _fetch_image_for_material(target)
    if not img:
        return {"status": "not_found", "image_url": ""}
    target.image_url = img
    db.commit()
    return {"status": "ok", "image_url": img}


@router.post("/materials/fetch-images-bulk")
def fetch_images_bulk(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin_user(user)
    # Pick materials with empty image_url
    rows = db.query(Material).filter(
        (Material.image_url == None) | (Material.image_url == "")  # noqa: E711
    ).limit(limit).all()
    found = 0
    failed = 0
    for mat in rows:
        img = _fetch_image_for_material(mat)
        if img:
            mat.image_url = img
            found += 1
        else:
            failed += 1
    db.commit()
    return {"status": "ok", "processed": len(rows), "found": found, "failed": failed}

