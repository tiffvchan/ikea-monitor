#!/usr/bin/env python3

print("🔍 Testing improved IKEA Events Monitor...")

try:
    import json
    
    # Clear previous events
    with open('previous_events.json', 'w') as f:
        json.dump({"etobicoke": [], "north_york": []}, f, indent=2)
    print("✅ Cleared previous events")
    
    # Import and run
    from ikea_events_monitor import IKEAEventsMonitor
    
    monitor = IKEAEventsMonitor()
    print("✅ Created monitor")
    
    print("🔄 Running check...")
    monitor.check_for_updates()
    
    # Check results
    with open('previous_events.json', 'r') as f:
        results = json.load(f)
    
    print("\n📄 RESULTS:")
    print("=" * 40)
    
    for location, events in results.items():
        print(f"\n📍 {location.upper()}:")
        if events:
            for i, event in enumerate(events, 1):
                print(f"  {i}. {event.get('title', 'No title')}")
                if event.get('date'):
                    print(f"     📅 {event.get('date')}")
                print(f"     📝 {event.get('description', '')[:80]}...")
        else:
            print("  No events found")
    
    print("\n✅ Test completed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc() 