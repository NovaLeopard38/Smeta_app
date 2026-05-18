from fastapi import APIRouter, Depends

from auth import get_current_user, require_admin_user
from database import engine
from models import User
from schemas import SiteSettingsIn

router = APIRouter()


def _ensure_site_settings_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        defaults = {
            "company_name": "\u0412\u0421\u041139 \u2014 \u0412\u0430\u0448\u0430 \u0421\u0438\u0441\u0442\u0435\u043c\u0430 \u0411\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u043e\u0441\u0442\u0438",
            "phone":        "+7 (4012) 55-55-55",
            "email":        "info@vsb39.ru",
            "address":      "\u0433. \u041a\u0430\u043b\u0438\u043d\u0438\u043d\u0433\u0440\u0430\u0434",
            "ya_maps_key":  "",
            "ya_maps_coords": "54.7104,20.5128",
            "ya_metrika_id":"89149915",
            "ga_id":        "",
            "ya_webmaster":"",
            "gsc_token":    "",
            "calltouch":    "",
            "inn":          "3912345678",
        }
        for k, v in defaults.items():
            conn.exec_driver_sql(
                "INSERT INTO site_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                (k, v),
            )


_ensure_site_settings_schema()

# Whitelist of allowed keys (consolidated from all sections of original app.py)
_SITE_KEYS = {
    "company_name", "phone", "email", "address", "inn",
    "ya_maps_key", "ya_maps_coords", "ya_metrika_id", "ga_id",
    "ya_webmaster", "gsc_token", "calltouch",
    "og_image_default", "twitter_handle", "geo_lat", "geo_lng",
    "opening_hours", "robots_txt", "base_url",
    "tinkoff_api_key", "tinkoff_secret_key", "tinkoff_voice",
    "tinkoff_endpoint", "tts_provider", "tts_model", "tts_voice",
}


@router.get("/site/settings")
def get_site_settings():
    """Public. API keys are returned as they are visible on the frontend anyway."""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("SELECT key, value FROM site_settings").fetchall()
    return {r[0]: r[1] for r in rows}


@router.post("/site/settings")
def save_site_settings(body: SiteSettingsIn, user: User = Depends(get_current_user)):
    require_admin_user(user)
    payload = body.settings or {}
    saved = {}
    with engine.begin() as conn:
        for k, v in payload.items():
            if k not in _SITE_KEYS:
                continue
            v = str(v if v is not None else "")[:2000]
            conn.exec_driver_sql(
                "INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
                (k, v),
            )
            saved[k] = v
    return {"status": "ok", "saved": saved}
