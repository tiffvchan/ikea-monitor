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
import re
from urllib.parse import urlparse
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

NOISE_TITLE_PATTERNS = [
    "all events",
    "ikea etobicoke",
    "ikea north york",
    "logged in",
    "create an account",
    "join our events",
]

NOISE_DATE_PATTERNS = [
    "you need to be logged in",
    "create an account",
    "no registration required",
]

MONTH_PATTERN = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


def normalize_whitespace(value):
    return " ".join((value or "").split())


def split_nonempty_lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def is_noise_title(value):
    normalized = normalize_whitespace(value).lower()
    if not normalized:
        return True
    return any(pattern in normalized for pattern in NOISE_TITLE_PATTERNS)


def is_noise_date(value):
    normalized = normalize_whitespace(value).lower()
    if not normalized:
        return True
    return any(pattern in normalized for pattern in NOISE_DATE_PATTERNS)


def looks_like_date_line(value):
    normalized = normalize_whitespace(value)
    lowered = normalized.lower()
    return bool(
        normalized
        and (
            MONTH_PATTERN.search(normalized)
            or " a.m." in lowered
            or " p.m." in lowered
            or " et" in lowered
            or " am " in lowered
            or " pm " in lowered
        )
    )


def is_event_detail_url(event_url, location_name):
    """Keep only real store event detail pages."""
    try:
        parsed = urlparse(event_url)
        path = (parsed.path or "").lower().rstrip("/")
        if not path.startswith("/ca/en/stores/events/"):
            return False
        # Exclude generic listing root pages.
        if path in {"/ca/en/stores/events", "/ca/en/stores/events/ikea-etobicoke", "/ca/en/stores/events/ikea-north-york"}:
            return False
        store_slug = location_name.lower().replace(" ", "-")
        return f"/stores/events/{store_slug}/" in path
    except Exception:
        return False


def normalize_event_url(url):
    """Stable key for deduplication across runs (query/fragment and casing ignored)."""
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip())
        if not parsed.netloc:
            return ""
        path = (parsed.path or "").rstrip("/").lower()
        if "/stores/events/" not in path:
            return ""
        host = (parsed.netloc or "").lower()
        return f"{host}{path}"
    except Exception:
        return ""


def extract_title_and_date_from_text(raw_text):
    lines = split_nonempty_lines(raw_text)
    if not lines:
        return "", ""

    title = ""
    date = ""

    for line in lines:
        if len(line) > 5 and not is_noise_title(line) and not looks_like_date_line(line):
            title = line
            break

    # Fallback when event card text is sparse and title line is missing.
    if not title:
        for line in lines:
            if len(line) > 5 and not is_noise_title(line):
                title = line
                break

    for line in lines:
        candidate = normalize_whitespace(line)
        if candidate == title:
            continue
        if is_noise_date(candidate):
            continue
        if looks_like_date_line(candidate):
            date = candidate
            break

    return title, date

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
    """Load prior event identity from DB (hashes + normalized URLs)."""
    empty = {"hashes": set(), "urls": set()}
    conn = get_database_connection()
    if not conn:
        return empty

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT event_hash, url FROM previous_events")
            rows = cur.fetchall()
        hashes = {row["event_hash"] for row in rows if row.get("event_hash")}
        urls = set()
        for row in rows:
            nu = normalize_event_url(row.get("url") or "")
            if nu:
                urls.add(nu)
        return {"hashes": hashes, "urls": urls}
    except Exception as e:
        logger.error(f"Error getting previous events: {e}")
        return empty
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

