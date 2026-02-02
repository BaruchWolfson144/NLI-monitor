"""
Sync readings from Cloud Storage to local SQLite database.
Run this periodically to keep local data up to date.
"""

import json
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import storage
from local.database import (
    init_db,
    get_or_create_location,
    insert_reading,
    mark_blob_synced,
    is_blob_synced,
    get_readings_count
)

# Configuration
BUCKET_NAME = os.environ.get("BUCKET_NAME", "nli-monitor-data")
READINGS_PREFIX = "readings/"

# Location mapping (place_id -> metadata)
# This will be expanded as we add more locations
LOCATIONS = {
    "ChIJy8LxJaZGHRURzNVZXycuQnw": {
        "name": "National Library of Israel",
        "name_he": "הספרייה הלאומית",
        "address": "Edmond J. Safra Campus, Givat Ram, Jerusalem"
    }
}


def get_storage_client():
    """Get Cloud Storage client."""
    return storage.Client()


def sync_readings():
    """Sync all new readings from Cloud Storage to SQLite."""
    print(f"Starting sync from gs://{BUCKET_NAME}/{READINGS_PREFIX}")

    # Initialize database if needed
    init_db()

    # Get storage client
    try:
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
    except Exception as e:
        print(f"Error connecting to Cloud Storage: {e}")
        print("Make sure you're authenticated: gcloud auth application-default login")
        return

    # List all JSON files in readings/
    blobs = list(bucket.list_blobs(prefix=READINGS_PREFIX))
    json_blobs = [b for b in blobs if b.name.endswith(".json")]

    print(f"Found {len(json_blobs)} reading files in Cloud Storage")

    new_count = 0
    skip_count = 0
    error_count = 0

    for blob in json_blobs:
        # Check if already synced
        if is_blob_synced(blob.name):
            skip_count += 1
            continue

        try:
            # Download and parse JSON
            content = blob.download_as_text()
            data = json.loads(content)

            # Get or create location
            place_id = data.get("place_id")
            if not place_id:
                print(f"  Skipping {blob.name}: no place_id")
                error_count += 1
                continue

            location_info = LOCATIONS.get(place_id, {})
            location_id = get_or_create_location(
                place_id=place_id,
                name=location_info.get("name"),
                name_he=location_info.get("name_he"),
                address=location_info.get("address")
            )

            # Insert reading
            inserted = insert_reading(
                location_id=location_id,
                popularity=data.get("popularity"),
                timestamp=data.get("timestamp"),
                day_of_week=data.get("day_of_week"),
                hour=data.get("hour"),
                is_open=data.get("is_open", True),
                synced_from=blob.name
            )

            if inserted:
                new_count += 1
                print(f"  Synced: {blob.name}")
            else:
                skip_count += 1

            # Mark as synced
            mark_blob_synced(blob.name)

        except Exception as e:
            print(f"  Error processing {blob.name}: {e}")
            error_count += 1

    print()
    print("=== Sync Complete ===")
    print(f"New readings: {new_count}")
    print(f"Skipped (already synced): {skip_count}")
    print(f"Errors: {error_count}")
    print(f"Total readings in database: {get_readings_count()}")


def show_status():
    """Show current sync status."""
    init_db()

    print("=== Database Status ===")
    print(f"Database: {Path(__file__).parent.parent / 'data' / 'readings.db'}")
    print(f"Total readings: {get_readings_count()}")

    # Try to connect to Cloud Storage
    try:
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
        blobs = list(bucket.list_blobs(prefix=READINGS_PREFIX))
        json_blobs = [b for b in blobs if b.name.endswith(".json")]
        print(f"Files in Cloud Storage: {len(json_blobs)}")

        # Count unsynced
        unsynced = sum(1 for b in json_blobs if not is_blob_synced(b.name))
        print(f"Pending sync: {unsynced}")
    except Exception as e:
        print(f"Could not connect to Cloud Storage: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync readings from Cloud Storage")
    parser.add_argument("--status", action="store_true", help="Show sync status")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        sync_readings()
