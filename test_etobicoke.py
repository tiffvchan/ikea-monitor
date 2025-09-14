#!/usr/bin/env python3

import json
from ikea_events_monitor import IKEAEventsMonitor

# Clear previous events
with open('previous_events.json', 'w') as f:
    json.dump({"etobicoke": [], "north_york": []}, f, indent=2)

monitor = IKEAEventsMonitor()
monitor.check_for_updates()

with open('previous_events.json', 'r') as f:
    data = json.load(f)

print("\nEvents found for Etobicoke:")
for i, event in enumerate(data['etobicoke'], 1):
    print(f"{i}. {event['title']}")
    print(f"   Date: {event['date']}")
    print(f"   URL: {event['url']}")
    print() 