# National Library Crowd Monitor Bot

This project contains a simple, efficient Python script to monitor the crowd levels at the National Library of Israel using Google Maps' "Popular Times" data and broadcast updates to a Telegram channel.

## Architecture

- **Data Source**: Google Maps "Popular Times" (via `populartimes` library).
- **Backend**: A single Python script (`monitor.py`).
- **Frontend**: A public Telegram channel.
- **Infrastructure**: Designed to be run with a scheduler like `cron` or as a persistent background process.

## Setup Instructions

1.  **Clone or Download:**
    Get the files into a directory on your system.

2.  **Create a `.env` File:**
    Duplicate the `.env.example` file and rename it to `.env`.

    ```bash
    cp .env.example .env
    ```

3.  **Fill in Credentials in `.env`:**
    Open the `.env` file and fill in the following values:
    - `GOOGLE_API_KEY`: Your Google Cloud API Key. You need to enable the **Places API** for your project in the [Google Cloud Console](https://console.cloud.google.com/).
    - `PLACE_ID`: The Google Maps Place ID for the location. The default is for the National Library of Israel.
    - `TELEGRAM_BOT_TOKEN`: The token for your Telegram bot, which you can get from [BotFather](https://t.me/botfather).
    - `TELEGRAM_CHAT_ID`: The ID of the Telegram channel or chat where you want to send updates (e.g., `@mychannelname` for a public channel, or your personal chat ID for testing).

4.  **Install Dependencies:**
    It's recommended to use a virtual environment.

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

5.  **Set Cost & Quota Limits (Recommended):**
    To prevent unexpected costs, go to your Google Cloud Console and set a daily quota for the Places API. A limit of 50 requests per day is a safe starting point.

## How to Run

You can run the script in two ways:

### 1. As a Persistent Background Process

The script uses the `schedule` library to run every 30 minutes. Simply run it in the background:

```bash
nohup python3 monitor.py &
```

The script will handle its own scheduling.

### 2. Using a Cron Job (Recommended for Stability)

If you prefer using a system scheduler, you can set up a cron job.

- First, modify `monitor.py` by commenting out the `schedule` loop at the end and uncommenting the single `run_check()` call.
- Then, open your crontab:
  ```bash
  crontab -e
  ```
- Add this line to run the script every 30 minutes. Make sure to use the absolute path to your python executable and script.
  ```cron
  */30 * * * * /path/to/your/venv/bin/python /path/to/your/project/monitor.py
  ```

This approach is generally more robust for long-term execution.
