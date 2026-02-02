import os
import time
import datetime
import requests
import schedule
import livepopulartimes as populartimes
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PLACE_ID = os.getenv("PLACE_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MESSAGE_ID_FILE = os.getenv("MESSAGE_ID_FILE", "telegram_message_id.txt")

# --- Constants ---
# Library operating hours (Sunday to Thursday, 9 AM to 8 PM)
# Represented as (weekday, open_hour, close_hour)
# Monday is 0 and Sunday is 6
OPERATING_HOURS = {
    0: (9, 20),  # Monday
    1: (9, 20),  # Tuesday
    2: (9, 20),  # Wednesday
    3: (9, 20),  # Thursday
    4: (9, 13),  # Friday
    6: (9, 20),  # Sunday
}

# --- Helper Functions ---

def is_library_open():
    """Checks if the library is within its operating hours."""
    now = datetime.datetime.now()
    weekday = now.weekday()
    current_hour = now.hour

    if weekday in OPERATING_HOURS:
        open_hour, close_hour = OPERATING_HOURS[weekday]
        return open_hour <= current_hour < close_hour
    return False

def get_crowd_data():
    """
    Fetches crowd data using the populartimes library.
    Returns the current popularity value or None if not available.
    """
    try:
        place_data = populartimes.get_populartimes_by_PlaceID(GOOGLE_API_KEY, PLACE_ID)
        return place_data.get("current_popularity")
    except Exception as e:
        print(f"Error fetching data from Google: {e}")
        return None

def classify_load(popularity):
    """Classifies the popularity value into a human-readable load level."""
    if popularity is None:
        return "לא ידוע", "⚪️"  # Unknown, White Circle

    if popularity < 30:
        return "נמוך", "🟢"  # Low, Green Circle
    elif 30 <= popularity < 60:
        return "בינוני", "🟡"  # Medium, Yellow Circle
    else:
        return "גבוה", "🔴"  # High, Red Circle

def get_last_message_id():
    """Reads the last sent message ID from a file."""
    try:
        with open(MESSAGE_ID_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_last_message_id(message_id):
    """Saves the last sent message ID to a file."""
    with open(MESSAGE_ID_FILE, "w") as f:
        f.write(str(message_id))

def send_telegram_message(text):
    """Sends a new message to the Telegram channel and saves its ID."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("ok"):
            message_id = data["result"]["message_id"]
            save_last_message_id(message_id)
            print(f"Successfully sent new message (ID: {message_id}).")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")

def edit_telegram_message(message_id, text):
    """Edits an existing Telegram message."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        # If the message is not modified, Telegram API returns an error. We can ignore it.
        if response.status_code == 400 and 'message is not modified' in response.text:
            print("Message content is the same, no edit needed.")
            return True
        response.raise_for_status()
        print(f"Successfully edited message (ID: {message_id}).")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error editing Telegram message: {e}. It might have been deleted.")
        return False

# --- Core Logic ---

def run_check():
    """
    The main job function to be scheduled.
    It checks if the library is open, fetches data, and sends an update.
    """
    print(f"Running check at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not is_library_open():
        print("Library is closed. Skipping check.")
        # Optional: update message to "Closed"
        last_message_id = get_last_message_id()
        closed_message = "הספרייה הלאומית סגורה כעת."
        if last_message_id:
            edit_telegram_message(last_message_id, closed_message)
        else:
            send_telegram_message(closed_message)
        return

    popularity = get_crowd_data()
    load_level, emoji = classify_load(popularity)
    
    timestamp = datetime.datetime.now().strftime("%H:%M")
    
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

    last_message_id = get_last_message_id()

    if last_message_id:
        if not edit_telegram_message(last_message_id, message):
            # If editing fails (e.g., message deleted), send a new one
            send_telegram_message(message)
    else:
        send_telegram_message(message)

# --- Scheduler ---

if __name__ == "__main__":
    print("Starting crowd monitor bot...")

    # --- Use this block for cron-based execution ---
    # print("Running a single check...")
    # run_check()
    # print("Single check finished.")
    
    # --- Use this block for persistent, scheduled execution ---
    schedule.every(30).minutes.do(run_check)
    
    # Run one check immediately at the start
    run_check()
    
    while True:
        schedule.run_pending()
        time.sleep(1)