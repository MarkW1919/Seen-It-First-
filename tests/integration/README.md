# Integration Tests

End-to-end integration tests for the RepoScan Pro backend API. These tests
run against a live instance of the backend (typically the `docker-compose.test.yml`
stack) and exercise all major API endpoints including authentication, detections,
hot list management, and WebSocket communication.

## Prerequisites

- **Docker & Docker Compose** (for the test stack)
- **Python 3.11+** with the following packages:
  ```
  pip install httpx pytest pytest-asyncio websockets
  ```

## Starting the Test Stack

From the repository root:

```bash
docker compose -f docker-compose.test.yml up -d --build --wait
```

This starts PostgreSQL (PostGIS), Redis, the backend, and the frontend. The
backend will be available at `http://localhost:8000`.

Verify the stack is healthy:

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"reposcan-backend"}
```

## Running the Tests

From the repository root:

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run a specific test file
pytest tests/integration/test_health.py -v

# Run a specific test
pytest tests/integration/test_auth_flow.py::test_full_auth_flow -v

# Run with output shown
pytest tests/integration/ -v -s
```

## Test Structure

| File                       | What it tests                                            |
|----------------------------|----------------------------------------------------------|
| `conftest.py`              | Shared fixtures: async HTTP client, test user, auth tokens |
| `test_health.py`           | `/health`, `/`, `/docs`, `/openapi.json` endpoints       |
| `test_auth_flow.py`        | Register, login, get me, refresh token                   |
| `test_detections_api.py`   | Detection CRUD: create, list, get by ID, pagination      |
| `test_hotlist_api.py`      | Hot list entry CRUD: create, list, update, delete        |
| `test_websocket.py`        | WebSocket connect, ping/pong, subscribe                  |

## Configuration

The tests default to `http://localhost:8000` as the backend URL. This is
configured in `conftest.py` via the `BASE_URL` constant. If you need to
target a different host (e.g., a staging environment), update the constant
or extend the fixtures to read from an environment variable.

## Tearing Down

```bash
docker compose -f docker-compose.test.yml down -v --remove-orphans
```

## Notes

- Each test session creates a **unique test user** (with a random email) so
  tests do not interfere with each other when the stack is reused across runs.
- Tests use **session-scoped fixtures** to avoid redundant registration/login
  calls within a single test run.
- The WebSocket tests verify connection handshake and message exchange but do
  not test Redis pub/sub broadcast (that requires backend-side event triggers).
- All HTTP tests use `httpx.AsyncClient` and all WebSocket tests use the
  `websockets` library.
