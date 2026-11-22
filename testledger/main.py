from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from testledger.auth import router as auth_router
from testledger.errors import documented_errors, register_error_handlers
from testledger.routes import router
from testledger.security import Database

swagger_assets = Path(__file__).resolve().parents[1] / "swagger-ui"
bundled_swagger = swagger_assets.is_dir()
app = FastAPI(
    title="TestLedger", version="1.0.0", docs_url=None if bundled_swagger else "/docs", redoc_url=None
)
register_error_handlers(app)
app.include_router(auth_router)
app.include_router(router)


if bundled_swagger:
    app.mount("/swagger-ui", StaticFiles(directory=swagger_assets), name="swagger_ui")

    @app.get("/docs", include_in_schema=False)
    def docs(request: Request):
        root = request.scope.get("root_path", "").rstrip("/")
        return get_swagger_ui_html(
            openapi_url=f"{root}/openapi.json",
            title="TestLedger · Swagger UI",
            swagger_js_url=f"{root}/swagger-ui/swagger-ui-bundle.js",
            swagger_css_url=f"{root}/swagger-ui/swagger-ui.css",
            swagger_favicon_url=f"{root}/swagger-ui/favicon-32x32.png",
            swagger_ui_parameters={"validatorUrl": None},
        )


@app.get("/health", tags=["system"], responses=documented_errors(503))
def health(db: Database):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
