# IKEA Monitor - Cloud Deployment Guide

This guide will help you deploy your IKEA events monitor to a reliable cloud hosting platform.

## 🚀 Quick Start - Railway.app (Recommended)

### Step 1: Prepare Your Repository

1. Push your code to GitHub (if not already done)
2. Make sure you have these files in your repo:
   - `ikea_events_monitor_cloud.py` (cloud-optimized version)
   - `requirements.txt`
   - `railway.json`
   - `Procfile`

### Step 2: Deploy to Railway

1. Go to [Railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your IKEA monitor repository
5. Railway will automatically detect it's a Python project

### Step 3: Configure Environment Variables

In Railway dashboard, go to your project → Variables tab and add:

```
SENDER_EMAIL=tiffanyvchan@gmail.com
SENDER_PASSWORD=efhv hwcr tnfs sgaw
RECIPIENT_EMAILS=tiffanyvchan@gmail.com,friend@gmail.com,family@gmail.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
CHECK_INTERVAL_HOURS=24
TIMEOUT_SECONDS=30
```

### Step 4: Set Up Cron Job

1. In Railway dashboard, go to your project
2. Click on "Cron" tab
3. Add a new cron job:
   - **Command**: `python ikea_events_monitor_cloud.py --once`
   - **Schedule**: `0 12,17 * * *` (runs at 12 PM and 5 PM daily)
   - **Timezone**: Your local timezone

### Step 5: Test

1. Railway will automatically deploy your app
2. Check the logs to ensure it's running
3. Test the cron job manually first

---

## 🔄 Alternative: Render.com

### Step 1: Deploy to Render

1. Go to [Render.com](https://render.com)
2. Sign up and connect GitHub
3. Create "New Web Service"
4. Connect your repository
5. Use these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python ikea_events_monitor_cloud.py`

### Step 2: Configure Environment Variables

In Render dashboard → Environment tab, add the same variables as Railway.

### Step 3: Set Up Cron Job

1. In Render dashboard, go to "Cron Jobs"
2. Create new cron job:
   - **Command**: `python ikea_events_monitor_cloud.py --once`
   - **Schedule**: `0 12,17 * * *`

---

## 🎯 Alternative: External Cron Service

If you prefer to keep your script simple and use an external service:

### Step 1: Deploy Anywhere

Deploy your script to any hosting provider (even GitHub Pages with a simple webhook).

### Step 2: Use EasyCron

1. Go to [EasyCron.com](https://easycron.com)
2. Create account (free tier available)
3. Add new cron job:
   - **URL**: `https://your-app-url.com/check-events`
   - **Schedule**: `0 12,17 * * *`
   - **Method**: GET

### Step 3: Add Web Endpoint

Add this to your script to make it web-accessible:

```python
from flask import Flask
app = Flask(__name__)

@app.route('/check-events')
def check_events():
    monitor = IKEAEventsMonitorCloud()
    monitor.check_for_updates()
    return "Check completed", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
```

---

## 🔧 Configuration Options

### Environment Variables

- `SENDER_EMAIL`: Your Gmail address
- `SENDER_PASSWORD`: Gmail app password (not your regular password)
- `RECIPIENT_EMAILS`: Comma-separated list of email addresses (e.g., `email1@gmail.com,email2@gmail.com`)
- `RECIPIENT_EMAIL`: Single email address (legacy support)
- `SMTP_SERVER`: Usually `smtp.gmail.com`
- `SMTP_PORT`: Usually `587`
- `WEBHOOK_URL`: Slack webhook URL (optional)
- `CHECK_INTERVAL_HOURS`: How often to check (default: 24)
- `TIMEOUT_SECONDS`: Request timeout (default: 30)

### Gmail App Password Setup

1. Enable 2-factor authentication on Gmail
2. Go to Google Account settings
3. Security → App passwords
4. Generate password for "Mail"
5. Use this password in `SENDER_PASSWORD`

---

## 📊 Monitoring & Logs

### Railway

- View logs in Railway dashboard
- Set up alerts for failures
- Monitor resource usage

### Render

- Check logs in Render dashboard
- Set up uptime monitoring
- Configure alerts

### External Services

- EasyCron provides execution logs
- Set up uptime monitoring with UptimeRobot
- Monitor your hosting provider's status

---

## 🛠️ Troubleshooting

### Common Issues

1. **Script not running**: Check environment variables are set correctly
2. **Email not sending**: Verify Gmail app password and 2FA
3. **No events found**: Check if IKEA changed their website structure
4. **Cron not triggering**: Verify schedule syntax and timezone

### Debug Commands

```bash
# Test script locally
python ikea_events_monitor_cloud.py --once

# Check configuration
python ikea_events_monitor_cloud.py --config

# Run with debug logging
python ikea_events_monitor_cloud.py --once
```

---

## 💰 Cost Comparison

| Platform | Free Tier       | Paid Plans | Reliability |
| -------- | --------------- | ---------- | ----------- |
| Railway  | 500 hours/month | $5/month   | ⭐⭐⭐⭐⭐  |
| Render   | 750 hours/month | $7/month   | ⭐⭐⭐⭐    |
| Heroku   | None            | $5-7/month | ⭐⭐⭐⭐⭐  |
| EasyCron | 20 jobs/month   | $2/month   | ⭐⭐⭐⭐    |

---

## 🎉 You're All Set!

Your IKEA monitor will now run reliably in the cloud. You'll receive email notifications whenever new events are posted at IKEA Etobicoke or North York.

**Pro Tips:**

- Test your deployment with `--once` flag first
- Monitor logs for the first few days
- Set up alerts for failures
- Keep your Gmail app password secure
