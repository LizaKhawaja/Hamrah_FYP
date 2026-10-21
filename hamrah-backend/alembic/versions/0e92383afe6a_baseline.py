"""Initial schema for core tables.

Revision ID: 0e92383afe6a
Revises:
Create Date: 2026-02-24 15:15:56.393685
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0e92383afe6a"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables required by models.py."""

    op.create_table(
        "dsu_students",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("dsu_reg_id", sa.String(length=20), nullable=False),
        sa.Column("department", sa.String(length=50), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.UniqueConstraint("dsu_reg_id", name="uq_dsu_students_dsu_reg_id"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("first_name", sa.String(length=50), nullable=False),
        sa.Column("last_name", sa.String(length=50), nullable=False),
        sa.Column("dsu_reg_id", sa.String(length=20), nullable=False),
        sa.Column("phone_number", sa.String(length=15), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("gender", sa.String(length=50), nullable=False),
        sa.Column("is_passenger", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_driver", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("role", sa.String(length=10), nullable=False, server_default="passenger"),
        sa.Column("nic_image_url", sa.Text(), nullable=True),
        sa.Column("live_image_url", sa.Text(), nullable=True),
        sa.Column("license_image_url", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("otp_code", sa.String(length=6), nullable=True),
        sa.Column("otp_expiry", sa.DateTime(), nullable=True),
        sa.Column("reset_token", sa.String(length=255), nullable=True),
        sa.Column("reset_token_expiry", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("dsu_reg_id", name="uq_users_dsu_reg_id"),
        sa.UniqueConstraint("phone_number", name="uq_users_phone_number"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_of_transport", sa.String(length=10), nullable=False),
        sa.Column("vehicle_number", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("vehicle_number", name="uq_vehicles_vehicle_number"),
    )

    op.create_table(
        "rides",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("from_address", sa.String(), nullable=False),
        sa.Column("from_lat", sa.Float(), nullable=False),
        sa.Column("from_lng", sa.Float(), nullable=False),
        sa.Column("to_address", sa.String(), nullable=False),
        sa.Column("to_lat", sa.Float(), nullable=False),
        sa.Column("to_lng", sa.Float(), nullable=False),
        sa.Column("departure_time", sa.DateTime(), nullable=False),
        sa.Column("seats_available", sa.Integer(), nullable=False),
        sa.Column("ac", sa.Boolean(), nullable=True),
        sa.Column("gender_filter", sa.String(), nullable=True, server_default="any"),
        sa.Column("fare_per_seat", sa.Float(), nullable=True, server_default="0"),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "ride_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("ride_id", sa.Integer(), sa.ForeignKey("rides.id"), nullable=False),
        sa.Column("passenger_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=True, server_default="pending"),
        sa.Column("distance_from_route", sa.Float(), nullable=True, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    """Drop all core tables (reverse order)."""

    op.drop_table("ride_requests")
    op.drop_table("rides")
    op.drop_table("vehicles")
    op.drop_table("users")
    op.drop_table("dsu_students")
