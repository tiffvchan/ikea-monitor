#!/bin/bash

echo "🛏️ IKEA Etobicoke Events Monitor Setup"
echo "======================================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

echo "✅ Python 3 found"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3 first."
    exit 1
fi

echo "✅ pip3 found"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Make the script executable
chmod +x ikea_events_monitor.py

# Create initial config
echo "⚙️ Creating initial configuration..."
python3 ikea_events_monitor.py --config

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config.json to configure your notification settings"
echo "2. Run the script:"
echo "   • Test once: python3 ikea_events_monitor.py --once"
echo "   • Run scheduler: python3 ikea_events_monitor.py"
echo ""
echo "For automated daily monitoring, consider adding this to your crontab:"
echo "0 9 * * * cd $(pwd) && python3 ikea_events_monitor.py --once" 