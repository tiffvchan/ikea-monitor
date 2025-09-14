#!/usr/bin/env python3
"""
Selenium-based IKEA events monitor with database support
"""

import os
import smtplib
import email.mime.text
import email.mime.multipart
from datetime import datetime
import logging
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_connection():
    """Get database connection."""
    try:
        # Use Render's DATABASE_URL environment variable
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("No DATABASE_URL found, using file-based storage")
            return None
        
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def init_database():
    """Initialize database table."""
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS previous_events (
                    id SERIAL PRIMARY KEY,
                    event_hash VARCHAR(255) UNIQUE,
                    title TEXT,
                    date TEXT,
                    location TEXT,
                    url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
        logger.info("Database table initialized")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False
    finally:
        conn.close()

def get_previous_events():
    """Get previous events from database."""
    conn = get_database_connection()
    if not conn:
        return {}
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT event_hash FROM previous_events")
            rows = cur.fetchall()
            return {row['event_hash']: True for row in rows}
    except Exception as e:
        logger.error(f"Error getting previous events: {e}")
        return {}
    finally:
        conn.close()

def save_previous_events(events):
    """Save events to database."""
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            for event in events:
                event_hash = get_event_hash(event)
                cur.execute("""
                    INSERT INTO previous_events (event_hash, title, date, location, url)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (event_hash) DO NOTHING
                """, (event_hash, event['title'], event['date'], event['location'], event['url']))
        conn.commit()
        logger.info(f"Saved {len(events)} events to database")
        return True
    except Exception as e:
        logger.error(f"Error saving events: {e}")
        return False
    finally:
        conn.close()

def get_driver():
    """Get a Chrome WebDriver instance."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Failed to create Chrome driver: {e}")
        return None

def scrape_ikea_events(url, location_name):
    """Scrape events from IKEA page using Selenium."""
    driver = None
    events = []
    seen_events = set()
    
    try:
        logger.info(f"Scraping {location_name}: {url}")
        
        driver = get_driver()
        if not driver:
            return events
            
        driver.get(url)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        import time
        time.sleep(5)
        
        try:
            event_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'BINGO') or contains(text(), 'Warehouse') or contains(text(), 'workshop') or contains(text(), 'class')]")
            
            for element in event_elements:
                try:
                    parent = element.find_element(By.XPATH, "./ancestor::li[1]")
                    
                    title_elem = parent.find_elements(By.TAG_NAME, "h3")
                    date_elem = parent.find_elements(By.TAG_NAME, "p")
                    link_elem = parent.find_elements(By.TAG_NAME, "a")
                    
                    if title_elem and link_elem:
                        title = title_elem[0].text.strip()
                        date = date_elem[0].text.strip() if date_elem else ""
                        url = link_elem[0].get_attribute('href')
                        
                        if title and len(title) > 5:
                            event_key = f"{title}|{date}|{url}"
                            if event_key not in seen_events:
                                seen_events.add(event_key)
                                events.append({
                                    'title': title,
                                    'date': date,
                                    'url': url,
                                    'location': location_name
                                })
                                logger.info(f"Found event: {title}")
                            
                except Exception as e:
                    continue
                    
        except Exception as e:
            logger.debug(f"Strategy 1 failed: {e}")
        
        if not events:
            try:
                event_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/events/')]")
                logger.info(f"Found {len(event_links)} event links")
                
                for link in event_links:
                    try:
                        parent = link.find_element(By.XPATH, "./ancestor::li[1]")
                        
                        title_elem = parent.find_elements(By.TAG_NAME, "h3")
                        date_elem = parent.find_elements(By.TAG_NAME, "p")
                        
                        if title_elem:
                            title = title_elem[0].text.strip()
                            date = date_elem[0].text.strip() if date_elem else ""
                            url = link.get_attribute('href')
                            
                            if title and len(title) > 5:
                                event_key = f"{title}|{date}|{url}"
                                if event_key not in seen_events:
                                    seen_events.add(event_key)
                                    events.append({
                                        'title': title,
                                        'date': date,
                                        'url': url,
                                        'location': location_name
                                    })
                                    logger.info(f"Found event: {title}")
                                
                    except Exception as e:
                        continue
                        
            except Exception as e:
                logger.debug(f"Strategy 2 failed: {e}")
        
        logger.info(f"Found {len(events)} unique events for {location_name}")
        return events
        
    except Exception as e:
        logger.error(f"Error scraping {location_name}: {e}")
        return events
    finally:
        if driver:
            driver.quit()

def get_event_hash(event):
    """Create a unique hash for an event."""
    event_string = f"{event['title']}|{event['date']}|{event['location']}"
    return hashlib.md5(event_string.encode()).hexdigest()

def find_new_events(current_events, previous_events):
    """Find events that are new since last check."""
    new_events = []
    
    for event in current_events:
        event_hash = get_event_hash(event)
        if event_hash not in previous_events:
            new_events.append(event)
            logger.info(f"New event found: {event['title']}")
    
    return new_events

def send_email(events):
    """Send email notification about events."""
    if not events:
        return
        
    try:
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipient_emails = os.getenv('RECIPIENT_EMAILS', '').split(',')
        
        if not sender_email or not sender_password or not recipient_emails:
            logger.warning("Email credentials not configured")
            return
        
        msg = email.mime.multipart.MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipient_emails)
        msg['Subject'] = f"IKEA Events Update - {len(events)} New Events"
        
        body = f"Found {len(events)} NEW IKEA events:\n\n"
        
        for i, event in enumerate(events, 1):
            body += f"Event {i}:\n"
            body += f"Title: {event['title']}\n"
            body += f"Date: {event['date']}\n"
            body += f"Location: {event['location']}\n"
            body += f"URL: {event['url']}\n"
            body += "-" * 50 + "\n\n"
        
        msg.attach(email.mime.text.MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg, to_addrs=recipient_emails)
        server.quit()
        
        logger.info(f"Email sent successfully to {len(recipient_emails)} recipients")
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")

def main():
    """Main function."""
    # Initialize database
    if not init_database():
        logger.warning("Database initialization failed, continuing without duplicate prevention")
    
    locations = [
        {
            'name': 'IKEA Etobicoke',
            'url': 'https://www.ikea.com/ca/en/stores/events/ikea-etobicoke/'
        },
        {
            'name': 'IKEA North York',
            'url': 'https://www.ikea.com/ca/en/stores/events/ikea-north-york/'
        }
    ]
    
    # Get previous events
    previous_events = get_previous_events()
    logger.info(f"Loaded {len(previous_events)} previous events from database")
    
    all_events = []
    
    for location in locations:
        events = scrape_ikea_events(location['url'], location['name'])
        all_events.extend(events)
    
    if all_events:
        logger.info(f"Found {len(all_events)} total events")
        
        # Find new events
        new_events = find_new_events(all_events, previous_events)
        
        if new_events:
            logger.info(f"Found {len(new_events)} NEW events")
            send_email(new_events)
            
            # Save all current events to database
            save_previous_events(all_events)
        else:
            logger.info("No new events found - no email sent")
    else:
        logger.info("No events found")

if __name__ == "__main__":
    main()
