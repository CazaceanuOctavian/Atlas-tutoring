from httpx import AsyncClient, ASGITransport

from main import create_app


async def test_health_check():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
