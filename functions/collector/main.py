"""
Cloud Function for monitoring crowd levels at cultural institutions.
Triggered by Cloud Scheduler every 30 minutes during operating hours.
"""

import datetime
import json
import os

import functions_framework
import requests
from google.cloud import secretmanager, storage
import livepopulartimes as populartimes


# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "nli-monitor-data")
STATE_BLOB = "state/telegram_message_id.txt"
READINGS_PREFIX = "readings/"

# --- Constants ---
# Library operating hours (Sunday to Thursday, 9 AM to 8 PM)
# Monday is 0 and Sunday is 6
OPERATING_HOURS = {
    0: (9, 20),  # Monday
    1: (9, 20),  # Tuesday
    2: (9, 20),  # Wednesday
    3: (9, 20),  # Thursday
    4: (9, 13),  # Friday
    6: (9, 20),  # Sunday
}


def get_secret(secret_id: str) -> str:
    """Retrieves a secret from Google Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def get_storage_client():
    """Returns a Cloud Storage client."""
    return storage.Client()


def is_library_open() -> bool:
    """Checks if the library is within its operating hours."""
    # Use Israel timezone
    import pytz
    tz = pytz.timezone("Asia/Jerusalem")
    now = datetime.datetime.now(tz)
    weekday = now.weekday()
    current_hour = now.hour

    if weekday in OPERATING_HOURS:
        open_hour, close_hour = OPERATING_HOURS[weekday]
        return open_hour <= current_hour < close_hour
    return False


def get_crowd_data(api_key: str, place_id: str) -> int | None:
    """
    Fetches crowd data using the populartimes library.
    Returns the current popularity value or None if not available.
    """
    try:
        place_data = populartimes.get_populartimes_by_PlaceID(api_key, place_id)
        return place_data.get("current_popularity")
    except Exception as e:
        print(f"Error fetching data from Google for {place_id}: {e}")
        return None


def classify_load(popularity: int | None) -> tuple[str, str]:
    """Classifies the popularity value into a human-readable load level."""
    if popularity is None:
        return "לא ידוע", "⚪️"

    if popularity < 30:
        return "נמוך", "🟢"
    elif 30 <= popularity < 60:
        return "בינוני", "🟡"
    else:
        return "גבוה", "🔴"


def get_last_message_id(storage_client) -> str | None:
    """Reads the last sent message ID from Cloud Storage."""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(STATE_BLOB)
        if blob.exists():
            return blob.download_as_text().strip()
    except Exception as e:
        print(f"Error reading message ID: {e}")
    return None


def save_last_message_id(storage_client, message_id: str):
    """Saves the last sent message ID to Cloud Storage."""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(STATE_BLOB)
        blob.upload_from_string(str(message_id))
    except Exception as e:
        print(f"Error saving message ID: {e}")


def save_reading(storage_client, reading: dict):
    """Saves a reading to Cloud Storage for later sync."""
    try:
        import pytz
        tz = pytz.timezone("Asia/Jerusalem")
        now = datetime.datetime.now(tz)

        # Create path: readings/2024/01/28/14-30.json
        path = now.strftime(f"{READINGS_PREFIX}%Y/%m/%d/%H-%M.json")

        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(path)
        blob.upload_from_string(
            json.dumps(reading, ensure_ascii=False, indent=2),
            content_type="application/json"
        )
        print(f"Saved reading to {path}")
    except Exception as e:
        print(f"Error saving reading: {e}")


def send_telegram_message(token: str, chat_id: str, text: str) -> str | None:
    """Sends a new message to the Telegram channel and returns its ID."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("ok"):
            message_id = str(data["result"]["message_id"])
            print(f"Successfully sent new message (ID: {message_id}).")
            return message_id
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
    return None


def edit_telegram_message(token: str, chat_id: str, message_id: str, text: str) -> bool:
    """Edits an existing Telegram message."""
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 400 and 'message is not modified' in response.text:
            print("Message content is the same, no edit needed.")
            return True
        response.raise_for_status()
        print(f"Successfully edited message (ID: {message_id}).")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error editing Telegram message: {e}. It might have been deleted.")
        return False


@functions_framework.http
def monitor_crowds(request):
    """
    HTTP Cloud Function entry point.
    Triggered by Cloud Scheduler.
    """
    import pytz
    tz = pytz.timezone("Asia/Jerusalem")
    now = datetime.datetime.now(tz)

    print(f"Running check at {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get secrets
    try:
        google_api_key = get_secret("GOOGLE_API_KEY")
        telegram_token = get_secret("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = get_secret("TELEGRAM_CHAT_ID")
        place_id = get_secret("PLACE_ID")
    except Exception as e:
        print(f"Error getting secrets: {e}")
        return ("Error getting secrets", 500)

    storage_client = get_storage_client()

    if not is_library_open():
        print("Library is closed. Updating status.")
        closed_message = "הספרייה הלאומית סגורה כעת."

        last_message_id = get_last_message_id(storage_client)
        if last_message_id:
            if not edit_telegram_message(telegram_token, telegram_chat_id, last_message_id, closed_message):
                # Message was deleted, create a new one
                new_id = send_telegram_message(telegram_token, telegram_chat_id, closed_message)
                if new_id:
                    save_last_message_id(storage_client, new_id)
        else:
            new_id = send_telegram_message(telegram_token, telegram_chat_id, closed_message)
            if new_id:
                save_last_message_id(storage_client, new_id)

        return ("Library closed", 200)

    # Get crowd data
    popularity = get_crowd_data(google_api_key, place_id)
    load_level, emoji = classify_load(popularity)

    timestamp = now.strftime("%H:%M")

    # Save reading for later sync
    reading = {
        "timestamp": now.isoformat(),
        "place_id": place_id,
        "popularity": popularity,
        "day_of_week": now.weekday(),
        "hour": now.hour,
        "is_open": True
    }
    save_reading(storage_client, reading)

    # Build message
    if popularity is not None:
        message = (
            f"{emoji} *עדכון עומס בספרייה הלאומית*\n\n"
            f"רמת העומס כעת: *{load_level}* ({popularity}%)\n\n"
            f"_עודכן לאחרונה: {timestamp}_"
        )
    else:
        message = (
            f"{emoji} *עדכון עומס בספרייה הלאומית*\n\n"
            f"לא ניתן היה לקבל את רמת העומס כעת.\n\n"
            f"_נסיון אחרון: {timestamp}_"
        )

    # Send/edit Telegram message
    last_message_id = get_last_message_id(storage_client)

    if last_message_id:
        if not edit_telegram_message(telegram_token, telegram_chat_id, last_message_id, message):
            new_id = send_telegram_message(telegram_token, telegram_chat_id, message)
            if new_id:
                save_last_message_id(storage_client, new_id)
    else:
        new_id = send_telegram_message(telegram_token, telegram_chat_id, message)
        if new_id:
            save_last_message_id(storage_client, new_id)

    return (f"Success: popularity={popularity}", 200)
