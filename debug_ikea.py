#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json

def debug_ikea_page():
    print("🔍 Debugging IKEA Etobicoke events page...")
    
    url = "https://www.ikea.com/ca/en/stores/events/ikea-etobicoke/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        print(f"📡 Fetching: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"📄 Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Look for any text containing "BINGO" or "Deal of the Week"
        all_text = soup.get_text()
        
        print("\n🔍 Searching for known events...")
        if "BINGO" in all_text:
            print("✅ Found 'BINGO' in page content")
        else:
            print("❌ 'BINGO' NOT found in page content")
            
        if "Deal of the Week" in all_text:
            print("✅ Found 'Deal of the Week' in page content")
        else:
            print("❌ 'Deal of the Week' NOT found in page content")
        
        # Look for common event-related elements
        print("\n🔍 Analyzing page structure...")
        
        # Check for different types of containers
        containers = {
            'divs': len(soup.find_all('div')),
            'articles': len(soup.find_all('article')),
            'sections': len(soup.find_all('section')),
            'list_items': len(soup.find_all('li')),
            'cards': len(soup.find_all(class_=lambda x: x and 'card' in x.lower())),
            'events': len(soup.find_all(class_=lambda x: x and 'event' in x.lower())),
        }
        
        for container_type, count in containers.items():
            print(f"  {container_type}: {count}")
        
        # Look for elements with substantial text
        print("\n🔍 Looking for content containers...")
        content_containers = []
        
        for tag in ['div', 'article', 'section', 'li']:
            elements = soup.find_all(tag)
            for elem in elements:
                text = elem.get_text().strip()
                if len(text) > 50 and any(keyword in text.lower() for keyword in ['bingo', 'deal', 'event', 'workshop', 'class']):
                    content_containers.append({
                        'tag': tag,
                        'text': text[:200] + '...' if len(text) > 200 else text,
                        'classes': elem.get('class', [])
                    })
        
        print(f"Found {len(content_containers)} potential content containers:")
        for i, container in enumerate(content_containers[:5]):  # Show first 5
            print(f"  {i+1}. <{container['tag']}> classes: {container['classes']}")
            print(f"     Text: {container['text']}")
            print()
        
        # Save the HTML for manual inspection
        with open('ikea_debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("💾 Saved full HTML to 'ikea_debug.html' for manual inspection")
        
        # Save the text content
        with open('ikea_debug_text.txt', 'w', encoding='utf-8') as f:
            f.write(all_text)
        print("💾 Saved text content to 'ikea_debug_text.txt'")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_ikea_page() 