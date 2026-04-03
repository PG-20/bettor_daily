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
        "eventIds": ",".join(today_event_ids),
        "markets": "h2h"
    }
    try:
        odds_response = requests.get(odds_url, params=params)
        odds_response.raise_for_status()
        odds_data = odds_response.json()
        
        # 3. Parse Favorites Programmatically
        summary = []
        for match in odds_data:
            home_team = match.get('home_team')
            away_team = match.get('away_team')
            
            favorite = None
            min_price = float('inf')
            
            if match.get('bookmakers'):
                bookmaker = match['bookmakers'][0]
                markets = bookmaker.get('markets', [])
                if markets:
                    outcomes = markets[0].get('outcomes', [])
                    for outcome in outcomes:
                        if outcome['price'] < min_price:
                            min_price = outcome['price']
                            favorite = outcome['name']
            
            if favorite:
                summary.append(f"Match: {home_team} vs {away_team} | Favorite to bet on: {favorite}")
        
        return "\n".join(summary) if summary else "NO_ODDS"
        
    except Exception as e:
        print(f"❌ Error fetching/parsing odds: {e}")
        return None

async def run_betting_bot():
    # Reverting to the requested Meta model
    llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct")

    print("📊 Fetching today's IPL odds...")
    odds_summary = get_today_ipl_odds()

    if odds_summary == "NO_MATCHES":
        send_discord_notification("ℹ️ **No IPL matches today.** Skipping betting.")
        return
    elif odds_summary == "NO_ODDS":
        send_discord_notification("⚠️ **Matches found but no odds available yet.**")
        return
    elif odds_summary is None:
        send_discord_notification("❌ **Failed to fetch odds!** Check API key or connection.")
        return

    # Count specific matches and compress summary
    matches_list = [m for m in odds_summary.split('\n') if m.strip()]
    num_matches = len(matches_list)
    compact_summary = odds_summary.replace("Match: ", "").replace(" | Favorite to bet on: ", " -> ")

    task = (
        "Login to http://flask-env.eba-txvdvhqt.us-west-2.elasticbeanstalk.com/ with "
        "Phone: 68467746 and Password: '  ' (2 spaces). \n"
        f"Summary: {num_matches} match(es) to bet on today: {compact_summary}. "
        "For each match mentioned: find under 'Up Next', click the row, select team, and submit. return home"
        f"If all {num_matches} matches in summary have been completed, STOP; otherwise continue."
    )

    browser = Browser(
        headless=True,
        window_size={'width': 1280, 'height': 1100}
    )
    # use_vision=False saves tokens, but we still capture screenshots in history
    agent = Agent(task=task, llm=llm, browser=browser, use_vision=False)

    try:
        print("🚀 Starting betting bot...")
        history = await agent.run()

        # Get all screenshots from history
        screenshots = history.screenshots()
        screenshot_path = "bet_confirmation.png"
        has_screenshot = False

        if screenshots:
            import base64
            # We want the screenshot of the success page, not the final 'home' page.
            # Usually, the second to last screenshot (if successful) is the confirmation.
            # If there are multiple matches, we'll try to get the most recent confirmation.
            target_index = -2 if len(screenshots) > 1 else -1
            
            # Additional logic: if the agent failed, the last screenshot is likely the error state.
            if not history.is_successful():
                target_index = -1

            last_screenshot_base64 = screenshots[target_index]
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(last_screenshot_base64))
            print(f"📸 Screenshot saved as {screenshot_path} (Index: {target_index})")
            has_screenshot = True

        if history.is_successful():
            final_res = history.final_result()
            print(f"✅ Agent succeeded: {final_res}")
            send_discord_notification(
                f"✅ **Betting Bot Success!**\n**Result:** {final_res}",
                file_path=screenshot_path if has_screenshot else None
            )
        else:
            error_msg = "❌ **Betting Bot Failed!**\n**Reason:** Agent did not mark task as successful."
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
