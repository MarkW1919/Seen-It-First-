# RepoScan Pro - API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

## Authentication

All endpoints (except `/api/auth/login` and `/api/auth/register`) require a Bearer token.

### POST /api/auth/register
Create a new user account.

```json
{
  "email": "agent@example.com",
  "password": "secure-password",
  "full_name": "Agent Name",
  "role": "agent"
}
```
Roles: `admin`, `supervisor`, `agent`

### POST /api/auth/login
```json
{
  "email": "agent@example.com",
  "password": "secure-password"
}
```
Returns: `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`

### POST /api/auth/refresh
```json
{ "refresh_token": "..." }
```

### GET /api/auth/me
Returns current user profile.

## Detections

### POST /api/detections/
Submit a new detection (typically from AI pipeline).

```json
{
  "vehicle_type": "car",
  "vehicle_color": "white",
  "vehicle_make": "Toyota",
  "vehicle_model": "Camry",
  "vehicle_year": 2020,
  "vehicle_confidence": 0.92,
  "latitude": 33.4484,
  "longitude": -112.0740,
  "plate_reads": [
    {
      "plate_text": "ABC1234",
      "plate_state": "AZ",
      "confidence": 0.95
    }
  ]
}
```

### GET /api/detections/
Query parameters: `page`, `page_size`, `session_id`, `start_date`, `end_date`

### GET /api/detections/{id}

## Hot List

### POST /api/hotlist/entries
```json
{
  "plate_text": "XYZ5678",
  "plate_state": "CA",
  "case_number": "REPO-2024-001",
  "lender_name": "First National Bank",
  "vehicle_year": 2019,
  "vehicle_make": "Honda",
  "vehicle_model": "Civic",
  "vehicle_color": "blue",
  "vin": "1HGBH41JXMN109186",
  "debtor_name": "John Doe",
  "debtor_address": "123 Main St, Phoenix AZ",
  "priority": "high"
}
```

### GET /api/hotlist/entries
Query: `active_only` (default: true), `page`, `page_size`

### PATCH /api/hotlist/entries/{id}
### DELETE /api/hotlist/entries/{id}

### POST /api/hotlist/entries/import
Bulk import:
```json
{ "entries": [ { ... }, { ... } ] }
```

### GET /api/hotlist/alerts
Query: `status` (new, acknowledged, dispatched, resolved, false_positive)

### PATCH /api/hotlist/alerts/{id}
```json
{ "status": "acknowledged", "notes": "On route to location" }
```

## Search

### GET /api/search/plate
Query: `q` (plate text), `exact` (boolean), `page`

### GET /api/search/nearby
Query: `lat`, `lng`, `radius` (miles, default 1.0)

## Plates

### GET /api/plates/recent
Query: `limit` (default 100)

### GET /api/plates/stats
Returns total reads, unique plates, top states.

### GET /api/plates/by-state/{state}

## Camera

### GET /api/camera/status
### POST /api/camera/ptz
```json
{ "pan": 45.0, "tilt": -10.0, "zoom": 2.0 }
```

### POST /api/camera/night-mode/{enabled}
### POST /api/camera/capture
### GET /api/camera/config
### PUT /api/camera/config

## System

### GET /api/system/info
### GET /api/system/stats (admin only)

## WebSocket

Connect: `ws://localhost:8000/ws?token=<access_token>`

### Events from server:
```json
{ "type": "hotlist_alert", "alert_id": "...", "plate_text": "ABC1234", "confidence": 0.95, ... }
{ "type": "detection", "detection_id": "...", "plate_text": "XYZ5678", ... }
{ "type": "system:camera", "data": { "is_connected": true, "fps": 28.5, ... } }
```

### Messages to server:
```json
{ "type": "ping" }
{ "type": "subscribe", "channel": "alerts" }
```
