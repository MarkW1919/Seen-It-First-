from fastapi.testclient import TestClient

from edge.api.app import create_app


def _build_client() -> TestClient:
    app = create_app(
        scheduler=object(),
        api_config={
            "environment": "production",
            "allowed_origins": ["https://dashboard.example.com"],
            "auth": {"enabled": True, "api_key": "secret-key"},
        },
    )
    return TestClient(app)


def test_navigation_preflight_skips_auth_and_returns_cors_response():
    client = _build_client()

    response = client.options(
        "/navigation/status",
        headers={
            "Origin": "https://dashboard.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, X-API-Key",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://dashboard.example.com"


def test_navigation_non_preflight_without_auth_is_rejected():
    client = _build_client()

    response = client.get("/navigation/status")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
