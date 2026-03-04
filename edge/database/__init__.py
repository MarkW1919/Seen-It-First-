"""
SEEN IT FIRST - Edge Database Package

Public surface:
    DatabaseConnection  - async SQLite connection manager
    DetectionRepository - async CRUD facade
    Models              - Vehicle, Plate, Detection, Address, HotlistEntry, SystemLog
    run_migrations      - schema versioning entry point
"""

from edge.database.connection import DatabaseConnection
from edge.database.models import (
    Address,
    Detection,
    HotlistEntry,
    Plate,
    SystemLog,
    Vehicle,
)
from edge.database.migrations import run_migrations
from edge.database.repository import DetectionRepository

__all__ = [
    "Address",
    "DatabaseConnection",
    "Detection",
    "DetectionRepository",
    "HotlistEntry",
    "Plate",
    "SystemLog",
    "Vehicle",
    "run_migrations",
]
