import importlib.util
import unittest

from edge.api.app import (
    _extract_auth_credentials,
    _extract_bearer_token,
    _is_api_authorized,
    _is_protected_path,
    _normalize_allowed_origins,
    _resolve_cors_origins,
    ConnectionManager,
    create_app,
)

_HTTPX_AVAILABLE = importlib.util.find_spec("httpx") is not None

if _HTTPX_AVAILABLE:
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect


class _DummyScheduler:
    def __init__(self):
        self._active = True

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False

    @property
    def is_active(self):
        return self._active


class TestApiAuthHelpers(unittest.TestCase):
    def test_extract_bearer_token(self):
        self.assertEqual(_extract_bearer_token("Bearer abc123"), "abc123")
        self.assertEqual(_extract_bearer_token("bearer xyz"), "xyz")
        self.assertIsNone(_extract_bearer_token("Basic abc"))
        self.assertIsNone(_extract_bearer_token(None))

    def test_extract_auth_credentials(self):
        self.assertEqual(
            _extract_auth_credentials("key", "Bearer token", "q"),
            ("key", "token", "q"),
        )

    def test_is_api_authorized(self):
        self.assertTrue(_is_api_authorized("", None, None, None))
        self.assertTrue(_is_api_authorized("tok", "tok", None, None))
        self.assertTrue(_is_api_authorized("tok", None, "tok", None))
        self.assertTrue(_is_api_authorized("tok", None, None, "tok"))
        self.assertFalse(_is_api_authorized("tok", "bad", None, None))

    def test_is_protected_path(self):
        self.assertTrue(_is_protected_path("/navigation"))
        self.assertTrue(_is_protected_path("/navigation/status"))
        self.assertFalse(_is_protected_path("/ws"))

    def test_normalize_allowed_origins(self):
        self.assertEqual(
            _normalize_allowed_origins("http://a.com, http://b.com"),
            ["http://a.com", "http://b.com"],
        )
        self.assertEqual(
            _normalize_allowed_origins(["http://a.com", "  ", "http://b.com"]),
            ["http://a.com", "http://b.com"],
        )

    def test_resolve_cors_origins_defaults_for_development(self):
        self.assertEqual(
            _resolve_cors_origins({"environment": "development"}),
            ["http://localhost:5173"],
        )

    def test_resolve_cors_origins_requires_explicit_production_origins(self):
        with self.assertRaises(ValueError):
            _resolve_cors_origins({"environment": "production"})

    def test_resolve_cors_origins_rejects_wildcard(self):
        with self.assertRaises(ValueError):
            _resolve_cors_origins({"allowed_origins": ["*"]})


@unittest.skipUnless(_HTTPX_AVAILABLE, "httpx not installed; skipping FastAPI TestClient integration checks")
class TestApiAuthMiddleware(unittest.TestCase):
    def _client(self, auth_token: str):
        app = create_app(
            scheduler=_DummyScheduler(),
            config={},
            api_config={"auth_token": auth_token, "allowed_origins": ["http://localhost:5173"]},
        )
        return TestClient(app)

    def test_navigation_route_requires_token_when_enabled(self):
        with self._client("secret-token") as client:
            no_auth = client.get("/navigation/status")
            self.assertEqual(no_auth.status_code, 401)

            with_key = client.get("/navigation/status", headers={"X-API-Key": "secret-token"})
            self.assertEqual(with_key.status_code, 200)
            self.assertIn("pipeline_active", with_key.json())

            with_bearer = client.get(
                "/navigation/status",
                headers={"Authorization": "Bearer secret-token"},
            )
            self.assertEqual(with_bearer.status_code, 200)


    def test_options_preflight_skips_auth_when_token_enabled(self):
        with self._client("secret-token") as client:
            response = client.options(
                "/navigation/status",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
            self.assertEqual(response.status_code, 200)

    def test_options_without_preflight_header_requires_auth(self):
        with self._client("secret-token") as client:
            response = client.options("/navigation/status")
            self.assertEqual(response.status_code, 401)

    def test_navigation_get_with_preflight_header_still_requires_auth(self):
        with self._client("secret-token") as client:
            response = client.get(
                "/navigation/status",
                headers={"Access-Control-Request-Method": "POST"},
            )
            self.assertEqual(response.status_code, 401)

    def test_navigation_route_open_when_token_disabled(self):
        with self._client("") as client:
            response = client.get("/navigation/status")
            self.assertEqual(response.status_code, 200)

    def test_websocket_requires_token_and_does_not_register_client(self):
        ws_manager = ConnectionManager()
        app = create_app(
            scheduler=_DummyScheduler(),
            config={},
            api_config={
                "auth_token": "secret-token",
                "allowed_origins": ["http://localhost:5173"],
            },
            ws_manager=ws_manager,
        )

        with TestClient(app) as client:
            with self.assertRaises(WebSocketDisconnect) as ctx:
                with client.websocket_connect("/ws"):
                    pass

        self.assertEqual(ctx.exception.code, 1008)
        self.assertEqual(ws_manager.client_count, 0)


if __name__ == "__main__":
    unittest.main()
