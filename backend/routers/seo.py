from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from auth import get_current_user, require_admin_user
from database import engine
from models import User
from schemas import SeoPageIn

router = APIRouter()


def _ensure_seo_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS seo_pages (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                keywords TEXT NOT NULL DEFAULT '',
                og_title TEXT NOT NULL DEFAULT '',
                og_description TEXT NOT NULL DEFAULT '',
                og_image TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT '0.8',
                changefreq TEXT NOT NULL DEFAULT 'weekly',
                indexable INTEGER NOT NULL DEFAULT 1,
                label TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        seeds = [
            ("home",    "Главная",    "ВСБ39 \u2014 Видеонаблюдение, СКУД, Охранная сигнализация в Калининграде",
             "Установка и обслуживание систем безопасности в Калининграде: видеонаблюдение, СКУД, ОС/ОТС. 313 объектов, выезд 4 часа, гарантия 6 мес.",
             "видеонаблюдение Калининград, СКУД Калининград, охранная сигнализация, монтаж камер, ВСБ39, Болид, Орион, техобслуживание ТСО",
             "1.0", "daily"),
            ("catalog", "Каталог",    "Каталог оборудования для систем безопасности \u2014 ВСБ39 Калининград",
             "IP-камеры, AHD-камеры, видеорегистраторы, СКУД, охранная сигнализация. Реальные цены, наличие, гарантия.",
             "каталог камер калининград, ip камеры, ahd камеры, регистраторы, скуд, охранная сигнализация",
             "0.9", "daily"),
            ("smeta",   "Смета",      "Калькулятор сметы видеонаблюдения и СКУД онлайн \u2014 ВСБ39",
             "Точный расч\u0451т стоимости системы безопасности под объект. Камеры, NVR, кабель, монтаж, ПНР. КП за 30 секунд.",
             "калькулятор сметы видеонаблюдение, расч\u0451т стоимости скуд, цена монтажа камер калининград",
             "0.9", "weekly"),
            ("about",   "О компании", "ВСБ39 \u2014 интегратор систем безопасности в Калининграде",
             "8+ лет опыта, 313 объектов под ТО, аттестован НПФ Болид и Орион. Калининград и область.",
             "всб39, интегратор систем безопасности, калининград, болид, орион",
             "0.7", "monthly"),
            ("support", "Поддержка",  "Тех. поддержка ВСБ39 \u2014 AI-консультант и быстрый отклик",
             "AI-консультант ответит мгновенно. Сложные вопросы \u2014 обратный звонок в течение часа.",
             "поддержка вебвсб39, помощь по видеонаблюдению",
             "0.5", "monthly"),
        ]
        for s, lbl, t, d, k, p, cf in seeds:
            conn.exec_driver_sql(
                "INSERT INTO seo_pages (slug, label, title, description, keywords, priority, changefreq) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(slug) DO NOTHING",
                (s, lbl, t, d, k, p, cf),
            )
        more_defaults = {
            "og_image_default": "https://vsb39.ru/og.jpg",
            "twitter_handle":   "",
            "geo_lat":          "54.7104",
            "geo_lng":          "20.5128",
            "opening_hours":    "Mo-Fr 09:00-18:00",
            "robots_txt":       "User-agent: *\nDisallow: /to/\nDisallow: /api/\n\nSitemap: https://vsb39.ru/sitemap.xml\n",
            "base_url":         "https://vsb39.ru",
        }
        for k, v in more_defaults.items():
            conn.exec_driver_sql(
                "INSERT INTO site_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                (k, v),
            )


_ensure_seo_schema()


@router.get("/seo/pages")
def list_seo_pages():
    with engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT slug, label, title, description, keywords, og_title, og_description, og_image, "
            "priority, changefreq, indexable, updated_at FROM seo_pages ORDER BY priority DESC, slug"
        ).fetchall()
    return [{
        "slug": r[0], "label": r[1] or r[0], "title": r[2], "description": r[3],
        "keywords": r[4], "og_title": r[5], "og_description": r[6], "og_image": r[7],
        "priority": r[8], "changefreq": r[9], "indexable": bool(r[10]),
        "updated_at": str(r[11]) if r[11] else None,
    } for r in rows]


@router.post("/seo/pages")
def save_seo_page(body: SeoPageIn, user: User = Depends(get_current_user)):
    require_admin_user(user)
    slug = (body.slug or "").strip().lower()[:64]
    if not slug:
        raise HTTPException(status_code=400, detail="slug \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u0435\u043d")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO seo_pages (slug, label, title, description, keywords, og_title, og_description, og_image, priority, changefreq, indexable, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(slug) DO UPDATE SET label=excluded.label, title=excluded.title, description=excluded.description, "
            "keywords=excluded.keywords, og_title=excluded.og_title, og_description=excluded.og_description, "
            "og_image=excluded.og_image, priority=excluded.priority, changefreq=excluded.changefreq, "
            "indexable=excluded.indexable, updated_at=CURRENT_TIMESTAMP",
            (slug, body.label[:80], body.title[:200], body.description[:500], body.keywords[:500],
             body.og_title[:200], body.og_description[:500], body.og_image[:500],
             body.priority[:8], body.changefreq[:16], 1 if body.indexable else 0),
        )
    return {"status": "ok", "slug": slug}


@router.delete("/seo/pages/{slug}")
def delete_seo_page(slug: str, user: User = Depends(get_current_user)):
    require_admin_user(user)
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM seo_pages WHERE slug = ?", (slug,))
    return {"status": "ok"}


@router.get("/sitemap.xml")
def sitemap_xml():
    with engine.begin() as conn:
        base = (conn.exec_driver_sql("SELECT value FROM site_settings WHERE key='base_url'").fetchone() or [""])[0] or "https://vsb39.ru"
        rows = conn.exec_driver_sql(
            "SELECT slug, priority, changefreq, updated_at FROM seo_pages WHERE indexable = 1 ORDER BY priority DESC"
        ).fetchall()
    base = base.rstrip("/")
    items = []
    for slug, pri, cf, upd in rows:
        loc = base + ("/" if slug == "home" else "/#" + slug)
        items.append(
            f"  <url>\n    <loc>{loc}</loc>\n    <changefreq>{cf}</changefreq>\n    <priority>{pri}</priority>\n  </url>"
        )
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(items) + "\n</urlset>\n"
    return Response(content=body, media_type="application/xml")


@router.get("/robots.txt")
def robots_txt():
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT value FROM site_settings WHERE key='robots_txt'").fetchone()
    txt = (row[0] if row else "") or "User-agent: *\nDisallow:\n"
    return Response(content=txt, media_type="text/plain")
