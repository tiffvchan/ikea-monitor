#!/usr/bin/env python3
"""
IKEA Events Monitor (Cloud Version)
Monitors IKEA Etobicoke and North York events pages and sends notifications.
Optimized for cloud deployment with environment variable configuration.
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

# Configure logging for cloud environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Only console logging for cloud
    ]
)
logger = logging.getLogger(__name__)

class IKEAEventsMonitorCloud:
    def __init__(self):
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
        
        self.events_file = "previous_events.json"
        self.config = self.load_config_from_env()
        
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

    def load_config_from_env(self) -> Dict:
        """Load configuration from environment variables."""
        # Parse recipient emails (support both single email and comma-separated list)
        recipient_emails_str = os.getenv('RECIPIENT_EMAILS', '') or os.getenv('RECIPIENT_EMAIL', '')
        recipient_emails = [email.strip() for email in recipient_emails_str.split(',') if email.strip()]
        
        config = {
            "notifications": {
                "email": {
                    "enabled": bool(os.getenv('SENDER_EMAIL') and os.getenv('SENDER_PASSWORD') and recipient_emails),
                    "smtp_server": os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                    "smtp_port": int(os.getenv('SMTP_PORT', '587')),
                    "sender_email": os.getenv('SENDER_EMAIL', ''),
                    "sender_password": os.getenv('SENDER_PASSWORD', ''),
                    "recipient_emails": recipient_emails
                },
                "webhook": {
                    "enabled": bool(os.getenv('WEBHOOK_URL')),
                    "url": os.getenv('WEBHOOK_URL', '')
                }
            },
            "check_interval_hours": int(os.getenv('CHECK_INTERVAL_HOURS', '24')),
            "timeout_seconds": int(os.getenv('TIMEOUT_SECONDS', '30'))
        }
        
        logger.info(f"Email notifications: {'enabled' if config['notifications']['email']['enabled'] else 'disabled'}")
        if config['notifications']['email']['enabled']:
            logger.info(f"Recipients: {', '.join(recipient_emails)}")
        logger.info(f"Webhook notifications: {'enabled' if config['notifications']['webhook']['enabled'] else 'disabled'}")
        
        return config

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
            # Look for event containers - try multiple selectors
            event_containers = []
            
            # Method 1: Look for <li> elements containing event links
            li_elements = soup.find_all('li')
            for li in li_elements:
                # Check if this li contains an event link
                event_link = li.find('a', href=True)
                if event_link and '/events/' in event_link.get('href', ''):
                    event_containers.append(li)
            
            # Method 2: Look for sections with event structure
            if not event_containers:
                sections = soup.find_all('section', class_=re.compile(r'sc-'))
                for section in sections:
                    # Check if this section contains event elements
                    h3 = section.find('h3')
                    p = section.find('p')
                    if h3 and p and h3.get_text(strip=True):
                        # Find the parent container
                        parent = section.find_parent('li') or section.find_parent('div')
                        if parent:
                            event_containers.append(parent)
            
            # Parse each event container
            for container in event_containers:
                try:
                    # Get event link
                    event_link = container.find('a', href=True)
                    event_url = event_link.get('href', '') if event_link else ''
                    
                    # Get event title from h3
                    h3 = container.find('h3')
                    title = h3.get_text(strip=True) if h3 else ''
                    
                    # Get event date from p tag
                    p = container.find('p')
                    date = p.get_text(strip=True) if p else ''
                    
                    # Only add if we have a title and it looks like a real event
                    if title and self.is_valid_event_title(title):
                        # Make URL absolute if it's relative
                        if event_url and event_url.startswith('/'):
                            event_url = 'https://www.ikea.com' + event_url
                        
                        events.append({
                            'title': title,
                            'date': date,
                            'description': '',
                            'url': event_url,
                            'location': location_key,
                            'location_name': self.locations[location_key]['name'],
                            'extracted_at': datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    logger.debug(f"Error parsing individual event: {e}")
                    continue
            
            logger.info(f"Found {len(events)} events at {self.locations[location_key]['name']}")
            return events
            
        except Exception as e:
            logger.error(f"Error parsing events for {self.locations[location_key]['name']}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def parse_events_fallback(self, html_content: str, location_key: str) -> List[Dict]:
        """Fallback parsing method for other locations."""
        soup = BeautifulSoup(html_content, 'html.parser')
        events = []
        
        # Look for common event containers
        event_containers = soup.find_all(['div', 'article', 'section'], 
                                       class_=re.compile(r'event|card|item', re.I))
        
        for container in event_containers:
            event_data = self.extract_event_data(container, location_key)
            if event_data and self.is_valid_event(event_data):
                events.append(event_data)
        
        return events

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
        
        # Filter out promotional and marketing content
        invalid_keywords = [
            'sign up for', 'log in to', 'create account',
            'newsletter signup', 'follow us on', 'social media',
            'customer service', 'contact us', 'store hours',
            'directions to store', 'parking information',
            'return policy', 'privacy policy', 'terms and conditions',
            'shop online', 'add to cart', 'add to wishlist',
            'ikea family', 'rewards and instant benefits',
            'business owner', 'meet ikea for business',
            'enjoy rewards', 'instant benefits',
            'family membership', 'loyalty program',
            'credit card', 'ikea card', 'financing',
            'delivery', 'assembly', 'installation',
            'catalog', 'brochure', 'flyer'
        ]
        
        # Check if title or description contains invalid keywords
        if any(keyword in title or keyword in description for keyword in invalid_keywords):
            return False
        
        # Check for very generic/repetitive titles
        generic_titles = [
            'click here', 'read more', 'view all details',
            'learn more', 'find out more', 'discover more'
        ]
        
        if any(generic in title for generic in generic_titles):
            return False
        
        # Look for actual event indicators
        event_indicators = [
            'workshop', 'class', 'session', 'seminar', 'training',
            'demonstration', 'tour', 'presentation', 'meeting',
            'event', 'activity', 'program', 'course', 'lesson',
            'cooking', 'crafting', 'design', 'decorating',
            'sustainability', 'organization', 'storage',
            'kids', 'children', 'family fun', 'story time'
        ]
        
        # Must contain at least one event indicator to be considered valid
        has_event_indicator = any(indicator in title or indicator in description for indicator in event_indicators)
        
        return has_event_indicator

    def is_valid_event_title(self, title: str) -> bool:
        """Check if the title represents a real event, not promotional content."""
        title_lower = title.lower()
        
        # Filter out promotional content
        invalid_keywords = [
            'ikea family', 'rewards and instant benefits', 'enjoy rewards',
            'business owner', 'meet ikea for business', 'family membership',
            'loyalty program', 'credit card', 'ikea card', 'financing',
            'delivery', 'assembly', 'installation', 'catalog', 'brochure',
            'flyer', 'newsletter', 'sign up', 'log in', 'create account',
            'customer service', 'contact us', 'store hours', 'directions',
            'parking', 'return policy', 'privacy policy', 'terms and conditions',
            'shop online', 'add to cart', 'add to wishlist', 'click here',
            'read more', 'view all details', 'learn more', 'find out more'
        ]
        
        # Check if title contains invalid keywords
        if any(keyword in title_lower for keyword in invalid_keywords):
            return False
        
        # Look for actual event indicators
        event_indicators = [
            'workshop', 'class', 'session', 'seminar', 'training',
            'demonstration', 'tour', 'presentation', 'meeting',
            'event', 'activity', 'program', 'course', 'lesson',
            'cooking', 'crafting', 'design', 'decorating',
            'sustainability', 'organization', 'storage',
            'kids', 'children', 'family fun', 'story time',
            'sale', 'warehouse sale', 'clearance', 'special offer',
            'launch', 'opening', 'celebration', 'festival'
        ]
        
        # Must contain at least one event indicator
        return any(indicator in title_lower for indicator in event_indicators)

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
            recipient_emails = email_config['recipient_emails']
            
            if not recipient_emails:
                logger.warning("No recipient emails configured")
                return
            
            msg = email.mime.multipart.MIMEMultipart()
            msg['From'] = email_config['sender_email']
            msg['To'] = ', '.join(recipient_emails)  # Support multiple recipients
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
            server.send_message(msg, to_addrs=recipient_emails)  # Send to all recipients
            server.quit()
            
            logger.info(f"Email notification sent successfully to {len(recipient_emails)} recipient(s): {', '.join(recipient_emails)}")
            
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
    monitor = IKEAEventsMonitorCloud()
    
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == '--once':
            # Run once and exit
            monitor.check_for_updates()
        elif sys.argv[1] == '--config':
            # Show config info
            print("Configuration loaded from environment variables:")
            print(f"Email notifications: {'enabled' if monitor.config['notifications']['email']['enabled'] else 'disabled'}")
            print(f"Webhook notifications: {'enabled' if monitor.config['notifications']['webhook']['enabled'] else 'disabled'}")
            print(f"Check interval: {monitor.config['check_interval_hours']} hours")
        else:
            print("Usage:")
            print("  python ikea_events_monitor_cloud.py         # Run scheduler")
            print("  python ikea_events_monitor_cloud.py --once  # Run once")
            print("  python ikea_events_monitor_cloud.py --config # Show config info")
    else:
        # Run scheduler
        try:
            monitor.run_scheduler()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")

if __name__ == "__main__":
    main()
