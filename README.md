# IKEA Events Monitor

Monitors IKEA Etobicoke and North York events pages and sends email notifications when new events are posted.

## 🚀 Quick Setup

### Local Development

1. Copy the template config: `cp config.json.template config.json`
2. Edit `config.json` with your email settings
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python ikea_events_monitor.py --once`

### Cloud Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions on deploying to Railway, Render, or other platforms.

## 📁 Files

- `ikea_events_monitor.py` - Main script (local version)
- `ikea_events_monitor_cloud.py` - Cloud-optimized version
- `config.json.template` - Configuration template
- `requirements.txt` - Python dependencies
- `DEPLOYMENT_GUIDE.md` - Cloud deployment instructions

## 🔒 Security

- **Never commit** `config.json` with real credentials
- Use environment variables for cloud deployment
- Keep your Gmail app password secure

## 📧 Email Setup

1. Enable 2-factor authentication on Gmail
2. Generate an app password
3. Use the app password in your config (not your regular password)

## 🕐 Scheduling

The script can run:

- **Locally**: Using cron jobs or the built-in scheduler
- **Cloud**: Using Railway, Render, or external cron services

See the deployment guide for cloud setup instructions.
