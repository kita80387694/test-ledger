from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from testledger.auth import router as auth_router
from testledger.errors import LedgerError, documented_errors, register_error_handlers
from testledger.routes import router
from testledger.security import Database

app = FastAPI(title="TestLedger", version="1.0.0")
register_error_handlers(app)
app.include_router(auth_router)
app.include_router(router)


@app.get("/health", tags=["system"], responses=documented_errors(503))
def health(db: Database):
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        raise LedgerError(503, "database_unavailable", "Database is unavailable.") from None
    return {"status": "ok"}
