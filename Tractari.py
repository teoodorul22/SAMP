import cloudscraper
import json
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup
import random
import requests

# Configuration
FACTION_PAGE_URL = "https://panel.b-hood.ro/factions/members/8"  # Replace with actual URL
DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL"  # Replace with your webhook URL
DATA_FILE = "faction_data.json"
CHECK_INTERVAL = 3  # Time to wait between checks (in seconds)
MAX_RETRIES = 5  # Max retries for each request

# Create a cloudscraper object with headers
scraper = cloudscraper.create_scraper()

# Headers to avoid bot detection
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://panel.b-hood.ro/factions/members/8',
    'Connection': 'keep-alive'
}

def load_previous_data():
    """Load previously saved member data."""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        # If file doesn't exist, create an empty one
        save_current_data({})
        return {}
    except Exception as e:
        print(f"[{datetime.now()}] Error loading data file: {str(e)}")
        # Create a new empty data file
        save_current_data({})
        return {}

def save_current_data(data):
    """Save current member data to file."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[{datetime.now()}] Error saving data file: {str(e)}")

def send_discord_webhook(content, username="Faction Tracker"):
    """Send notification to Discord webhook."""
    webhook_data = {
        "content": content,
        "username": username
    }
    
    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=webhook_data
        )
        
        if response.status_code == 204:
            print(f"[{datetime.now()}] Webhook sent successfully")
            return True
        else:
            print(f"[{datetime.now()}] Failed to send webhook. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] Error sending webhook: {str(e)}")
        return False

def scrape_faction_data():
    """Scrape member data from the faction page with retries."""
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            attempt += 1
            print(f"[{datetime.now()}] Attempt {attempt} to scrape data...")
            
            response = scraper.get(FACTION_PAGE_URL, headers=headers)
            
            if response.status_code != 200:
                print(f"[{datetime.now()}] Failed to load page. Status code: {response.status_code}")
                if attempt < MAX_RETRIES:
                    print(f"[{datetime.now()}] Retrying...")
                    time.sleep(random.uniform(3, 6))  # Delay between retries to avoid rate-limiting
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='table table-striped table-hover')

            if not table:
                print(f"[{datetime.now()}] Could not find the faction table")
                if attempt < MAX_RETRIES:
                    print(f"[{datetime.now()}] Retrying...")
                    time.sleep(random.uniform(3, 6))
                continue

            tbody = table.find('tbody')
            if not tbody:
                print(f"[{datetime.now()}] Could not find the table body")
                if attempt < MAX_RETRIES:
                    print(f"[{datetime.now()}] Retrying...")
                    time.sleep(random.uniform(3, 6))
                continue

            member_rows = tbody.find_all('tr')
            print(f"[{datetime.now()}] Found {len(member_rows)} member rows")

            current_data = {}

            for row in member_rows:
                try:
                    username_element = row.find('a')
                    if not username_element:
                        continue

                    username = username_element.text.strip()
                    player_id = username_element.get('id')  # Extract player ID like '195032'
                    if not player_id:
                        print(f"[{datetime.now()}] Skipping {username} (no ID found)")
                        continue

                    spans = row.find_all('span', class_=f'points-{player_id}')

                    tractate_value = int(spans[0].text.strip()) if len(spans) > 0 else 0
                    reparate_value = int(spans[1].text.strip()) if len(spans) > 1 else 0
                    umplute_value = int(spans[2].text.strip()) if len(spans) > 2 else 0

                    current_data[username] = {
                        'vehicule_tractate': tractate_value,
                        'vehicule_reparate': reparate_value,
                        'rezervoare_umplute': umplute_value,
                        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                    print(f"[{datetime.now()}] Data for {username}: tractate={tractate_value}, reparate={reparate_value}, umplute={umplute_value}")
                except Exception as e:
                    print(f"[{datetime.now()}] Error processing row: {str(e)}")
                    continue

            if not current_data:
                print(f"[{datetime.now()}] No member data found")
                if attempt < MAX_RETRIES:
                    print(f"[{datetime.now()}] Retrying...")
                    time.sleep(random.uniform(3, 6))
                continue

            print(f"[{datetime.now()}] Successfully collected data for {len(current_data)} members")
            return current_data

        except Exception as e:
            print(f"[{datetime.now()}] Error scraping data: {str(e)}")
            if attempt < MAX_RETRIES:
                print(f"[{datetime.now()}] Retrying in 5 seconds...")
                time.sleep(random.uniform(5, 10))  # Retry with longer delay
            continue

    print(f"[{datetime.now()}] Max retries reached. Skipping this scrape.")
    return None

def main():
    print(f"[{datetime.now()}] Starting faction monitoring script")

    # First run - get initial data
    print(f"[{datetime.now()}] Getting initial faction data...")
    initial_data = scrape_faction_data()
    
    if initial_data:
        print(f"[{datetime.now()}] Sending initial summary to Discord webhook")
        save_current_data(initial_data)
    else:
        print(f"[{datetime.now()}] Failed to get initial faction data. Retrying...")
        time.sleep(5)  # Wait before trying again

    # Start monitoring loop
    while True:
        try:
            print(f"[{datetime.now()}] Starting monitoring cycle")
            
            # Load previous data
            previous_data = load_previous_data()
            
            # Get current data
            current_data = scrape_faction_data()
            
            if current_data:
                save_current_data(current_data)
            else:
                print(f"[{datetime.now()}] Failed to get current faction data")
            
            # Wait for next check
            print(f"[{datetime.now()}] Sleeping for {CHECK_INTERVAL} seconds")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[{datetime.now()}] Error in monitoring loop: {str(e)}")
            time.sleep(60)  # Wait a minute before trying again

if __name__ == "__main__":
    main()
