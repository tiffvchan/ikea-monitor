# 🛏️ IKEA Etobicoke Events Monitor

A Python script that monitors the IKEA Etobicoke events page daily and sends you notifications when new events are posted.

## Features

- 🔍 **Automatic Monitoring**: Checks the IKEA Etobicoke events page at configurable intervals
- 📧 **Email Notifications**: Sends detailed email alerts about new events
- 🪝 **Webhook Support**: Integrate with Slack, Discord, or other webhook services
- 💾 **Change Detection**: Only notifies about genuinely new events by comparing with previous data
- 📝 **Detailed Logging**: Complete logging for monitoring and debugging
- ⚙️ **Configurable**: Flexible configuration for different notification preferences

## Quick Start

### 1. Setup

```bash
# Clone or download the files to a directory
chmod +x setup.sh
./setup.sh
```

### 2. Configure Notifications

Edit the generated `config.json` file to set up your preferred notification methods:

```json
{
  "notifications": {
    "email": {
      "enabled": true,
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "sender_email": "your_email@gmail.com",
      "sender_password": "your_app_password",
      "recipient_email": "recipient@gmail.com"
    },
    "webhook": {
      "enabled": false,
      "url": "https://hooks.slack.com/services/your/webhook/url"
    }
  },
  "check_interval_hours": 24,
  "timeout_seconds": 30
}
```

### 3. Run the Monitor

```bash
# Test run (checks once and exits)
python3 ikea_events_monitor.py --once

# Run continuously with scheduler
python3 ikea_events_monitor.py
```

## Configuration Options

### Email Notifications

To use Gmail:

1. Enable 2-factor authentication on your Google account
2. Generate an "App Password" for this script
3. Use your email and the app password in the config

### Webhook Notifications

Popular webhook services:

- **Slack**: Create an incoming webhook in your Slack workspace
- **Discord**: Create a webhook in your Discord server
- **Microsoft Teams**: Set up an incoming webhook connector

### Scheduling Options

You can configure different check intervals:

- `"check_interval_hours": 24` - Check once daily
- `"check_interval_hours": 12` - Check twice daily
- `"check_interval_hours": 6` - Check every 6 hours

## Usage Examples

### One-time Check

```bash
python3 ikea_events_monitor.py --once
```

### Continuous Monitoring

```bash
python3 ikea_events_monitor.py
```

### Background Process

```bash
nohup python3 ikea_events_monitor.py > monitor.log 2>&1 &
```

### Using Cron (Alternative to built-in scheduler)

Add to your crontab for daily checks at 9 AM:

```bash
crontab -e
# Add this line:
0 9 * * * cd /path/to/ikea-monitor && python3 ikea_events_monitor.py --once
```

## Files Created

- `config.json` - Configuration settings
- `previous_events.json` - Stores last known events for comparison
- `ikea_events_monitor.log` - Activity log file

## Troubleshooting

### Common Issues

1. **No events found**: The script uses intelligent parsing but IKEA may change their page structure. Check the logs for details.

2. **Email not sending**:

   - Verify your email credentials
   - For Gmail, ensure you're using an App Password, not your regular password
   - Check that "Less secure app access" is enabled (if not using App Password)

3. **Script stops running**: Use `nohup` or run in a screen/tmux session for continuous monitoring.

### Debug Mode

To see more detailed output:

```bash
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from ikea_events_monitor import IKEAEventsMonitor
monitor = IKEAEventsMonitor()
monitor.check_for_updates()
"
```

## Advanced Usage

### Custom Webhook Format

The webhook payload can be customized by modifying the `send_webhook_notification` method. Current format works with Slack/Discord.

### Multiple Recipients

To send emails to multiple recipients, modify the email configuration:

```python
# In the send_email_notification method, change:
msg['To'] = ", ".join(["email1@example.com", "email2@example.com"])
```

### Different Check Times

For more complex scheduling, you can use cron instead of the built-in scheduler:

```bash
# Check every weekday at 9 AM and 5 PM
0 9,17 * * 1-5 cd /path/to/ikea-monitor && python3 ikea_events_monitor.py --once
```

## Privacy & Ethics

This script:

- ✅ Respects robots.txt and reasonable request rates
- ✅ Uses appropriate User-Agent headers
- ✅ Only accesses publicly available information
- ✅ Implements proper error handling and timeouts

Please use responsibly and in accordance with IKEA's terms of service.

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `schedule` - Task scheduling
- `lxml` - XML/HTML parser (faster parsing)

## License

This script is provided as-is for personal use. Please respect IKEA's terms of service and use responsibly.
