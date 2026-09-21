import os
import sys
import requests
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import math

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==================================================
# CONFIGURATION
# ==================================================

API_URL = (
    "https://api.open-meteo.com/v1/forecast?"
    "latitude=78.2232&longitude=15.6469"
    "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m"
    "&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,snowfall,weather_code,visibility,wind_speed_10m,wind_direction_10m"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset,wind_speed_10m_max"
    "&timezone=Europe/Oslo&forecast_days=2"
)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

_sender_env = os.environ.get("SENDER_EMAIL", "").strip()
_password_env = os.environ.get("SENDER_PASSWORD", "").strip()
_recipient_env = os.environ.get("RECIPIENT_EMAIL", "").strip()

SENDER_EMAIL = _sender_env if _sender_env else "godwin7776@gmail.com"
SENDER_PASSWORD = _password_env if _password_env else "pzzu bcwu vnou dfrv"
RECIPIENT_EMAIL = _recipient_env if _recipient_env else "wistlygod@gmail.com"

LOCATION_NAME = "Longyearbyen, Svalbard, Norway"
TIMEZONE = "Europe/Oslo"

STRONG_WIND_THRESHOLD_KMH = 40
POOR_VISIBILITY_THRESHOLD_KM = 1.0

WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def safe_value(value, formatter=None, suffix=""):
    """Return 'Not available' if value is missing/None, otherwise format it."""
    if value is None:
        return "Not available"
    try:
        if formatter is not None:
            return f"{formatter(value)}{suffix}"
        return f"{value}{suffix}"
    except (TypeError, ValueError):
        return "Not available"


def weather_code_to_description(code):
    if code is None:
        return "Not available"
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "Not available"
    return WEATHER_CODE_MAP.get(code, "Not available")


def degrees_to_direction(degrees):
    if degrees is None:
        return None
    try:
        degrees = float(degrees) % 360
    except (TypeError, ValueError):
        return None

    directions = [
        (22.5, "N"), (67.5, "NE"), (112.5, "E"), (157.5, "SE"),
        (202.5, "S"), (247.5, "SW"), (292.5, "W"), (337.5, "NW"),
        (360.01, "N"),
    ]
    for boundary, name in directions:
        if degrees < boundary:
            return name
    return "N"


def format_wind_direction(degrees):
    direction = degrees_to_direction(degrees)
    if direction is None or degrees is None:
        return "Not available"
    try:
        return f"{direction} ({int(round(float(degrees)))}°)"
    except (TypeError, ValueError):
        return "Not available"


def format_time(iso_time_str):
    if not iso_time_str:
        return "Not available"
    try:
        dt = datetime.fromisoformat(iso_time_str)
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return "Not available"


def format_date(iso_time_str):
    if not iso_time_str:
        return "Not available"
    try:
        dt = datetime.fromisoformat(iso_time_str)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "Not available"


def parse_hourly_time(time_str):
    try:
        return datetime.fromisoformat(time_str)
    except (ValueError, TypeError):
        return None


# ==================================================
# GET WEATHER DATA
# ==================================================

def get_weather_data():
    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.Timeout:
        print("Error: The request to Open-Meteo timed out.")
        return None
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Open-Meteo API.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP error from Open-Meteo API: {e}")
        return None
    except ValueError:
        print("Error: Failed to parse JSON response from Open-Meteo API.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: Unexpected error while requesting weather data: {e}")
        return None


# ==================================================
# NEXT 24-HOUR ANALYSIS
# ==================================================

