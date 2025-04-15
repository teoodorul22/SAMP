import cloudscraper
import json
import time
import os
from datetime import datetime

# Configuration
FACTION_PAGE_URL = "https://panel.b-hood.ro/factions/members/8"  # Replace with actual URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1361717456858513488/_pTEH2xeuMLbjvBS1kBU-4Jd97jfI2XVVbImfiytjRGRlI8aOK6kNnSvL9nGG8KSp5gB"  # Replace with your webhook URL
DATA_FILE = "faction_data.json"
CHECK_INTERVAL = 3 

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

def send_notification_for_member(username, tractate_count):
    """Send notification for a single member's activity."""
    content = f"<@707663433390096384> {username} a tractat un vehicul, vehicule tractate: {tractate_count}"
    send_discord_webhook(content)

def send_initial_summary(member_data):
    """Send an initial summary of all members to the webhook."""
    if not member_data:
        send_discord_webhook("No member data available. Check the scraping configuration.")
        return
    
    # Create a summary message
    summary = "**Current Faction Members Tractari Summary:**\n"
    
    # Sort members by tractate count (highest first)
    sorted_members = sorted(
        member_data.items(), 
        key=lambda x: x[1]['vehicule_tractate'], 
        reverse=True
    )
    
    # Add each member to the summary
    for username, data in sorted_members:
        tractate_count = data['vehicule_tractate']
        summary += f"• **{username}**: {tractate_count} vehicule tractate\n"
    
    # Add a timestamp and total count
    total_tractate = sum(data['vehicule_tractate'] for data in member_data.values())
    summary += f"\n**Total tractari**: {total_tractate}"
    summary += f"\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    # Send to Discord
    send_discord_webhook(summary)

def scrape_faction_data():
    """Scrape member data from the faction page based on the HTML structure provided."""
    try:
        scraper = cloudscraper.create_scraper()  # Cloudflare-aware session

        response = scraper.get(FACTION_PAGE_URL)
        if response.status_code != 200:
            print(f"[{datetime.now()}] Failed to load page. Status code: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', class_='table table-striped table-hover')

        if not table:
            table_container = soup.find('div', class_='table-responsive')
            if table_container:
                table = table_container.find('table')
            if not table:
                print(f"[{datetime.now()}] Could not find the faction table")
                return None

        tbody = table.find('tbody')
        if not tbody:
            print(f"[{datetime.now()}] Could not find the table body")
            return None

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

                # Find all spans with the class pattern for this player
                spans = row.find_all('span', class_=f'points-{player_id}')

                # Extract values in order: tractate, reparate, umplute
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
            return None

        print(f"[{datetime.now()}] Successfully collected data for {len(current_data)} members")
        return current_data

    except Exception as e:
        print(f"[{datetime.now()}] Error scraping data: {str(e)}")
        return None

def notify_member_changes(previous_data, current_data):
    """Notify about members who joined or left the faction."""
    
    # Find new members
    new_members = set(current_data.keys()) - set(previous_data.keys())
    
    # Find members who left
    left_members = set(previous_data.keys()) - set(current_data.keys())
    
    # Send notifications
    for member in new_members:
        message = f"🆕 **New member joined**: {member}"
        send_discord_webhook(message)
    
    for member in left_members:
        message = f"👋 **Member left**: {member}"
        send_discord_webhook(message)
    
    return len(new_members) > 0 or len(left_members) > 0

def main():
    print(f"[{datetime.now()}] Starting faction monitoring script")
    
    # Create the data file if it doesn't exist
    if not os.path.exists(DATA_FILE):
        print(f"[{datetime.now()}] Creating new data file")
        save_current_data({})

    # First run - get initial data
    print(f"[{datetime.now()}] Getting initial faction data...")
    initial_data = scrape_faction_data()
    
    if initial_data:
        # Send initial summary to Discord
        print(f"[{datetime.now()}] Sending initial summary to Discord webhook")
        send_initial_summary(initial_data)
        
        # Save data for future comparisons
        save_current_data(initial_data)
    else:
        error_msg = "Failed to get initial faction data. Please check the script configuration."
        print(f"[{datetime.now()}] {error_msg}")
        send_discord_webhook(error_msg)
        # Don't exit, let's try again in the loop
    
    # Start monitoring loop
    while True:
        try:
            print(f"[{datetime.now()}] Starting monitoring cycle")
            
            # Load previous data
            previous_data = load_previous_data()
            
            # Get current data
            current_data = scrape_faction_data()
            
            if current_data:
                # Check for member changes (joins/leaves)
                member_changes = notify_member_changes(previous_data, current_data)
                
                # If there were member changes, send a new summary
                if member_changes:
                    print(f"[{datetime.now()}] Member changes detected, sending updated summary")
                    send_initial_summary(current_data)
                
                # Check for increases in "Vehicule tractate"
                for username, data in current_data.items():
                    current_tractate = data['vehicule_tractate']
                    
                    # Check if we have previous data for this user
                    if username in previous_data:
                        previous_tractate = previous_data[username]['vehicule_tractate']
                        
                        # If value increased, send notification
                        if current_tractate > previous_tractate:
                            increase_amount = current_tractate - previous_tractate
                            print(f"[{datetime.now()}] {username}'s tractate increased by {increase_amount} (from {previous_tractate} to {current_tractate})")
                            
                            # Send notification for each vehicle towed
                            for i in range(increase_amount):
                                # Calculate the count for each notification
                                notification_count = previous_tractate + i + 1
                                send_notification_for_member(username, notification_count)
                
                # Save current data for next comparison
                save_current_data(current_data)
            else:
                print(f"[{datetime.now()}] Failed to get current faction data")
            
            # Wait for next check
            print(f"[{datetime.now()}] Sleeping for {CHECK_INTERVAL} seconds")
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            error_message = f"Error in monitoring loop: {str(e)}"
            print(f"[{datetime.now()}] {error_message}")
            send_discord_webhook(f"⚠️ **Script Error**: {error_message}")
            time.sleep(60)  # Wait a minute before trying again

if __name__ == "__main__":
    main()
