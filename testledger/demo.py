import asyncio
import sys
from datetime import timedelta
from uuid import uuid4

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from testledger.config import DemoSettings
from testledger.demo_http import demo_http_client, login


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def expect(
    http: httpx.AsyncClient, method: str, path: str, status: int = 200, **kwargs
) -> dict:
    response = await http.request(method, path, **kwargs)
    require(
        response.status_code == status,
        f"{method} {path} returned {response.status_code}, expected {status}: {response.text}",
    )
    return response.json()


async def create_plan(http, headers, name, defect_titles):
    plan = await expect(http, "POST", "/plans", 201, headers=headers, json={"name": name})
    execution = await expect(
        http, "POST", f"/plans/{plan['id']}/executions", 201,
        headers=headers, json={"case_key": "DEMO-001", "result": "failed"},
    )
    ids = []
    for title in defect_titles:
        defect = await expect(
            http, "POST", f"/executions/{execution['id']}/defects", 201,
            headers=headers, json={"title": title},
        )
        require(defect["status"] == "open", "A new defect must start open.")
        ids.append(defect["id"])
    return plan["id"], execution["id"], ids


async def check_http_state(http, viewer, plan, failed, expected):
    summary = await expect(http, "GET", f"/plans/{plan}/summary", headers=viewer)
    counts = (summary["failed_execution_count"], summary["open_defect_count"])
    require(counts == (1, len(expected)), f"Wrong counts for {plan}: {counts}")
    failures = await expect(http, "GET", f"/plans/{plan}/failed-executions", headers=viewer)
    require([item["id"] for item in failures["items"]] == [failed], "Unexpected failed execution IDs.")
    defects = await expect(http, "GET", f"/plans/{plan}/open-defects", headers=viewer)
    actual = sorted(item["id"] for item in defects["items"])
    require(actual == sorted(expected), f"Unexpected HTTP defect IDs for {plan}: {actual}")


async def close_defect(http, tester, defect_id):
    for status in ("in_progress", "resolved", "closed"):
        defect = await expect(
            http, "PATCH", f"/defects/{defect_id}/status", headers=tester, json={"status": status},
        )
        require(defect["status"] == status, f"Expected status {status} for {defect_id}.")


async def check_mcp_state(session: ClientSession, plan: str, expected: list[str]) -> None:
    result = await session.call_tool("list_open_defects", {"plan_id": plan})
    data = result.structuredContent
    if result.isError or data is None:
        raise AssertionError(f"MCP list_open_defects failed: {result.content}")
    require(data["plan_id"] == plan, f"MCP returned the wrong plan: {data['plan_id']}")
    actual = sorted(item["id"] for item in data["items"])
    require(actual == sorted(expected), f"Unexpected MCP defect IDs for {plan}: {actual}")


def report(message: str) -> None:
    print(message, flush=True)


async def run() -> None:
    settings = DemoSettings()
    base_url = str(settings.demo_base_url)
    viewer_password = settings.demo_viewer_password.get_secret_value()
    run_id = uuid4().hex
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "testledger.mcp_server"],
        env={"DEMO_BASE_URL": base_url, "DEMO_VIEWER_PASSWORD": viewer_password},
    )
    async with demo_http_client(base_url=base_url) as http:
        tester = await login(http, "tester", settings.demo_tester_password.get_secret_value())
        plan, failed, defects = await create_plan(
            http, tester, f"Demo checkout {run_id}", ["Incorrect checkout total", "Missing tax line"],
        )
        other, other_failed, other_defects = await create_plan(
            http, tester, f"Demo search {run_id}", ["Search results are missing"],
        )
        report(f"[1/6] Created plans {plan} and {other}; primary failed execution {failed}.")

        viewer = await login(http, "viewer", viewer_password)
        await check_http_state(http, viewer, plan, failed, defects)
        await check_http_state(http, viewer, other, other_failed, other_defects)
        report(f"[2/6] HTTP counts (1 failed, 2 open); exact defect IDs {defects}.")

        denied = await expect(
            http, "POST", "/plans", 403, headers=viewer, json={"name": f"Forbidden {run_id}"},
        )
        require(denied["error"]["code"] == "forbidden", "Expected the role-based denial.")
        report("[3/6] Viewer write denied with HTTP 403.")

        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                require([tool.name for tool in tools] == ["list_open_defects"], "Unexpected MCP tools.")
                annotations = tools[0].annotations
                require(
                    annotations is not None and annotations.readOnlyHint is True,
                    "Expected the MCP tool to advertise read-only access.",
                )
                await check_mcp_state(session, plan, defects)
                report("[4/6] MCP stdio discovered list_open_defects and matched both primary defect IDs.")

                await close_defect(http, tester, defects[0])
                await check_http_state(http, viewer, plan, failed, defects[1:])
                await check_mcp_state(session, plan, defects[1:])
                report(f"[5/6] HTTP counts (1 failed, 1 open); HTTP and MCP matched ID {defects[1]}.")

                await close_defect(http, tester, defects[1])
                await check_http_state(http, viewer, plan, failed, [])
                await check_mcp_state(session, plan, [])
                await check_http_state(http, viewer, other, other_failed, other_defects)
                await check_mcp_state(session, other, other_defects)
                report("[6/6] HTTP and MCP agree on 0 open; failure retained and other plan unaffected.")
    report(f"PASS {run_id}")


if __name__ == "__main__":
    asyncio.run(run())
