#!/usr/bin/env python3
"""
IKEA Events Monitor (Multi-Location)
Monitors IKEA Etobicoke and North York events pages daily and sends notifications about new events.
"""

import requests
from bs4 import BeautifulSoup
import json
import hashlib
import time
import schedule
import smtplib
import email.mime.text
import email.mime.multipart
from datetime import datetime
import os
import logging
import re
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ikea_events_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IKEAEventsMonitor:
    def __init__(self, config_file: str = 'config.json'):
        # Multiple IKEA locations to monitor
        self.locations = {
            'etobicoke': {
                'name': 'IKEA Etobicoke',
                'url': 'https://www.ikea.com/ca/en/stores/events/ikea-etobicoke/'
            },
            'north_york': {
                'name': 'IKEA North York', 
                'url': 'https://www.ikea.com/ca/en/stores/events/ikea-north-york/'
            }
        }
        
        self.config_file = config_file
        self.events_file = "previous_events.json"
        self.config = self.load_config()
        
        # HTTP headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def load_config(self) -> Dict:
        """Load configuration from file or create default config."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create default config
            default_config = {
                "notifications": {
                    "email": {
                        "enabled": False,
                        "smtp_server": "smtp.gmail.com",
                        "smtp_port": 587,
                        "sender_email": "your_email@gmail.com",
                        "sender_password": "your_app_password",
                        "recipient_email": "recipient@gmail.com"
                    },
                    "webhook": {
                        "enabled": False,
                        "url": "https://hooks.slack.com/services/your/webhook/url"
                    }
                },
                "check_interval_hours": 24,
                "timeout_seconds": 30
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            logger.info(f"Created default config file: {self.config_file}")
            logger.info("Please update the configuration with your notification settings.")
            return default_config

    def fetch_page_content(self, url: str, location_name: str) -> Optional[str]:
        """Fetch the IKEA events page content for a specific location."""
        try:
            logger.info(f"Fetching content from {location_name}: {url}")
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.config.get('timeout_seconds', 30)
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching page for {location_name}: {e}")
            return None

    def parse_events(self, html_content: str, location_key: str) -> List[Dict]:
        """Parse events from the HTML content and add location info."""
        soup = BeautifulSoup(html_content, 'html.parser')
        events = []
        try:
            if location_key == 'etobicoke':
                # Target the <ul> with aria-label="All events at IKEA Etobicoke"
                ul = soup.find('ul', attrs={'aria-label': 'All events at IKEA Etobicoke'})
                if ul:
                    for li in ul.find_all('li', recursive=False):
                        # Get event link
                        a = li.find('a', href=True)
                        event_url = a['href'] if a else ''
                        # Get event title
                        h3 = li.find('h3')
                        title = h3.get_text(strip=True) if h3 else ''
                        # Get event date/time
                        p = li.find('p')
                        date = p.get_text(strip=True) if p else ''
                        # Compose event dict
                        if title:
                            events.append({
                                'title': title,
                                'date': date,
                                'description': '',
                                'url': event_url,
                                'location': location_key,
                                'location_name': self.locations[location_key]['name'],
                                'extracted_at': datetime.now().isoformat()
                            })
                else:
                    logger.warning('Could not find events <ul> for Etobicoke!')
            else:
                # Fallback to previous logic for other locations
                return super().parse_events(html_content, location_key) if hasattr(super(), 'parse_events') else []
            logger.info(f"Found {len(events)} events at {self.locations[location_key]['name']}")
            return events
        except Exception as e:
            logger.error(f"Error parsing events for {self.locations[location_key]['name']}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def has_event_indicators(self, text: str) -> bool:
        """Check if text contains indicators of being an actual event."""
        text_lower = text.lower()
        
        # Look for date patterns
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
            r'\b\d{1,2}(st|nd|rd|th)\b',  # 1st, 2nd, 3rd, etc.
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(mon|tue|wed|thu|fri|sat|sun)\b'
        ]
        
        has_date = any(re.search(pattern, text_lower) for pattern in date_patterns)
        
        # Look for event keywords
        event_keywords = [
            'workshop', 'class', 'session', 'seminar', 'training',
            'demonstration', 'tour', 'presentation', 'meeting',
            'event', 'activity', 'program', 'course'
        ]
        
        has_event_keyword = any(keyword in text_lower for keyword in event_keywords)
        
        # Look for time patterns
        time_patterns = [
            r'\b\d{1,2}:\d{2}\s*(am|pm|AM|PM)\b',
            r'\b\d{1,2}\s*(am|pm|AM|PM)\b',
            r'\b(morning|afternoon|evening|noon)\b'
        ]
        
        has_time = any(re.search(pattern, text_lower) for pattern in time_patterns)
        
        # Must have either a date or be substantial content with event keywords and time
        return has_date or (has_event_keyword and has_time and len(text) > 100)

    def extract_event_data(self, container, location_key: str) -> Optional[Dict]:
        """Extract event data from a container element with improved parsing."""
        try:
            # Try to find title with multiple strategies
            title = ""
            title_selectors = [
                'h1, h2, h3, h4, h5, h6',
                '[class*="title"]',
                '[class*="heading"]',
                '[class*="name"]'
            ]
            
            for selector in title_selectors:
                title_elem = container.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    break
            
            # If no title found, use first significant text
            if not title:
                text_content = container.get_text().strip()
                lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                if lines:
                    title = lines[0][:100]  # First line, max 100 chars
            
            # Try to find date with improved parsing
            date = ""
            date_selectors = [
                'time',
                '[class*="date"]',
                '[class*="when"]',
                '[datetime]'
            ]
            
            for selector in date_selectors:
                date_elem = container.select_one(selector)
                if date_elem:
                    date = date_elem.get_text().strip()
                    # Also check for datetime attribute
                    if not date and date_elem.get('datetime'):
                        date = date_elem.get('datetime')
                    break
            
            # If no date element found, try to extract from text
            if not date:
                text_content = container.get_text()
                date_patterns = [
                    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b',
                    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b',
                    r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
                    r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+\w+\s+\d{1,2}(?:st|nd|rd|th)?\b'
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, text_content, re.IGNORECASE)
                    if match:
                        date = match.group()
                        break
            
            # Get description, avoiding the title
            description = container.get_text().strip()
            if title and title in description:
                description = description.replace(title, '').strip()
            if date and date in description:
                description = description.replace(date, '').strip()
            
            # Clean up description
            description = re.sub(r'\s+', ' ', description)  # Normalize whitespace
            description = description[:500]  # Limit length
            
            # Only return if we have meaningful content
            if title and len(title) > 3:
                return {
                    'title': title,
                    'date': date,
                    'description': description,
                    'location': location_key,
                    'location_name': self.locations[location_key]['name'],
                    'extracted_at': datetime.now().isoformat()
                }
            
        except Exception as e:
            logger.debug(f"Error extracting event data from container: {e}")
        
        return None

    def is_valid_event(self, event_data: Dict) -> bool:
        """Check if extracted event data represents a valid event rather than promotional content."""
        title = event_data.get('title', '').lower()
        description = event_data.get('description', '').lower()
        
        # Must have some meaningful content
        if len(event_data.get('title', '')) < 3:
            return False
        
        # Only filter out the most obvious promotional content
        invalid_keywords = [
            'sign up for', 'log in to', 'create account',
            'newsletter signup', 'follow us on', 'social media',
            'customer service', 'contact us', 'store hours',
            'directions to store', 'parking information',
            'return policy', 'privacy policy', 'terms and conditions',
            'shop online', 'add to cart', 'add to wishlist'
        ]
        
        # Check if title or description contains invalid keywords
        if any(keyword in title or keyword in description for keyword in invalid_keywords):
            return False
        
        # Check for very generic/repetitive titles
        generic_titles = [
            'click here', 'read more', 'view all details'
        ]
        
        if any(generic in title for generic in generic_titles):
            return False
        
        # Be very permissive - if it has a title and isn't obviously promotional, accept it
        return True

    def deduplicate_events(self, events: List[Dict]) -> List[Dict]:
        """Remove duplicate events based on title and content similarity."""
        if not events:
            return events
        
        unique_events = []
        seen_hashes = set()
        
        for event in events:
            # Create a hash based on title and first part of description
            content = f"{event.get('title', '')}{event.get('description', '')[:100]}"
            content_hash = hashlib.md5(content.lower().encode()).hexdigest()
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_events.append(event)
        
        return unique_events

    def load_previous_events(self) -> Dict[str, List[Dict]]:
        """Load previously stored events organized by location."""
        try:
            with open(self.events_file, 'r') as f:
                data = json.load(f)
                # Handle legacy format (flat list) and convert to location-based format
                if isinstance(data, list):
                    return {'etobicoke': data, 'north_york': []}
                return data
        except FileNotFoundError:
            return {'etobicoke': [], 'north_york': []}

    def save_events(self, events_by_location: Dict[str, List[Dict]]):
        """Save events to file organized by location."""
        with open(self.events_file, 'w') as f:
            json.dump(events_by_location, f, indent=2)

    def get_content_hash(self, events: List[Dict]) -> str:
        """Generate a hash of the events content."""
        content = json.dumps(events, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    def find_new_events(self, current_events: List[Dict], previous_events: List[Dict]) -> List[Dict]:
        """Find new events by comparing with previous events."""
        if not previous_events:
            return current_events
        
        # Create a set of previous event hashes for comparison
        previous_hashes = set()
        for event in previous_events:
            event_str = f"{event.get('title', '')}{event.get('date', '')}{event.get('description', '')}"
            previous_hashes.add(hashlib.md5(event_str.encode()).hexdigest())
        
        new_events = []
        for event in current_events:
            event_str = f"{event.get('title', '')}{event.get('date', '')}{event.get('description', '')}"
            event_hash = hashlib.md5(event_str.encode()).hexdigest()
            if event_hash not in previous_hashes:
                new_events.append(event)
        
        return new_events

    def send_email_notification(self, new_events_by_location: Dict[str, List[Dict]]):
        """Send email notification about new events from all locations."""
        if not self.config['notifications']['email']['enabled']:
            return
        
        # Count total new events
        total_new_events = sum(len(events) for events in new_events_by_location.values())
        if total_new_events == 0:
            return
            
        try:
            email_config = self.config['notifications']['email']
            
            msg = email.mime.multipart.MIMEMultipart()
            msg['From'] = email_config['sender_email']
            msg['To'] = email_config['recipient_email']
            msg['Subject'] = f"IKEA Events Update - {total_new_events} New Events"
            
            body = f"Found {total_new_events} new events at IKEA locations:\n\n"
            
            # Add each location section
            for location_key, events in new_events_by_location.items():
                if events:  # Only add section if there are events
                    location_name = self.locations[location_key]['name']
                    location_url = self.locations[location_key]['url']
                    
                    body += f"🛏️ {location_name.upper()}\n"
                    body += f"View events: {location_url}\n"
                    body += "=" * 60 + "\n\n"
                    
                    for i, event in enumerate(events, 1):
                        body += f"Event {i}:\n"
                        body += f"Title: {event.get('title', 'N/A')}\n"
                        body += f"Date: {event.get('date', 'N/A')}\n"
                        body += f"Description: {event.get('description', 'N/A')}\n"
                        body += "-" * 50 + "\n\n"
                    
                    body += "\n"
            
            msg.attach(email.mime.text.MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['sender_email'], email_config['sender_password'])
            server.send_message(msg)
            server.quit()
            
            logger.info("Email notification sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    def send_webhook_notification(self, new_events_by_location: Dict[str, List[Dict]]):
        """Send webhook notification (e.g., to Slack) for all locations."""
        if not self.config['notifications']['webhook']['enabled']:
            return
        
        try:
            webhook_url = self.config['notifications']['webhook']['url']
            
            # Count total new events
            total_new_events = sum(len(events) for events in new_events_by_location.values())
            if total_new_events == 0:
                return
            
            message = f"🛏️ IKEA Events Update!\n\nFound {total_new_events} new events across all locations:\n\n"
            
            # Add each location section
            for location_key, events in new_events_by_location.items():
                if events:  # Only add section if there are events
                    location_name = self.locations[location_key]['name']
                    location_url = self.locations[location_key]['url']
                    
                    message += f"🛏️ {location_name.upper()}\n"
                    message += f"View events: {location_url}\n"
                    message += "=" * 60 + "\n\n"
                    
                    for i, event in enumerate(events, 1):
                        message += f"{i}. **{event.get('title', 'N/A')}**\n"
                        if event.get('date'):
                            message += f"   📅 {event.get('date')}\n"
                        message += f"   📝 {event.get('description', 'N/A')[:200]}...\n\n"
                    
                    message += "\n"
            
            message += f"View all events: https://www.ikea.com/ca/en/stores/events/"
            
            payload = {
                'text': message
            }
            
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Webhook notification sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")

    def check_for_updates(self):
        """Main method to check for updates at all locations."""
        logger.info("Starting IKEA events check for all locations...")
        
        # Load previous events
        previous_events_by_location = self.load_previous_events()
        current_events_by_location = {}
        new_events_by_location = {}
        
        # Check each location
        for location_key, location_info in self.locations.items():
            logger.info(f"Checking {location_info['name']}...")
            
            # Fetch current page content
            html_content = self.fetch_page_content(location_info['url'], location_info['name'])
            if not html_content:
                logger.error(f"Failed to fetch page content for {location_info['name']}")
                current_events_by_location[location_key] = []
                new_events_by_location[location_key] = []
                continue
            
            # Parse events from the page
            current_events = self.parse_events(html_content, location_key)
            current_events_by_location[location_key] = current_events
            
            if not current_events:
                logger.warning(f"No events found on {location_info['name']} page")
                new_events_by_location[location_key] = []
                continue
            
            # Find new events for this location
            previous_events = previous_events_by_location.get(location_key, [])
            new_events = self.find_new_events(current_events, previous_events)
            new_events_by_location[location_key] = new_events
            
            if new_events:
                logger.info(f"Found {len(new_events)} new events at {location_info['name']}!")
            else:
                logger.info(f"No new events found at {location_info['name']}")
        
        # Send notifications if there are any new events
        total_new_events = sum(len(events) for events in new_events_by_location.values())
        if total_new_events > 0:
            logger.info(f"Found {total_new_events} total new events across all locations!")
            self.send_email_notification(new_events_by_location)
            self.send_webhook_notification(new_events_by_location)
        else:
            logger.info("No new events found at any location")
        
        # Save current events
        self.save_events(current_events_by_location)

    def run_scheduler(self):
        """Run the scheduler to check for updates periodically."""
        interval_hours = self.config.get('check_interval_hours', 24)
        
        # Schedule the job
        schedule.every(interval_hours).hours.do(self.check_for_updates)
        
        logger.info(f"Scheduler started. Will check every {interval_hours} hours.")
        logger.info("Press Ctrl+C to stop.")
        
        # Run initial check
        self.check_for_updates()
        
        # Keep the scheduler running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute if it's time to run

def main():
    """Main function."""
    monitor = IKEAEventsMonitor()
    
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == '--once':
            # Run once and exit
            monitor.check_for_updates()
        elif sys.argv[1] == '--config':
            # Show config file location
            print(f"Config file: {monitor.config_file}")
            print("Update this file with your notification settings.")
        else:
            print("Usage:")
            print("  python ikea_events_monitor.py         # Run scheduler")
            print("  python ikea_events_monitor.py --once  # Run once")
            print("  python ikea_events_monitor.py --config # Show config info")
    else:
        # Run scheduler
        try:
            monitor.run_scheduler()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")

if __name__ == "__main__":
    main() 