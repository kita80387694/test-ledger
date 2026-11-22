from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, Enum as SAEnum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Role(str, Enum):
    ADMIN = "admin"
    TESTER = "tester"
    VIEWER = "viewer"


class Result(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


class DefectStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


def enum_column(enum_class: type[Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role, "ck_users_role"))


class TestPlan(Base):
    __tablename__ = "test_plans"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (Index("ix_executions_plan_result_id", "plan_id", "result", "id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("test_plans.id"))
    case_key: Mapped[str] = mapped_column(String(80))
    result: Mapped[Result] = mapped_column(enum_column(Result, "ck_executions_result"))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Defect(Base):
    __tablename__ = "defects"
    __table_args__ = (Index("ix_defects_execution_status_id", "execution_id", "status", "id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(ForeignKey("executions.id"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[DefectStatus] = mapped_column(
        enum_column(DefectStatus, "ck_defects_status"), default=DefectStatus.OPEN, server_default="open"
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
