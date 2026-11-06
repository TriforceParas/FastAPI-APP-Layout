"""initial schema

Table names follow .claude/skills/db-naming-conventions/SKILL.md.

Revision ID: 0001
Revises:
Create Date: 2026-11-05 23:46:06.270773
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.models

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # aud_: audit trail
    op.create_table(
        "aud_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("actor_email", sa.String(length=254), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aud_event", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("idx_aud_event_action"), ["action"], unique=False)
        batch_op.create_index(batch_op.f("idx_aud_event_actor_id"), ["actor_id"], unique=False)
        batch_op.create_index(batch_op.f("idx_aud_event_created_at"), ["created_at"], unique=False)

    # cfg_: configuration
    op.create_table(
        "cfg_system_flag",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flag_key", sa.String(length=64), nullable=False),
        sa.Column("flag_value", sa.String(length=255), nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flag_key", name=op.f("uq_cfg_system_flag_flag_key")),
    )
    # md_: master data
    op.create_table(
        "md_screen",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_screen_id", sa.Integer(), nullable=True),
        sa.Column("screen_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_screen_id"], ["md_screen.id"], name=op.f("fk_md_screen_parent_screen_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path", name=op.f("uq_md_screen_path")),
        sa.UniqueConstraint("screen_key", name=op.f("uq_md_screen_screen_key")),
    )
    with op.batch_alter_table("md_screen", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("idx_md_screen_parent_screen_id"), ["parent_screen_id"], unique=False)

    # md_: master data
    op.create_table(
        "md_user",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("mfa_method", sa.String(length=10), nullable=True),
        sa.Column("mfa_secret_encrypted", sa.String(length=255), nullable=True),
        sa.Column("mfa_totp_last_step", sa.Integer(), nullable=True),
        sa.Column("mfa_recovery_hashes", sa.JSON(), nullable=True),
        sa.Column("mfa_enabled_at", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name=op.f("uq_md_user_email")),
    )
    # md_: master data
    op.create_table(
        "md_role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("default_screen_id", sa.Integer(), nullable=True),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["default_screen_id"], ["md_screen.id"], name=op.f("fk_md_role_default_screen_id"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name=op.f("uq_md_role_name")),
    )
    # txn_: transaction data
    op.create_table(
        "txn_mfa_challenge",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("secret_encrypted", sa.String(length=255), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sends", sa.Integer(), nullable=False),
        sa.Column("last_sent_at", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("expires_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["md_user.id"], name=op.f("fk_txn_mfa_challenge_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name=op.f("uq_txn_mfa_challenge_token_hash")),
    )
    with op.batch_alter_table("txn_mfa_challenge", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("idx_txn_mfa_challenge_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("idx_txn_mfa_challenge_user_id"), ["user_id"], unique=False)

    # txn_: transaction data
    op.create_table(
        "txn_password_reset",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("used_at", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["md_user.id"], name=op.f("fk_txn_password_reset_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name=op.f("uq_txn_password_reset_token_hash")),
    )
    with op.batch_alter_table("txn_password_reset", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("idx_txn_password_reset_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("idx_txn_password_reset_user_id"), ["user_id"], unique=False)

    # md_: external sign-in identities (Microsoft) linked to users
    op.create_table(
        "md_user_identity",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("last_login_at", app.db.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["md_user.id"], name=op.f("fk_md_user_identity_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "tenant_id", "subject", name=op.f("uq_md_user_identity_provider_tenant_id_subject")
        ),
        sa.UniqueConstraint("user_id", "provider", name=op.f("uq_md_user_identity_user_id_provider")),
    )
    with op.batch_alter_table("md_user_identity", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("idx_md_user_identity_user_id"), ["user_id"], unique=False)

    # txn_: transaction data
    op.create_table(
        "txn_user_session",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("last_seen_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("expires_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["md_user.id"], name=op.f("fk_txn_user_session_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name=op.f("uq_txn_user_session_token_hash")),
    )
    with op.batch_alter_table("txn_user_session", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("idx_txn_user_session_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("idx_txn_user_session_user_id"), ["user_id"], unique=False)

    # map_: role <-> screen permissions
    op.create_table(
        "map_role_screen",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("screen_id", sa.Integer(), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=False),
        sa.Column("can_write", sa.Boolean(), nullable=False),
        sa.CheckConstraint("NOT can_write OR can_read", name=op.f("ck_map_role_screen_write_requires_read")),
        sa.ForeignKeyConstraint(
            ["role_id"], ["md_role.id"], name=op.f("fk_map_role_screen_role_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["screen_id"], ["md_screen.id"], name=op.f("fk_map_role_screen_screen_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "screen_id", name=op.f("uq_map_role_screen_role_id_screen_id")),
    )
    # map_: user <-> role
    op.create_table(
        "map_user_role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["role_id"], ["md_role.id"], name=op.f("fk_map_user_role_role_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["md_user.id"], name=op.f("fk_map_user_role_user_id"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name=op.f("uq_map_user_role_user_id_role_id")),
        sa.UniqueConstraint("user_id", "sort_order", name=op.f("uq_map_user_role_user_id_sort_order")),
    )


def downgrade() -> None:
    op.drop_table("map_user_role")
    op.drop_table("map_role_screen")
    with op.batch_alter_table("txn_user_session", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("idx_txn_user_session_user_id"))
        batch_op.drop_index(batch_op.f("idx_txn_user_session_expires_at"))

    op.drop_table("txn_user_session")
    with op.batch_alter_table("md_user_identity", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("idx_md_user_identity_user_id"))

    op.drop_table("md_user_identity")
    with op.batch_alter_table("txn_password_reset", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("idx_txn_password_reset_user_id"))
        batch_op.drop_index(batch_op.f("idx_txn_password_reset_expires_at"))

    op.drop_table("txn_password_reset")
    with op.batch_alter_table("txn_mfa_challenge", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("idx_txn_mfa_challenge_user_id"))
        batch_op.drop_index(batch_op.f("idx_txn_mfa_challenge_expires_at"))

    op.drop_table("txn_mfa_challenge")
    op.drop_table("md_role")
    op.drop_table("md_user")
    with op.batch_alter_table("md_screen", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("idx_md_screen_parent_screen_id"))

    op.drop_table("md_screen")
    op.drop_table("cfg_system_flag")
    with op.batch_alter_table("aud_event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("idx_aud_event_created_at"))
        batch_op.drop_index(batch_op.f("idx_aud_event_actor_id"))
        batch_op.drop_index(batch_op.f("idx_aud_event_action"))

    op.drop_table("aud_event")
