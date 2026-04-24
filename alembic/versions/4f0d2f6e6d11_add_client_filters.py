"""add client filters

Revision ID: 4f0d2f6e6d11
Revises: c99a96db36db
Create Date: 2026-04-16 16:20:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4f0d2f6e6d11"
down_revision = "c99a96db36db"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_filters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("max_price_category", sa.String(length=64), nullable=True),
        sa.Column("deadline_category", sa.String(length=64), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("client_filters")
