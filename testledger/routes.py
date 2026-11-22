from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from testledger import service
from testledger.errors import documented_errors
from testledger.schemas import (
    DefectCreate, DefectUpdate, DefectView, ExecutionCreate, ExecutionView,
    Page, PlanCreate, PlanSummary, PlanView,
)
from testledger.security import CurrentUser, Database, Writer

router = APIRouter(responses=documented_errors(401, 422))
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post("/plans", tags=["plans"], response_model=PlanView, status_code=201,
             responses=documented_errors(403))
def create_plan(data: PlanCreate, db: Database, user: Writer):
    return service.create_plan(db, data, user)


@router.get("/plans/{plan_id}/summary", tags=["plans"], response_model=PlanSummary,
            responses=documented_errors(404))
def plan_summary(plan_id: UUID, db: Database, _user: CurrentUser):
    return service.summarize_plan(db, plan_id)


@router.post("/plans/{plan_id}/executions", tags=["executions"], response_model=ExecutionView,
             status_code=201, responses=documented_errors(403, 404))
def record_execution(plan_id: UUID, data: ExecutionCreate, db: Database, user: Writer):
    return service.record_execution(db, plan_id, data, user)


@router.get("/plans/{plan_id}/failed-executions", tags=["executions"],
            response_model=Page[ExecutionView], responses=documented_errors(404))
def failed_executions(
    plan_id: UUID, db: Database, _user: CurrentUser, offset: Offset = 0, limit: Limit = 20
):
    rows = service.list_failed_executions(db, plan_id, offset, limit + 1)
    return {"items": rows[:limit], "offset": offset, "limit": limit, "has_more": len(rows) > limit}


@router.post("/executions/{execution_id}/defects", tags=["defects"], response_model=DefectView,
             status_code=201, responses=documented_errors(403, 404, 409))
def create_defect(execution_id: UUID, data: DefectCreate, db: Database, user: Writer):
    return service.create_defect(db, execution_id, data, user)


@router.patch("/defects/{defect_id}/status", tags=["defects"], response_model=DefectView,
              responses=documented_errors(403, 404, 409))
def update_defect_status(defect_id: UUID, data: DefectUpdate, db: Database, user: Writer):
    return service.change_defect_status(db, defect_id, data.status, user)


@router.get("/plans/{plan_id}/open-defects", tags=["defects"], response_model=Page[DefectView],
            responses=documented_errors(404))
def open_defects(
    plan_id: UUID, db: Database, _user: CurrentUser, offset: Offset = 0, limit: Limit = 20
):
    rows = service.list_open_defects(db, plan_id, offset, limit + 1)
    return {"items": rows[:limit], "offset": offset, "limit": limit, "has_more": len(rows) > limit}
