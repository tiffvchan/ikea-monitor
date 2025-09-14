from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
import smtplib
import email.mime.text
import email.mime.multipart
import os

locations = {
    "etobicoke": {
        "name": "IKEA Etobicoke",
        "url": "https://www.ikea.com/ca/en/stores/events/ikea-etobicoke/",
        "aria_label": "All events at IKEA Etobicoke"
    },
    "north_york": {
        "name": "IKEA North York",
        "url": "https://www.ikea.com/ca/en/stores/events/ikea-north-york/",
        "aria_label": "All events at IKEA North York"
    }
}

def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

def load_previous_events():
    if os.path.exists("previous_events.json"):
        with open("previous_events.json", "r") as f:
            return json.load(f)
    return {"etobicoke": [], "north_york": []}

def save_events(events):
    with open("previous_events.json", "w") as f:
        json.dump(events, f, indent=2)

def find_new_events(current, previous):
    # Compare by title+date for simplicity
    prev_set = set((e['title'], e['date']) for e in previous)
    return [e for e in current if (e['title'], e['date']) not in prev_set]

def make_full_url(url):
    if url.startswith("/"):
        return f"https://www.ikea.com{url}"
    return url

def send_email(new_events_by_location, config):
    email_cfg = config['notifications']['email']
    if not email_cfg.get('enabled', False):
        return
    total_new = sum(len(events) for events in new_events_by_location.values())
    if total_new == 0:
        return
    msg = email.mime.multipart.MIMEMultipart()
    msg['From'] = email_cfg['sender_email']
    msg['To'] = email_cfg['recipient_email']
    msg['Subject'] = f"IKEA Events Update - {total_new} New Events"
    body = f"Found {total_new} new events at IKEA locations:\n\n"
    for loc, events in new_events_by_location.items():
        if events:
            body += f"{locations[loc]['name']}\n"
            for e in events:
                full_url = make_full_url(e['url'])
                body += f"- {e['title']}\n  Date: {e['date']}\n  URL: {full_url}\n\n"
    msg.attach(email.mime.text.MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP(email_cfg['smtp_server'], email_cfg['smtp_port'])
        server.starttls()
        server.login(email_cfg['sender_email'], email_cfg['sender_password'])
        server.send_message(msg)
        server.quit()
        print("Email notification sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=options)

all_events = {}

for key, loc in locations.items():
    driver.get(loc["url"])
    print(f"Fetching {loc['name']}...")
    time.sleep(5)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    ul = soup.find('ul', attrs={'aria-label': loc["aria_label"]})
    events = []
    if ul:
        for li in ul.find_all('li', recursive=False):
            a = li.find('a', href=True)
            event_url = a['href'] if a else ''
            h3 = li.find('h3')
            title = h3.get_text(strip=True) if h3 else ''
            p = li.find('p')
            date = p.get_text(strip=True) if p else ''
            if title:
                events.append({
                    "title": title,
                    "date": date,
                    "url": event_url,
                    "location": key,
                    "location_name": loc["name"],
                    "extracted_at": datetime.now().isoformat()
                })
    else:
        print(f"Could not find events <ul> for {loc['name']}!")
    all_events[key] = events

driver.quit()

# Print results
for key, events in all_events.items():
    print(f"\nEvents for {locations[key]['name']}:")
    for event in events:
        print(f"- {event['title']}")
        print(f"  Date: {event['date']}")
        print(f"  URL: {event['url']}")
        print()

# Email notification logic
config = load_config()
previous = load_previous_events()
new_events_by_location = {k: find_new_events(all_events[k], previous.get(k, [])) for k in all_events}
send_email(new_events_by_location, config)

# Save new events
save_events(all_events) 