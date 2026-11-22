from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import Session

from testledger.errors import LedgerError
from testledger.models import Defect, DefectStatus, Execution, Result, Role, TestPlan, User
from testledger.schemas import DefectCreate, ExecutionCreate, PlanCreate, PlanSummary

TRANSITIONS = {
    DefectStatus.OPEN: {DefectStatus.IN_PROGRESS},
    DefectStatus.IN_PROGRESS: {DefectStatus.RESOLVED},
    DefectStatus.RESOLVED: {DefectStatus.IN_PROGRESS, DefectStatus.CLOSED},
    DefectStatus.CLOSED: {DefectStatus.IN_PROGRESS},
}


def get_plan(db: Session, plan_id: UUID) -> TestPlan:
    plan = db.get(TestPlan, plan_id)
    if plan is None:
        raise LedgerError(404, "plan_not_found", "Test plan not found.")
    return plan


def create_plan(db: Session, data: PlanCreate, user: User) -> TestPlan:
    plan = TestPlan(**data.model_dump(), created_by=user.id)
    db.add(plan)
    db.commit()
    return plan


def record_execution(db: Session, plan_id: UUID, data: ExecutionCreate, user: User) -> Execution:
    get_plan(db, plan_id)
    execution = Execution(**data.model_dump(), plan_id=plan_id, created_by=user.id)
    db.add(execution)
    db.commit()
    return execution


def create_defect(db: Session, execution_id: UUID, data: DefectCreate, user: User) -> Defect:
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise LedgerError(404, "execution_not_found", "Execution not found.")
    if execution.result != Result.FAILED:
        raise LedgerError(409, "execution_not_failed", "Only failed executions can have defects.")

    defect = Defect(**data.model_dump(), execution_id=execution_id, created_by=user.id)
    db.add(defect)
    db.commit()
    return defect


def change_defect_status(db: Session, defect_id: UUID, status: DefectStatus, user: User) -> Defect:
    # Serialize concurrent updates so each transition uses the latest stored status.
    defect = db.scalar(select(Defect).where(Defect.id == defect_id).with_for_update())
    if defect is None:
        raise LedgerError(404, "defect_not_found", "Defect not found.")
    if status not in TRANSITIONS[defect.status]:
        raise LedgerError(409, "invalid_transition", f"Cannot move {defect.status.value} to {status.value}.")
    if defect.status == DefectStatus.CLOSED and user.role != Role.ADMIN:
        raise LedgerError(403, "forbidden", "Only admins can reopen a closed defect.")

    defect.status = status
    db.commit()
    return defect


def summarize_plan(db: Session, plan_id: UUID) -> PlanSummary:
    # Filter in the outer joins so an empty plan or a failure with no open defects remains in the result.
    statement = (
        select(
            TestPlan,
            func.count(distinct(Execution.id)).label("failed_execution_count"),
            func.count(Defect.id).label("open_defect_count"),
        )
        .outerjoin(Execution, and_(Execution.plan_id == TestPlan.id, Execution.result == Result.FAILED))
        .outerjoin(Defect, and_(Defect.execution_id == Execution.id, Defect.status != DefectStatus.CLOSED))
        .where(TestPlan.id == plan_id)
        .group_by(TestPlan.id)
    )
    row = db.execute(statement).one_or_none()
    if row is None:
        raise LedgerError(404, "plan_not_found", "Test plan not found.")
    plan, failed, open_defects = row
    return PlanSummary(
        id=plan.id, name=plan.name, description=plan.description, created_by=plan.created_by,
        created_at=plan.created_at, failed_execution_count=failed, open_defect_count=open_defects,
    )


def list_failed_executions(
    db: Session, plan_id: UUID, offset: int, limit: int
) -> Sequence[Execution]:
    get_plan(db, plan_id)
    statement = (
        select(Execution)
        .where(Execution.plan_id == plan_id, Execution.result == Result.FAILED)
        .order_by(Execution.id)
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(statement).all()


def open_defects_query(plan_id: UUID):
    return (
        select(Defect)
        .join(Execution, Defect.execution_id == Execution.id)
        .where(Execution.plan_id == plan_id, Defect.status != DefectStatus.CLOSED)
        .order_by(Defect.id)
    )


def list_open_defects(db: Session, plan_id: UUID, offset: int, limit: int) -> Sequence[Defect]:
    get_plan(db, plan_id)
    return db.scalars(open_defects_query(plan_id).offset(offset).limit(limit)).all()
