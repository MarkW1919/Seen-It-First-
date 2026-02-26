from pydantic import BaseModel, ConfigDict, Field


class StopCreate(BaseModel):
    address: str
    latitude: float
    longitude: float
    geofence_radius_m: float = Field(default=50.0, ge=10.0, le=500.0)


class RouteCreate(BaseModel):
    name: str | None = None
    stops: list[StopCreate] = Field(..., min_length=1, max_length=200)


class StopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    address: str
    latitude: float
    longitude: float
    geofence_radius_m: float
    status: str
    arrived_at: str | None = None
    scan_started_at: str | None = None
    completed_at: str | None = None
    plates_found: int = 0
    notes: str | None = None


class RouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str | None
    status: str
    current_stop_index: int
    total_stops: int
    created_at: str
    completed_at: str | None = None
    stops: list[StopResponse] = []


class StopUpdate(BaseModel):
    notes: str | None = None
    plates_found: int | None = None
