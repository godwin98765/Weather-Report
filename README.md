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

## GitHub Actions Setup & Secrets

To ensure the automated alert runs securely on GitHub Actions:
1. Go to your repository on GitHub.
2. Navigate to **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret** and add:
   - `SENDER_EMAIL`: Your Gmail address (e.g., `godwin7776@gmail.com`)
   - `SENDER_PASSWORD`: Your 16-character Google App Password (e.g., `pzzu bcwu vnou dfrv`)
   - `RECIPIENT_EMAIL`: The recipient's email address (e.g., `wistlygod@gmail.com`)

### Triggers
The automated workflow is configured in [`.github/workflows/daily_weather_alert.yml`](.github/workflows/daily_weather_alert.yml):
- **Push**: Automatically runs immediately whenever code is pushed to `main`.
- **Schedule**: Runs everyday at `08:00 AM IST` (`cron: '30 2 * * *'`).
- **Manual Trigger**: Can also be triggered anytime manually from the **Actions** tab in GitHub.