def calculate_next_24_hours(hourly_data):
    result = {
        "min_temp": None,
        "max_temp": None,
        "start_temp": None,
        "end_temp": None,
        "trend_text": None,
        "has_precipitation": False,
        "total_precipitation": None,
        "max_precip_probability": None,
        "has_snowfall": False,
        "total_snowfall": None,
        "max_wind": None,
        "min_visibility_km": None,
        "condition_change_text": None,
        "bullets": [],
    }

    if not hourly_data:
        return result

    times = hourly_data.get("time") or []
    if not times:
        return result

    try:
        now = datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)
    except Exception:
        now = datetime.now()

    # Find the index of the first hourly timestamp >= now
    start_index = 0
    found = False
    for i, t in enumerate(times):
        dt = parse_hourly_time(t)
        if dt is not None and dt >= now:
            start_index = i
            found = True
            break
    if not found:
        start_index = 0

    end_index = min(start_index + 24, len(times))

    def slice_field(field_name):
        values = hourly_data.get(field_name)
        if not values:
            return []
        return values[start_index:end_index]

    temps = [v for v in slice_field("temperature_2m") if v is not None]
    precip = [v for v in slice_field("precipitation") if v is not None]
    precip_prob = [v for v in slice_field("precipitation_probability") if v is not None]
    snowfall = [v for v in slice_field("snowfall") if v is not None]
    wind_speed = [v for v in slice_field("wind_speed_10m") if v is not None]
    visibility = [v for v in slice_field("visibility") if v is not None]
    weather_codes = [v for v in slice_field("weather_code") if v is not None]

    # Temperature analysis
    if temps:
        result["min_temp"] = min(temps)
        result["max_temp"] = max(temps)
        result["start_temp"] = temps[0]
        result["end_temp"] = temps[-1]

        diff = result["end_temp"] - result["start_temp"]
        if diff >= 1.5:
            result["trend_text"] = (
                f"The temperature is expected to rise from approximately "
                f"{result['start_temp']:.1f} °C to {result['end_temp']:.1f} °C."
            )
        elif diff <= -1.5:
            result["trend_text"] = (
                f"The temperature is expected to fall from approximately "
                f"{result['start_temp']:.1f} °C to {result['end_temp']:.1f} °C."
            )
        else:
            result["trend_text"] = "The temperature is expected to remain relatively stable."

    # Precipitation analysis
    if precip:
        total_precip = sum(precip)
        result["total_precipitation"] = total_precip
        if total_precip > 0:
            result["has_precipitation"] = True

    if precip_prob:
        result["max_precip_probability"] = max(precip_prob)

    # Snowfall analysis
    if snowfall:
        total_snow = sum(snowfall)
        result["total_snowfall"] = total_snow
        if total_snow > 0:
            result["has_snowfall"] = True

    # Wind analysis
    if wind_speed:
        result["max_wind"] = max(wind_speed)

    # Visibility analysis
    if visibility:
        min_vis_m = min(visibility)
        result["min_visibility_km"] = min_vis_m / 1000

    # Weather condition changes
    if weather_codes:
        distinct_codes = []
        for code in weather_codes:
            if not distinct_codes or distinct_codes[-1] != code:
                distinct_codes.append(code)
        if len(distinct_codes) > 1:
            first_desc = weather_code_to_description(distinct_codes[0])
            last_desc = weather_code_to_description(distinct_codes[-1])
            if first_desc != "Not available" and last_desc != "Not available" and first_desc != last_desc:
                result["condition_change_text"] = (
                    f"Conditions are forecast to change from {first_desc.lower()} to {last_desc.lower()}."
                )

    # Build bullet points
    bullets = []

    if result["trend_text"]:
        bullets.append(result["trend_text"])

    if result["has_precipitation"]:
        if result["max_precip_probability"] is not None:
            bullets.append(
                f"Precipitation is possible during the forecast period, with the highest "
                f"hourly probability reaching {int(round(result['max_precip_probability']))}%."
            )
        else:
            bullets.append("Precipitation is possible during the forecast period.")
    elif result["max_precip_probability"] is not None and result["max_precip_probability"] >= 50:
        bullets.append(
            f"Precipitation probability reaches up to {int(round(result['max_precip_probability']))}% "
            f"during the forecast period."
        )

    if result["has_snowfall"]:
        bullets.append(
            f"Snowfall is forecast during the next 24 hours, with approximately "
            f"{result['total_snowfall']:.1f} cm accumulated across the available hourly forecast."
        )

    if result["max_wind"] is not None and result["max_wind"] >= STRONG_WIND_THRESHOLD_KMH:
        bullets.append(
            f"Strong winds are possible, with maximum forecast wind speeds reaching "
            f"approximately {result['max_wind']:.1f} km/h."
        )

    if result["min_visibility_km"] is not None and result["min_visibility_km"] < POOR_VISIBILITY_THRESHOLD_KM:
        bullets.append(
            f"Visibility may become poor, reaching approximately {result['min_visibility_km']:.2f} km."
        )

    if result["condition_change_text"]:
        bullets.append(result["condition_change_text"])

    if not bullets:
        bullets.append(
            "The weather remains relatively stable over the next 24 hours based on the available forecast."
        )

    result["bullets"] = bullets[:6]

    return result


# ==================================================
# CLOTHING / TRAVEL TIP & WEATHER NOTE
# ==================================================

