from fastapi import FastAPI
from sqlalchemy import text

from testledger.db import get_session_factory

app = FastAPI(title="TestLedger", version="1.0.0")


@app.get("/health", tags=["system"])
def health():
    with get_session_factory()() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok"}
