"""
SQLite database management for NLI Monitor.
Stores historical crowd readings for analysis and ML.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "readings.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with the required schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create locations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_he TEXT,
            place_id TEXT UNIQUE NOT NULL,
            address TEXT,
            operating_hours TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create readings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER REFERENCES locations(id),
            popularity INTEGER,
            timestamp TEXT NOT NULL,
            day_of_week INTEGER,
            hour INTEGER,
            is_open INTEGER,
            synced_from TEXT,
            UNIQUE(location_id, timestamp)
        )
    """)

    # Create indexes for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_location_time
        ON readings(location_id, timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_day_hour
        ON readings(day_of_week, hour)
    """)

    # Create sync_log table to track synced files
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blob_path TEXT UNIQUE NOT NULL,
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def get_or_create_location(place_id: str, name: str = None, name_he: str = None,
                           address: str = None, operating_hours: dict = None) -> int:
    """Get location ID by place_id, or create if doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Try to find existing
    cursor.execute("SELECT id FROM locations WHERE place_id = ?", (place_id,))
    row = cursor.fetchone()

    if row:
        location_id = row["id"]
    else:
        # Create new location
        cursor.execute("""
            INSERT INTO locations (name, name_he, place_id, address, operating_hours)
            VALUES (?, ?, ?, ?, ?)
        """, (
            name or "Unknown",
            name_he,
            place_id,
            address,
            json.dumps(operating_hours) if operating_hours else None
        ))
        location_id = cursor.lastrowid
        print(f"Created new location: {name} (ID: {location_id})")

    conn.commit()
    conn.close()
    return location_id


def insert_reading(location_id: int, popularity: Optional[int], timestamp: str,
                   day_of_week: int, hour: int, is_open: bool,
                   synced_from: str = None) -> bool:
    """Insert a reading. Returns True if inserted, False if duplicate."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO readings
            (location_id, popularity, timestamp, day_of_week, hour, is_open, synced_from)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (location_id, popularity, timestamp, day_of_week, hour,
              1 if is_open else 0, synced_from))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Duplicate entry
        conn.close()
        return False


def mark_blob_synced(blob_path: str):
    """Mark a Cloud Storage blob as synced."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO sync_log (blob_path) VALUES (?)",
            (blob_path,)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already synced

    conn.close()


def is_blob_synced(blob_path: str) -> bool:
    """Check if a blob has already been synced."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM sync_log WHERE blob_path = ?",
        (blob_path,)
    )
    result = cursor.fetchone() is not None
    conn.close()
    return result


def get_readings_count() -> int:
    """Get total number of readings in database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM readings")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_latest_readings(limit: int = 10) -> list:
    """Get the most recent readings."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, l.name, l.name_he
        FROM readings r
        JOIN locations l ON r.location_id = l.id
        ORDER BY r.timestamp DESC
        LIMIT ?
    """, (limit,))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
    print(f"Total readings: {get_readings_count()}")
