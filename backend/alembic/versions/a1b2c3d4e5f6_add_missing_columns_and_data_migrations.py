"""add missing columns and data migrations

Revision ID: a1b2c3d4e5f6
Revises: 3401b35703e5
Create Date: 2026-05-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3401b35703e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add materials.image_url column and run data migrations."""
    # Add image_url column (the only column not in the initial migration)
    try:
        op.add_column('materials', sa.Column('image_url', sa.Text(), server_default=''))
    except Exception:
        # Column may already exist in an existing database
        pass

    # Data migration: classify materials as work or equipment based on name/source
    op.execute(
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

    # Data migration: backfill base_unit_price from unit_price where missing
    op.execute(
        "UPDATE smeta_items SET base_unit_price = unit_price "
        "WHERE base_unit_price IS NULL"
    )


def downgrade() -> None:
    """Remove materials.image_url column."""
    try:
        op.drop_column('materials', 'image_url')
    except Exception:
        pass
