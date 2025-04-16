import requests
import json
import time
import random
from bs4 import BeautifulSoup
import os
from datetime import datetime
import cloudscraper
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("faction_tracker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
FACTION_PAGE_URL = "https://panel.b-hood.ro/factions/members/8"  # Replace with actual URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1361717456858513488/_pTEH2xeuMLbjvBS1kBU-4Jd97jfI2XVVbImfiytjRGRlI8aOK6kNnSvL9nGG8KSp5gB"  # Your webhook URL
DATA_FILE = "faction_data.json"
CHECK_INTERVAL = 3  # Increased to reduce detection chance
MAX_RETRIES = 3
BROWSER_FALLBACK = True  # Set to True to enable Selenium fallback

# Create modern browser headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ro;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "DNT": "1"
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
        logger.error(f"Error loading data file: {str(e)}")
        # Create a new empty data file
        save_current_data({})
        return {}

def save_current_data(data):
    """Save current member data to file."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data file: {str(e)}")

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

        if response.status_code in [200, 204]:
            logger.info("Webhook sent successfully")
            return response.json() if response.status_code == 200 else None
        else:
            logger.error(f"Failed to send webhook. Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error sending webhook: {str(e)}")
        return None


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
       status = data.get('status', 'unknown')  # Fallback to 'unknown' if status not found
       summary += f"• **{username}**: {tractate_count} vehicule tractate — **{status.upper()}**\n"

    # Add a timestamp and total count
    total_tractate = sum(data['vehicule_tractate'] for data in member_data.values())
    summary += f"\n**Total tractari**: {total_tractate}"
    summary += f"\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    # Send to Discord
    send_discord_webhook(summary)

def get_page_with_cloudscraper():
    """Try to get the page content using cloudscraper."""
    try:
        # Create a scraper instance
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            },
            delay=random.uniform(1, 3)  # Random delay
        )
        
        # Add some randomized delays and behavior
        time.sleep(random.uniform(1, 3))
        
        # Make the request
        response = scraper.get(FACTION_PAGE_URL)
        
        if response.status_code == 200:
            logger.info("Successfully retrieved page with cloudscraper")
            return response.text
        else:
            logger.warning(f"Failed to get page with cloudscraper. Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error using cloudscraper: {str(e)}")
        return None

def get_page_with_selenium():
    """Use Selenium to bypass Cloudflare protection."""
    driver = None
    try:
        logger.info("Attempting to use Selenium for retrieval")
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")
        
        # Use webdriver manager to handle driver installation
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException:
            # Fallback for Google Cloud VM
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=options)
        
        # Navigate to the page and wait for Cloudflare to resolve
        driver.get(FACTION_PAGE_URL)
        time.sleep(10)  # Wait for Cloudflare challenge to complete
        
        # Get the page source after Cloudflare has been bypassed
        page_content = driver.page_source
        logger.info("Successfully retrieved page with Selenium")
        return page_content
    except Exception as e:
        logger.error(f"Error using Selenium: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()

def get_status_from_color(row):
    """Get status based on the color indicator in the <i> tag."""
    try:
        color_icon = row.find('i', class_='fa fa-circle fa-fw')
        if not color_icon:
            return "unknown"
        color = color_icon.get('style', '').lower()
        if 'color:red' in color:
            return '🔴'
        elif 'color:orange' in color:
            return '🟡'
        elif 'color:green' in color:
            return '🟢'
        else:
            return 'unknown'
    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}")
        return "unknown"
           

def extract_member_data_from_html(html_content):
    """Extract member data from the HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', class_='table table-striped table-hover')

        if not table:
            table_container = soup.find('div', class_='table-responsive')
            if table_container:
                table = table_container.find('table')
            if not table:
                logger.error("Could not find the faction table")
                return None

        tbody = table.find('tbody')
        if not tbody:
            logger.error("Could not find the table body")
            return None

        member_rows = tbody.find_all('tr')
        logger.info(f"Found {len(member_rows)} member rows")

        current_data = {}

        for row in member_rows:
            try:
                username_element = row.find('a')
                if not username_element:
                    continue

                username = username_element.text.strip()
                player_id = username_element.get('id')  # Extract player ID like '195032'
                if not player_id:
                    logger.info(f"Skipping {username} (no ID found)")
                    continue

                # Find all spans with the class pattern for this player
                spans = row.find_all('span', class_=f'points-{player_id}')

                # Extract values in order: tractate, reparate, umplute
                tractate_value = int(spans[0].text.strip()) if len(spans) > 0 else 0
                reparate_value = int(spans[1].text.strip()) if len(spans) > 1 else 0
                umplute_value = int(spans[2].text.strip()) if len(spans) > 2 else 0

                status = get_status_from_color(row)

                current_data[username] = {
    'vehicule_tractate': tractate_value,
    'vehicule_reparate': reparate_value,
    'rezervoare_umplute': umplute_value,
    'status': status,
    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}


                logger.debug(f"Data for {username}: tractate={tractate_value}, reparate={reparate_value}, umplute={umplute_value}")
            except Exception as e:
                logger.error(f"Error processing row: {str(e)}")
                continue

        if not current_data:
            logger.error("No member data found")
            return None

        logger.info(f"Successfully collected data for {len(current_data)} members")
        return current_data

    except Exception as e:
        logger.error(f"Error extracting data: {str(e)}")
        return None

def scrape_faction_data():
    """Scrape member data with retries and multiple methods."""
    for attempt in range(MAX_RETRIES):
        logger.info(f"Scraping attempt {attempt + 1}/{MAX_RETRIES}")
        
        # First try cloudscraper
        html_content = get_page_with_cloudscraper()
        
        # If cloudscraper fails and browser fallback is enabled, try Selenium
        if html_content is None and BROWSER_FALLBACK:
            logger.info("Cloudscraper failed, trying Selenium fallback")
            html_content = get_page_with_selenium()
        
        # If we have HTML content, try to extract the data
        if html_content:
            data = extract_member_data_from_html(html_content)
            if data:
                return data
        
        # If we get here, the attempt failed
        logger.warning(f"Attempt {attempt + 1} failed, waiting before retry")
        time.sleep(random.uniform(5, 10))  # Wait between retries
    
    logger.error("All scraping attempts failed")
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
    
def notify_status_changes(previous_data, current_data):
    """Notify when a member changes their status (online/afk/offline)."""
    for username, current_info in current_data.items():
        previous_status = previous_data.get(username, {}).get("status")
        current_status = current_info.get("status")
        if previous_status and current_status and previous_status != current_status:
            message = f"🔄 **Status Change**: **{username}** is now **{current_status.upper()}** (was {previous_status.upper()}) -- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_discord_webhook(message)


def main():
    logger.info("Starting faction monitoring script")
    
    # Create the data file if it doesn't exist
    if not os.path.exists(DATA_FILE):
        logger.info("Creating new data file")
        save_current_data({})
    
    # First run - get initial data
    logger.info("Getting initial faction data...")
    initial_data = scrape_faction_data()
    
    if initial_data:
        # Send initial summary to Discord
        logger.info("Sending initial summary to Discord webhook")
        send_initial_summary(initial_data)
        
        # Save data for future comparisons
        save_current_data(initial_data)
    else:
        error_msg = "Failed to get initial faction data. Please check the script configuration."
        logger.error(error_msg)
        send_discord_webhook(error_msg)
    
    # Start monitoring loop
    while True:
        try:
            logger.info("Starting monitoring cycle")
            
            # Add random delay to appear more human-like
            sleep_time = CHECK_INTERVAL + random.uniform(1, 5)
            logger.info(f"Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            
            # Load previous data
            previous_data = load_previous_data()
            
            # Get current data
            current_data = scrape_faction_data()
            
            if current_data:
                # Check for member changes (joins/leaves)
                member_changes = notify_member_changes(previous_data, current_data)
                
                # If there were member changes, send a new summary
                notify_status_changes(previous_data, current_data)

                if member_changes:
                    logger.info("Member changes detected, sending updated summary")
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
                            logger.info(f"{username}'s tractate increased by {increase_amount} (from {previous_tractate} to {current_tractate})")
                            
                            # Send notification for each vehicle towed
                            for i in range(increase_amount):
                                # Calculate the count for each notification
                                notification_count = previous_tractate + i + 1
                                send_notification_for_member(username, notification_count)
                
                # Save current data for next comparison
                save_current_data(current_data)
            else:
                logger.error("Failed to get current faction data")
            
        except Exception as e:
            error_message = f"Error in monitoring loop: {str(e)}"
            logger.error(error_message)
            send_discord_webhook(f"⚠️ **Script Error**: {error_message}")
            time.sleep(60)  # Wait a minute before trying again

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script terminated by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        send_discord_webhook(f"🚨 **Critical Error**: Script crashed with error: {str(e)}")
