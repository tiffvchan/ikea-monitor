from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

url = "https://www.ikea.com/ca/en/stores/events/ikea-etobicoke/"

options = Options()
options.add_argument("--headless")  # Run in headless mode (no window)
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

# You may need to specify the path to chromedriver if not in PATH
# driver = webdriver.Chrome(executable_path="/opt/homebrew/bin/chromedriver", options=options)
driver = webdriver.Chrome(options=options)
driver.get(url)

# Wait for JavaScript to load content
print("Waiting for page to load JS events...")
time.sleep(5)  # You can increase this if needed

html = driver.page_source
driver.quit()

soup = BeautifulSoup(html, "html.parser")
ul = soup.find('ul', attrs={'aria-label': 'All events at IKEA Etobicoke'})
if ul:
    for li in ul.find_all('li', recursive=False):
        a = li.find('a', href=True)
        event_url = a['href'] if a else ''
        h3 = li.find('h3')
        title = h3.get_text(strip=True) if h3 else ''
        p = li.find('p')
        date = p.get_text(strip=True) if p else ''
        print(f"Title: {title}")
        print(f"Date: {date}")
        print(f"URL: {event_url}")
        print()
else:
    print("Could not find events <ul> for Etobicoke!") 