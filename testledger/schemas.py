from datetime import datetime
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from testledger.models import DefectStatus, Result


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def reject_nul_characters(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text must not contain NUL characters.")
        return value


class PlanCreate(Input):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    description: Annotated[str, StringConstraints(max_length=4000)] = ""


class ExecutionCreate(Input):
    case_key: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result: Result
    notes: Annotated[str, StringConstraints(max_length=4000)] = ""


class DefectCreate(Input):
    title: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    description: Annotated[str, StringConstraints(max_length=4000)] = ""


class DefectUpdate(Input):
    status: DefectStatus


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by: UUID
    created_at: datetime


class PlanView(Record):
    name: str
    description: str


class PlanSummary(PlanView):
    failed_execution_count: int
    open_defect_count: int


class ExecutionView(Record):
    plan_id: UUID
    case_key: str
    result: Result
    notes: str


class DefectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    execution_id: UUID
    title: str
    status: DefectStatus


class DefectView(DefectSummary):
    description: str
    created_by: UUID
    created_at: datetime


Item = TypeVar("Item")


class Page(BaseModel, Generic[Item]):
    items: list[Item]
    offset: int
    limit: int
    has_more: bool
