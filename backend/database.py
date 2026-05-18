
import os

from sqlalchemy import Column as _Col, String as _Str, create_engine, text
from sqlalchemy.orm import sessionmaker

from models import Base, Material

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smeta.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# VSB_BACKEND_V2 — attach image_url column to Material at runtime
if not hasattr(Material, 'image_url'):
    try:
        Material.image_url = _Col('image_url', _Str, default='')
    except Exception:
        pass


def ensure_schema():
    # VSB_BACKEND_V2 materials.image_url
    try:
        with engine.begin() as conn:
            cols = conn.exec_driver_sql("PRAGMA table_info(materials)").fetchall()
            if not any(c[1] == 'image_url' for c in cols):
                conn.exec_driver_sql("ALTER TABLE materials ADD COLUMN image_url TEXT DEFAULT ''")
    except Exception as _e:
        import logging as _lg; _lg.warning('image_url migration skipped: %s', _e)
    with engine.begin() as conn:
        tables = {
            "materials": ["characteristics", "item_type"],
            "works": ["characteristics"],
            "smeta_items": ["characteristics", "section", "base_unit_price"],
            "smetas": [
                "parent_id",
                "owner_id",
                "customer_name",
                "customer_details",
                "contractor_name",
                "contractor_details",
                "approver_name",
                "approver_details",
                "tax_mode",
                "tax_rate",
                "section_adjustments",
            ],
        }
        for table_name, columns in tables.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})"))}
            for column in columns:
                if column not in existing:
                    column_type = "FLOAT" if column in {"base_unit_price"} else "VARCHAR"
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column} {column_type}"))
        conn.execute(
            text(
                "UPDATE materials SET item_type = CASE "
                "WHEN lower(coalesce(source, '')) LIKE '%работ%' "
                "OR lower(coalesce(name, '')) LIKE 'монтаж %' "
                "OR coalesce(name, '') LIKE 'Монтаж %' "
                "OR lower(coalesce(name, '')) LIKE 'демонтаж %' "
                "OR coalesce(name, '') LIKE 'Демонтаж %' "
                "OR lower(coalesce(name, '')) LIKE 'прокладка %' "
                "OR coalesce(name, '') LIKE 'Прокладка %' "
                "OR lower(coalesce(name, '')) LIKE 'установка %' "
                "OR coalesce(name, '') LIKE 'Установка %' "
                "OR lower(coalesce(name, '')) LIKE 'настройка %' "
                "OR coalesce(name, '') LIKE 'Настройка %' "
                "OR lower(coalesce(name, '')) LIKE 'подключение %' "
                "OR coalesce(name, '') LIKE 'Подключение %' "
                "OR coalesce(name, '') LIKE 'Аренда вышки%' "
                "THEN 'work' ELSE 'equipment' END"
            )
        )
        conn.execute(
            text(
                "UPDATE smeta_items SET base_unit_price = unit_price "
                "WHERE base_unit_price IS NULL"
            )
        )


ensure_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