def cleanup_old_events(days_to_keep=30):
    """Delete events older than specified days."""
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Delete events older than specified days
            cur.execute("""
                DELETE FROM previous_events 
                WHERE created_at < NOW() - INTERVAL '%s days'
            """, (days_to_keep,))
            
            deleted_count = cur.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old events (older than {days_to_keep} days)")
            else:
                logger.info("No old events to clean up")
            
            return True
    except Exception as e:
        logger.error(f"Error cleaning up old events: {e}")
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
        time.sleep(6)

        # IKEA event cards are often rendered after initial load; scroll to trigger lazy loading.
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
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
                        event_url = link.get_attribute('href')
                        if not event_url or not is_event_detail_url(event_url, location_name):
                            continue

                        title, date = extract_title_and_date_from_text(link.text or "")
                        if not title:
                            # Support newer IKEA markup where title is nested under different heading tags.
                            title_candidates = link.find_elements(By.XPATH, ".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::span]")
                            for candidate in title_candidates:
                                candidate_title, candidate_date = extract_title_and_date_from_text(candidate.text or "")
                                if candidate_title:
                                    title = candidate_title
                                    if not date and candidate_date:
                                        date = candidate_date
                                    break

                        if not title:
                            # Try nearby container text when link text is empty.
                            container = link.find_element(By.XPATH, "./ancestor::*[self::article or self::section or self::div][1]")
                            title_candidates = container.find_elements(By.XPATH, ".//*[self::h1 or self::h2 or self::h3 or self::h4]")
                            for candidate in title_candidates:
                                candidate_title, _ = extract_title_and_date_from_text(candidate.text or "")
                                if candidate_title:
                                    title = candidate_title
                                    break

                        if not title or len(title) <= 5 or is_noise_title(title):
                            continue

                        if not date:
                            try:
                                container = link.find_element(By.XPATH, "./ancestor::*[self::article or self::section or self::div][1]")
                                container_text = container.text or ""
                                _, container_date = extract_title_and_date_from_text(container_text)
                                if container_date:
                                    date = container_date
                            except Exception:
                                pass

                        date = normalize_whitespace(date)
                        if is_noise_date(date):
                            date = ""

                        event_key = f"{title}|{date}|{event_url}"
                        if event_key not in seen_events:
                            seen_events.add(event_key)
                            events.append({
                                'title': title,
                                'date': date,
                                'url': event_url,
                                'location': location_name
                            })
                            logger.info(f"Found event: {title}")
                                
                    except Exception as e:
                        continue
                        
            except Exception as e:
                logger.debug(f"Strategy 2 failed: {e}")

        if not events:
            # Extra diagnostics to explain "0 events" cases in CI logs.
            all_links = driver.find_elements(By.TAG_NAME, "a")
            event_like_links = [a for a in all_links if "/events/" in (a.get_attribute("href") or "")]
            logger.warning(
                "No events extracted for %s. total_links=%d event_like_links=%d page_title=%s current_url=%s",
                location_name,
                len(all_links),
                len(event_like_links),
                driver.title,
                driver.current_url,
            )
        
        logger.info(f"Found {len(events)} unique events for {location_name}")
        return events
        
    except Exception as e:
        logger.error(f"Error scraping {location_name}: {e}")
        return events
    finally:
        if driver:
            driver.quit()

def legacy_event_hash(event):
    """Old identity: title/date/location can drift between scrapes — kept for DB migration."""
    event_string = f"{event['title']}|{event['date']}|{event['location']}"
    return hashlib.md5(event_string.encode()).hexdigest()


def get_event_hash(event):
    """Primary identity: normalized event URL (stable). Falls back if URL missing."""
    nu = normalize_event_url(event.get("url") or "")
    if nu:
        return hashlib.md5(nu.encode()).hexdigest()
    return legacy_event_hash(event)


def find_new_events(current_events, previous_events):
    """Find events that are new since last check."""
    new_events = []
    hashes = previous_events.get("hashes") or set()
    urls = previous_events.get("urls") or set()
    seen_urls_this_run = set()

    for event in current_events:
        nu = normalize_event_url(event.get("url") or "")
        if nu:
            if nu in urls or nu in seen_urls_this_run:
                continue
        h = get_event_hash(event)
        if h in hashes:
            continue
        if legacy_event_hash(event) in hashes:
            continue
        if nu:
            seen_urls_this_run.add(nu)
        new_events.append(event)
        logger.info(f"New event found: {event['title']}")

    return new_events

def send_email(events):
    """Send email notification about events."""
    if not events:
        logger.info("send_email called with no events")
        return
        
    try:
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipient_emails = [email.strip() for email in os.getenv('RECIPIENT_EMAILS', '').split(',') if email.strip()]
        
        if not sender_email or not sender_password or not recipient_emails:
            logger.warning(
                "Email not configured: sender_email=%s sender_password_set=%s recipients=%d",
                bool(sender_email),
                bool(sender_password),
                len(recipient_emails),
            )
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
            body += "-" * 45 + "\n\n"
        
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
    
    # Clean up old events (keep last 30 days)
    cleanup_old_events(days_to_keep=30)
    
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
    logger.info(
        "Loaded %d previous hashes and %d known event URLs from database",
        len(previous_events["hashes"]),
        len(previous_events["urls"]),
    )
    
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