def generate_clothing_tip(current_temp, analysis):
    if current_temp is not None and current_temp <= -10:
        return "Warm, insulated clothing is recommended due to the low temperatures."
    if analysis.get("has_snowfall"):
        return "Winter footwear and warm outerwear are recommended due to forecast snowfall."
    if analysis.get("has_precipitation"):
        return "Water-resistant outerwear is recommended due to the forecast precipitation."
    if analysis.get("max_wind") is not None and analysis["max_wind"] >= STRONG_WIND_THRESHOLD_KMH:
        return "Wind-resistant outerwear is recommended due to the forecast wind."
    if current_temp is not None and not analysis.get("has_precipitation") and not analysis.get("has_snowfall"):
        return "Normal outdoor clothing should be suitable based on the available forecast."
    return "Check the latest local conditions before travelling."


def generate_weather_note(analysis):
    notes = []

    if analysis.get("has_snowfall"):
        notes.append("snowfall")
    if analysis.get("has_precipitation"):
        notes.append("precipitation")
    if analysis.get("max_wind") is not None and analysis["max_wind"] >= STRONG_WIND_THRESHOLD_KMH:
        notes.append("strong wind")
    if analysis.get("min_visibility_km") is not None and analysis["min_visibility_km"] < POOR_VISIBILITY_THRESHOLD_KM:
        notes.append("poor visibility")
    if analysis.get("condition_change_text"):
        notes.append("rapid weather changes")

    if not notes:
        return "No significant weather concerns from the available forecast."

    return "Notable conditions in the forecast period: " + ", ".join(notes) + "."


# ==================================================
# EMAIL GENERATION
# ==================================================

def generate_plain_text_email(context):
    lines = []
    lines.append("Good Morning,")
    lines.append("")
    lines.append(f"Here is today's weather update for {LOCATION_NAME}.")
    lines.append("")
    lines.append("LOCATION")
    lines.append(LOCATION_NAME)
    lines.append("")
    lines.append("CURRENT WEATHER")
    lines.append(f"Temperature: {context['current_temp_str']}")
    lines.append(f"Feels Like: {context['feels_like_str']}")
    lines.append(f"Condition: {context['current_condition']}")
    lines.append(f"Humidity: {context['humidity_str']}")
    lines.append(f"Precipitation: {context['current_precip_str']}")
    lines.append("")
    lines.append("TODAY'S FORECAST")
    lines.append(f"High: {context['temp_max_str']}")
    lines.append(f"Low: {context['temp_min_str']}")
    lines.append(f"Precipitation Chance: {context['precip_prob_max_str']}")
    lines.append(f"Snowfall: {context['snowfall_24h_str']}")
    lines.append(f"Maximum Wind: {context['wind_max_str']}")
    lines.append("")
    lines.append("WIND")
    lines.append(f"Speed: {context['current_wind_speed_str']}")
    lines.append(f"Direction: {context['current_wind_dir_str']}")
    lines.append("")
    lines.append("VISIBILITY")
    lines.append(context["visibility_str"])
    lines.append("")
    lines.append("SUN")
    lines.append(f"Sunrise: {context['sunrise_str']}")
    lines.append(f"Sunset: {context['sunset_str']}")
    lines.append("")
    lines.append("NEXT 24 HOURS")
    for bullet in context["bullets"]:
        lines.append(f"- {bullet}")
    lines.append("")
    lines.append("CLOTHING / TRAVEL TIP")
    lines.append(context["clothing_tip"])
    lines.append("")
    lines.append("WEATHER NOTE")
    lines.append(context["weather_note"])
    lines.append("")
    lines.append("Have a great day! 🌟")

    return "\n".join(lines)


