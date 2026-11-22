import httpx


def demo_http_client(base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=10.0, trust_env=False)


async def login(http: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
    response = await http.post(
        "/auth/token", data={"grant_type": "password", "username": username, "password": password}
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
