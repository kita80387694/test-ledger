from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from testledger.config import get_auth_settings
from testledger.db import get_db
from testledger.errors import LedgerError
from testledger.models import Role, User

JWT_ISSUER = "test-ledger"
JWT_ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)
Database = Annotated[Session, Depends(get_db)]


def unauthorized(message: str = "A valid bearer token is required.") -> LedgerError:
    return LedgerError(401, "unauthorized", message, {"WWW-Authenticate": "Bearer"})


def current_user(db: Database, token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    if not token:
        raise unauthorized()
    try:
        claims = jwt.decode(
            token,
            get_auth_settings().jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["sub", "iat", "exp", "iss"]},
        )
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized() from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_writer(user: CurrentUser) -> User:
    if user.role not in {Role.ADMIN, Role.TESTER}:
        raise LedgerError(403, "forbidden", "This role cannot write test data.")
    return user


Writer = Annotated[User, Depends(require_writer)]
