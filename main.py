import asyncio
import os
import requests
import json
from datetime import datetime, timezone
from browser_use import Agent, Browser, ChatGroq
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

def send_discord_notification(message, file_path=None):
    if not DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL not found in .env")
        return

    payload = {"content": message}
    files = {}
    if file_path and os.path.exists(file_path):
        files = {"file": open(file_path, "rb")}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=payload, files=files)
        if response.status_code < 300:
            print("🔔 Discord notification sent!")
        else:
            print(f"❌ Failed to send Discord notification: {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending Discord notification: {e}")

def get_today_ipl_odds():
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY not found in .env")
        return None

    sport = "cricket_ipl"
    # 1. Get Events
    events_url = f"https://api.the-odds-api.com/v4/sports/{sport}/events?apiKey={ODDS_API_KEY}"
    try:
        events_response = requests.get(events_url)
        events_response.raise_for_status()
        events = events_response.json()
    except Exception as e:
        print(f"❌ Error fetching events: {e}")
        return None

    # Filter events for today (UTC)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_event_ids = [e['id'] for e in events if e['commence_time'].startswith(today)]

    if not today_event_ids:
        print("ℹ️ No IPL matches found for today.")
        return "NO_MATCHES"

    # 2. Get Odds for those event IDs
    odds_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "uk",
        "eventIds": ",".join(today_event_ids)
    }
    try:
        odds_response = requests.get(odds_url, params=params)
        odds_response.raise_for_status()
        return odds_response.json()
    except Exception as e:
        print(f"❌ Error fetching odds: {e}")
        return None

async def run_betting_bot():
    # Initialize the "Brain" (Gemini 3.1 Flash)
    llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct")

    print("📊 Fetching today's IPL odds...")
    odds_data = get_today_ipl_odds()

    if odds_data == "NO_MATCHES":
        send_discord_notification("ℹ️ **No IPL matches today.** Skipping betting.")
        return
    elif odds_data is None:
        send_discord_notification("❌ **Failed to fetch odds!** Check API key or connection.")
        return

    odds_json_str = json.dumps(odds_data, indent=2)

    # The Task: Use the odds data and place the bets
    task = (
        f"Using the following JSON odds data for today's IPL matches:\n{odds_json_str}\n\n"
        "1. Parse the JSON and determine the winner/favorite for each match (lower odds means favorite). "
        "2. For each match, note the teams and the chosen favorite. "
        "3. Go to http://flask-env.eba-txvdvhqt.us-west-2.elasticbeanstalk.com/, log in with "
        "Phone Number: 68467746 and Password: '  ' (2 spaces). "
        "Wait for the page to load. "
        "4. For each match identified from the odds data: "
        "   a. Find the match under 'Up Next' on the home page and click the row to go to the match page. "
        "   b. Click on 'Choose team', select the favorite team you identified, submit the bet, and take a screenshot. "
        "   c. Go back to the home page to handle the next match (if any). "
    )

    browser = Browser(
        headless=True,
        window_size={'width': 1280, 'height': 1100}
    )
    agent = Agent(task=task, llm=llm, browser=browser)

    try:
        print("🚀 Starting betting bot...")
        history = await agent.run()

        # Save the last screenshot if available (regardless of success, for debugging)
        screenshots = history.screenshots()
        screenshot_path = "bet_confirmation.png"
        has_screenshot = False

        if screenshots:
            import base64
            last_screenshot_base64 = screenshots[-1]
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(last_screenshot_base64))
            print(f"📸 Last screenshot saved as {screenshot_path}")
            has_screenshot = True

        if history.is_successful():
            final_res = history.final_result()
            print(f"✅ Agent succeeded: {final_res}")
            send_discord_notification(
                f"✅ **Betting Bot Success!**\n**Result:** {final_res}",
                file_path=screenshot_path if has_screenshot else None
            )
        else:
            # If not successful, we treat it as a failure even if no exception was raised
            error_msg = "❌ **Betting Bot Failed!**\n**Reason:** Agent did not mark the task as successful."
            print(error_msg)
            send_discord_notification(
                error_msg,
                file_path=screenshot_path if has_screenshot else None
            )

    except Exception as e:
        error_msg = f"❌ **Betting Bot Failed!**\n**Reason:** {str(e)}"
        print(error_msg)
        send_discord_notification(error_msg)

if __name__ == "__main__":
    asyncio.run(run_betting_bot())