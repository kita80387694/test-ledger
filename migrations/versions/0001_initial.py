"""Create users, test plans, executions and defects."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(6), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'tester', 'viewer')", name="ck_users_role"),
    )
    op.create_table(
        "test_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_test_plans_created_by", "test_plans", ["created_by"])
    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("test_plans.id"), nullable=False),
        sa.Column("case_key", sa.String(80), nullable=False),
        sa.Column("result", sa.String(6), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("result IN ('passed', 'failed')", name="ck_executions_result"),
    )
    op.create_index("ix_executions_created_by", "executions", ["created_by"])
    op.create_index("ix_executions_plan_result_id", "executions", ["plan_id", "result", "id"])
    op.create_table(
        "defects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("execution_id", sa.Uuid(), sa.ForeignKey("executions.id"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(11), server_default="open", nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')", name="ck_defects_status"
        ),
    )
    op.create_index("ix_defects_created_by", "defects", ["created_by"])
    op.create_index("ix_defects_execution_status_id", "defects", ["execution_id", "status", "id"])


def downgrade() -> None:
    op.drop_table("defects")
    op.drop_table("executions")
    op.drop_table("test_plans")
    op.drop_table("users")
