"""ratings table created

Revision ID: c3f1a2b4d5e6
Revises: b54bc9785c75
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3f1a2b4d5e6'
down_revision: Union[str, Sequence[str], None] = 'b54bc9785c75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ratings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ride_id', sa.Integer(), nullable=False),
        sa.Column('passenger_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('stars', sa.Integer(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('review', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['users.id']),
        sa.ForeignKeyConstraint(['passenger_id'], ['users.id']),
        sa.ForeignKeyConstraint(['ride_id'], ['rides.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ride_id', 'passenger_id', name='uq_rating_ride_passenger'),
    )
    op.create_index(op.f('ix_ratings_id'), 'ratings', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ratings_id'), table_name='ratings')
    op.drop_table('ratings')
