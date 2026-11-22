from uuid import UUID

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from testledger.config import DemoHTTPSettings
from testledger.demo_http import demo_http_client, login
from testledger.schemas import DefectSummary, Page

mcp = FastMCP("TestLedger", log_level="WARNING")


class OpenDefects(BaseModel):
    plan_id: UUID
    items: list[DefectSummary]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def list_open_defects(plan_id: UUID) -> OpenDefects:
    """List a test plan's defects whose status is not closed."""
    settings = DemoHTTPSettings()
    defects: list[DefectSummary] = []
    offset, limit = 0, 100
    async with demo_http_client(base_url=str(settings.demo_base_url)) as http:
        try:
            # The HTTP endpoint owns the query and authorization. This process uses the viewer account.
            headers = await login(http, "viewer", settings.demo_viewer_password.get_secret_value())
            while True:
                response = await http.get(
                    f"/plans/{plan_id}/open-defects",
                    headers=headers, params={"offset": offset, "limit": limit},
                )
                if response.status_code == 404:
                    raise ToolError("Test plan not found.")
                response.raise_for_status()
                page = Page[DefectSummary].model_validate(response.json())
                defects.extend(page.items)
                if not page.has_more:
                    return OpenDefects(plan_id=plan_id, items=defects)
                offset += limit
        except httpx.HTTPError as exc:
            raise ToolError("Cannot query TestLedger with the demo viewer account.") from exc


if __name__ == "__main__":
    mcp.run(transport="stdio")
