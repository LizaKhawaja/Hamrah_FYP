"""Merge heads and add missing columns

Revision ID: merge001
Revises: 10266d83314f, c3f1a2b4d5e6
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge001'
down_revision = ('10266d83314f', 'c3f1a2b4d5e6')
branch_labels = None
depends_on = None


def upgrade():
    # Add status column to rides if not exists
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='rides' AND column_name='status'"
    ))
    if not result.fetchone():
        op.add_column('rides', sa.Column('status', sa.String(20), server_default='active'))

    # Add pickup_lat/lng to ride_requests if not exists
    for col in ['pickup_lat', 'pickup_lng']:
        result = conn.execute(sa.text(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name='ride_requests' AND column_name='{col}'"
        ))
        if not result.fetchone():
            op.add_column('ride_requests', sa.Column(col, sa.Float(), nullable=True))


def downgrade():
    pass
