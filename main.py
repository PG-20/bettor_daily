import asyncio
import os
import requests
import json
from browser_use import Agent, Browser, ChatGroq
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

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

async def run_betting_bot():
    # Initialize the "Brain" (Gemini 3.1 Flash)
    llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct")

    # The Task: Research + Execution
    task = (
        "1. Search for 'IPL match today' to confirm who is playing. There might be 2 matches on the same day. "
        "2. Search for 'IPL [Teams] oddschecker today' to get the odds for each match one-by-one (in case of 2 matches). "
        "3. enter the oddschecker website and compile the odds from the table to decide who is the favourite. "
        f"4. Go to http://flask-env.eba-txvdvhqt.us-west-2.elasticbeanstalk.com/, log in with "
        f"Phone Number: 68467746 and Password: '  ' (2 spaces). "
        "Wait for the page to load. "
        "5. Find the match under 'Up Next' and click the row which will take you the match page. "
        "6. Click on Choose team, whichever one is decided, submit the bet and take a screenshot. "
        "7. Click on home and Repeat steps 5-6 for the other match (if there are 2 matches). "
    )

    browser = Browser(
        headless=True,  # Set to True for your GitHub Action
        window_size={'width': 1280, 'height': 1100}
    )
    agent = Agent(task=task, llm=llm, browser=browser)

    try:
        print("🚀 Starting betting bot...")
        history = await agent.run()

        # Check if the agent actually succeeded (browser-use specific)
        # Often the last result or finding a specific element is enough
        # We'll save the screenshot if available
        screenshots = history.screenshots()
        screenshot_path = "bet_confirmation.png"

        if screenshots:
            import base64
            last_screenshot_base64 = screenshots[-1]
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(last_screenshot_base64))
            print(f"✅ Screenshot saved as {screenshot_path}")

        send_discord_notification(
            "✅ **Betting Bot Success!** The bets have been placed successfully.",
            file_path=screenshot_path if screenshots else None
        )

    except Exception as e:
        error_msg = f"❌ **Betting Bot Failed!**\n**Reason:** {str(e)}"
        print(error_msg)
        send_discord_notification(error_msg)

if __name__ == "__main__":
    asyncio.run(run_betting_bot())