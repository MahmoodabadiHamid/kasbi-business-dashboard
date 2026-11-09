"""Load trip and destination data directly from SQL Server."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


TRIP_REQUIRED = {"Id", "OrganizationId", "DriverId", "StartDateTime", "EndDateTime", "TripCost", "TripDriverCost"}
DEST_REQUIRED = {"Id", "TripId", "DestinationCost", "DestinationCostWithoutStopTime", "StopTimeDestinationCost"}
ROOT = Path(__file__).resolve().parents[1]


def _odbc(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def connection_string() -> str:
    """Build a read-only SQL Server connection string from .env / environment."""
    load_dotenv(ROOT / ".env")
    required = ["SQL_SERVER", "SQL_DATABASE"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    parts = [
        f"DRIVER={_odbc(os.getenv('SQL_DRIVER', 'ODBC Driver 18 for SQL Server'))}",
        f"SERVER={_odbc(os.environ['SQL_SERVER'])}",
        f"DATABASE={_odbc(os.environ['SQL_DATABASE'])}",
        f"Encrypt={os.getenv('SQL_ENCRYPT', 'yes')}",
        f"TrustServerCertificate={os.getenv('SQL_TRUST_SERVER_CERTIFICATE', 'no')}",
        "ApplicationIntent=ReadOnly",
    ]
    username = os.environ.get("SQL_USERNAME")
    password = os.environ.get("SQL_PASSWORD")
    if username and password:
        parts.extend([f"UID={_odbc(username)}", f"PWD={_odbc(password)}"])
    else:
        parts.append("Trusted_Connection=yes")
    return ";".join(parts)


def read_database(start=None, end=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read all trip history by default, or the optional [start, end) bounds."""
    if start is not None and end is not None and not pd.Timestamp(start) < pd.Timestamp(end):
        raise ValueError("End date must be later than start date.")

    import pyodbc

    frames = []
    with pyodbc.connect(connection_string(), timeout=30) as connection:
        for name in ("trips", "destinations"):
            query = (ROOT / "sql" / f"{name}.sql").read_text(encoding="utf-8")
            frames.append(pd.read_sql_query(query, connection, params=[start, start, end, end]))
    return frames[0], frames[1]