def generate_html_email(context):
    bullets_html = "".join(f"<li>{b}</li>" for b in context["bullets"])

    html = f"""\
<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f0f6fb;font-family:Arial, Helvetica, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f6fb;padding:20px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

          <tr>
            <td style="background-color:#1f6f9e;padding:24px 30px;">
              <h1 style="color:#ffffff;font-size:20px;margin:0;">🌦️ Daily Weather Update</h1>
              <p style="color:#dceefc;font-size:13px;margin:6px 0 0 0;">{LOCATION_NAME} — {context['date_str']}</p>
            </td>
          </tr>

          <tr>
            <td style="padding:24px 30px 8px 30px;">
              <p style="font-size:14px;color:#333333;margin:0 0 16px 0;">Good Morning,<br>Here is today's weather update for {LOCATION_NAME}.</p>
            </td>
          </tr>

          <tr>
            <td style="padding:0 30px;">
              <div style="background-color:#eef7fc;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
                <h2 style="font-size:14px;color:#1f6f9e;margin:0 0 10px 0;">🌡️ CURRENT WEATHER</h2>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Temperature: <strong>{context['current_temp_str']}</strong></p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Feels Like: {context['feels_like_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Condition: {context['current_condition']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Humidity: {context['humidity_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Precipitation: {context['current_precip_str']}</p>
              </div>

              <div style="background-color:#eef7fc;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
                <h2 style="font-size:14px;color:#1f6f9e;margin:0 0 10px 0;">🌤️ TODAY'S FORECAST</h2>
                <p style="font-size:13px;color:#333333;margin:4px 0;">High: {context['temp_max_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Low: {context['temp_min_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Precipitation Chance: {context['precip_prob_max_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Snowfall: {context['snowfall_24h_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Maximum Wind: {context['wind_max_str']}</p>
              </div>

              <div style="background-color:#eef7fc;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
                <h2 style="font-size:14px;color:#1f6f9e;margin:0 0 10px 0;">💨 WIND &amp; 👁️ VISIBILITY</h2>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Speed: {context['current_wind_speed_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Direction: {context['current_wind_dir_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Visibility: {context['visibility_str']}</p>
              </div>

              <div style="background-color:#eef7fc;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
                <h2 style="font-size:14px;color:#1f6f9e;margin:0 0 10px 0;">🌅 SUN</h2>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Sunrise: {context['sunrise_str']}</p>
                <p style="font-size:13px;color:#333333;margin:4px 0;">Sunset: {context['sunset_str']}</p>
              </div>

              <div style="background-color:#eef7fc;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
                <h2 style="font-size:14px;color:#1f6f9e;margin:0 0 10px 0;">🔮 NEXT 24 HOURS</h2>
                <ul style="font-size:13px;color:#333333;margin:4px 0;padding-left:18px;">
                  {bullets_html}
                </ul>
              </div>

              <div style="background-color:#eef7fc;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
                <h2 style="font-size:14px;color:#1f6f9e;margin:0 0 10px 0;">🧣 CLOTHING / TRAVEL TIP</h2>
                <p style="font-size:13px;color:#333333;margin:0;">{context['clothing_tip']}</p>
              </div>

              <div style="background-color:#eef7fc;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
                <h2 style="font-size:14px;color:#1f6f9e;margin:0 0 10px 0;">📌 WEATHER NOTE</h2>
                <p style="font-size:13px;color:#333333;margin:0;">{context['weather_note']}</p>
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:16px 30px 26px 30px;">
              <p style="font-size:13px;color:#333333;margin:0;">Have a great day! 🌟</p>
            </td>
          </tr>

          <tr>
            <td style="background-color:#f0f6fb;padding:14px 30px;">
              <p style="font-size:11px;color:#888888;margin:0;">Data source: Open-Meteo — {LOCATION_NAME}</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html


# ==================================================
# SEND EMAIL
# ==================================================

def send_email(subject, plain_text_body, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    part1 = MIMEText(plain_text_body, "plain", "utf-8")
    part2 = MIMEText(html_body, "html", "utf-8")

    msg.attach(part1)
    msg.attach(part2)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(
                SENDER_EMAIL,
                RECIPIENT_EMAIL,
                msg.as_string()
            )
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"Error: SMTP authentication failed. Check your email and app password. Details: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"Error: Could not connect to the SMTP server. Details: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"Error: An SMTP error occurred: {e}")
        return False
    except Exception as e:
        print(f"Error: Unexpected error while sending email: {e}")
        return False


# ==================================================
# MAIN
# ==================================================

def main():
    data = get_weather_data()
    if data is None:
        print("Weather data could not be retrieved. Email will not be sent.")
        sys.exit(1)

    current = data.get("current") or {}
    daily = data.get("daily") or {}
    hourly = data.get("hourly") or {}

    # --- Current weather ---
    current_temp = current.get("temperature_2m")
    feels_like = current.get("apparent_temperature")
    current_humidity = current.get("relative_humidity_2m")
    current_precip = current.get("precipitation")
    current_weather_code = current.get("weather_code")
    current_wind_speed = current.get("wind_speed_10m")
    current_wind_dir = current.get("wind_direction_10m")

    current_condition = weather_code_to_description(current_weather_code)

    current_temp_str = safe_value(current_temp, lambda v: f"{v:.1f}", " °C")
    feels_like_str = safe_value(feels_like, lambda v: f"{v:.1f}", " °C")
    humidity_str = safe_value(current_humidity, lambda v: f"{int(round(v))}", "%")
    current_precip_str = safe_value(current_precip, lambda v: f"{v:.2f}", " mm")
    current_wind_speed_str = safe_value(current_wind_speed, lambda v: f"{v:.1f}", " km/h")
    current_wind_dir_str = format_wind_direction(current_wind_dir)

    # --- Daily forecast (first entry = today) ---
    def first_daily(field):
        values = daily.get(field)
        if values and len(values) > 0:
            return values[0]
        return None

    temp_max = first_daily("temperature_2m_max")
    temp_min = first_daily("temperature_2m_min")
    precip_prob_max = first_daily("precipitation_probability_max")
    wind_max = first_daily("wind_speed_10m_max")
    sunrise_raw = first_daily("sunrise")
    sunset_raw = first_daily("sunset")
    daily_time_raw = first_daily("time")

    temp_max_str = safe_value(temp_max, lambda v: f"{v:.1f}", " °C")
    temp_min_str = safe_value(temp_min, lambda v: f"{v:.1f}", " °C")
    precip_prob_max_str = safe_value(precip_prob_max, lambda v: f"{int(round(v))}", "%")
    wind_max_str = safe_value(wind_max, lambda v: f"{v:.1f}", " km/h")
    sunrise_str = format_time(sunrise_raw)
    sunset_str = format_time(sunset_raw)

    if daily_time_raw:
        date_str = daily_time_raw
    else:
        try:
            date_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
        except Exception:
            date_str = datetime.now().strftime("%Y-%m-%d")

    # --- Visibility (use current hour's hourly visibility if available) ---
    visibility_km = None
    hourly_times = hourly.get("time") or []
    hourly_visibility = hourly.get("visibility") or []
    try:
        now = datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)
    except Exception:
        now = datetime.now()

    for i, t in enumerate(hourly_times):
        dt = parse_hourly_time(t)
        if dt is not None and dt >= now:
            if i < len(hourly_visibility) and hourly_visibility[i] is not None:
                visibility_km = hourly_visibility[i] / 1000
            break

    visibility_str = safe_value(visibility_km, lambda v: f"{v:.2f}", " km")

    # --- Snowfall next 24h and hourly analysis ---
    analysis = calculate_next_24_hours(hourly)

    if analysis.get("total_snowfall") is not None:
        snowfall_24h_str = f"{analysis['total_snowfall']:.1f} cm"
    else:
        hourly_snowfall = hourly.get("snowfall")
        if hourly_snowfall is not None:
            snowfall_24h_str = "0 cm"
        else:
            snowfall_24h_str = "Not available"

    clothing_tip = generate_clothing_tip(current_temp, analysis)
    weather_note = generate_weather_note(analysis)

    context = {
        "date_str": date_str,
        "current_temp_str": current_temp_str,
        "feels_like_str": feels_like_str,
        "current_condition": current_condition,
        "humidity_str": humidity_str,
        "current_precip_str": current_precip_str,
        "temp_max_str": temp_max_str,
        "temp_min_str": temp_min_str,
        "precip_prob_max_str": precip_prob_max_str,
        "snowfall_24h_str": snowfall_24h_str,
        "wind_max_str": wind_max_str,
        "current_wind_speed_str": current_wind_speed_str,
        "current_wind_dir_str": current_wind_dir_str,
        "visibility_str": visibility_str,
        "sunrise_str": sunrise_str,
        "sunset_str": sunset_str,
        "bullets": analysis["bullets"],
        "clothing_tip": clothing_tip,
        "weather_note": weather_note,
    }

    subject = f"🌦️ Daily Weather Update – Longyearbyen, Svalbard – {date_str}"

    plain_text_body = generate_plain_text_email(context)
    html_body = generate_html_email(context)

    success = send_email(subject, plain_text_body, html_body)

    if success:
        print(f"Weather email sent successfully to {RECIPIENT_EMAIL}")
        print(f"Location: {LOCATION_NAME}")
        print(f"Date: {date_str}")
        print(f"Current temperature: {current_temp_str}")
        print(f"Condition: {current_condition}")
        print(f"Email recipient: {RECIPIENT_EMAIL}")
    else:
        print("Email sending failed. See error message above.")
        sys.exit(1)


if __name__ == "__main__":
    main()