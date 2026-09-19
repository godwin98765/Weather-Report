# Weather-Report 🌦️

Automated Weather Report Agent that fetches live weather forecasts and alerts, formats a comprehensive daily report, and sends it via email.

## Features
- **Accurate Forecasts**: Fetches weather metrics (temperature, precipitation, wind, visibility, snowfall) using the Open-Meteo API.
- **Automated Alerts**: Scheduled via GitHub Actions to deliver reports every morning at **8:00 AM IST** (`02:30 UTC`).
- **Responsive Email**: Beautifully styled HTML and plain-text email with clothing and travel recommendations.

## Setup & Running Locally

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables (Optional)**:
   You can set the following environment variables or use the defaults in `agent.py`:
   - `SENDER_EMAIL`: Gmail address used to send the alerts.
   - `SENDER_PASSWORD`: Gmail App Password (16 characters).
   - `RECIPIENT_EMAIL`: Email address to receive the alert.

3. **Run the script**:
   ```bash
   python agent.py
   ```

## GitHub Actions Schedule
The automated workflow is configured in [`.github/workflows/daily_weather_alert.yml`](.github/workflows/daily_weather_alert.yml):
- **Schedule**: Everyday at `08:00 AM IST` (`cron: '30 2 * * *'`)
- **Manual Trigger**: Can also be run manually from the **Actions** tab.
