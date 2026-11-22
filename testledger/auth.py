from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordRequestFormStrict
from pwdlib import PasswordHash
from pydantic import BaseModel
from sqlalchemy import select

from testledger.errors import documented_errors
from testledger.models import User
from testledger.security import Database, issue_token, unauthorized

router = APIRouter(prefix="/auth", tags=["auth"])
password_hash = PasswordHash.recommended()


@lru_cache
def dummy_hash() -> str:
    return password_hash.hash("unused-for-authentication")


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


@router.post("/token", response_model=TokenResponse, responses=documented_errors(401, 422))
def login(
    form: Annotated[OAuth2PasswordRequestFormStrict, Depends()], db: Database, response: Response
) -> TokenResponse:
    if not (1 <= len(form.username) <= 64 and 1 <= len(form.password) <= 256) or "\x00" in form.username:
        raise unauthorized("Invalid username or password.")

    user = db.scalar(select(User).where(User.username == form.username))
    encoded = user.password_hash if user is not None else dummy_hash()
    valid = password_hash.verify(form.password, encoded)
    if user is None or not valid:
        raise unauthorized("Invalid username or password.")

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=issue_token(user.id))
