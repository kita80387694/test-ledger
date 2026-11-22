from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from testledger.auth import password_hash
from testledger.config import DemoSeedSettings
from testledger.db import get_session_factory
from testledger.models import Defect, Execution, Result, Role, TestPlan, User


def demo_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"test-ledger/local-seed/{name}")


def seed_account(db: Session, role: Role, password: str) -> UUID:
    user = db.scalar(select(User).where(User.username == role.value))
    if user is not None and user.role == role and password_hash.verify(password, user.password_hash):
        return user.id

    statement = insert(User).values(
        username=role.value, password_hash=password_hash.hash(password), role=role
    )
    return db.execute(
        statement.on_conflict_do_update(
            index_elements=[User.username],
            set_={"password_hash": statement.excluded.password_hash, "role": statement.excluded.role},
        ).returning(User.id)
    ).scalar_one()


def seed_demo(db: Session, settings: DemoSeedSettings) -> UUID:
    seed_account(db, Role.ADMIN, settings.demo_admin_password.get_secret_value())
    tester_id = seed_account(db, Role.TESTER, settings.demo_tester_password.get_secret_value())
    seed_account(db, Role.VIEWER, settings.demo_viewer_password.get_secret_value())

    plan_id = demo_id("plan")
    execution_id = demo_id("execution")
    db.execute(
        insert(TestPlan).values(id=plan_id, name="Sample checkout plan", created_by=tester_id)
        .on_conflict_do_nothing(index_elements=[TestPlan.id])
    )
    db.execute(
        insert(Execution).values(
            id=execution_id, plan_id=plan_id, case_key="CHECKOUT-001",
            result=Result.FAILED, created_by=tester_id,
        ).on_conflict_do_nothing(index_elements=[Execution.id])
    )
    db.execute(
        insert(Defect).values(
            id=demo_id("defect"), execution_id=execution_id,
            title="Checkout total is missing", created_by=tester_id,
        ).on_conflict_do_nothing(index_elements=[Defect.id])
    )
    return plan_id


def main() -> None:
    settings = DemoSeedSettings()
    with get_session_factory()() as db, db.begin():
        plan_id = seed_demo(db, settings)
    print(f"Demo accounts and sample data are ready. Sample plan ID: {plan_id}")


if __name__ == "__main__":
    main()
