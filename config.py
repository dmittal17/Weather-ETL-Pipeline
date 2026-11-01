"""Central configuration for the weather ETL pipeline."""
from pathlib import Path

# ---------- Paths ----------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"

DB_PATH = DATA_DIR / "weather.db"
LOG_PATH = LOG_DIR / "pipeline.log"
CSV_EXPORT_PATH = OUTPUT_DIR / "weather_readings.csv"
DAILY_CSV_PATH = OUTPUT_DIR / "daily_summary.csv"
CHART_PATH = OUTPUT_DIR / "temperature_trend.png"

for _folder in (DATA_DIR, LOG_DIR, OUTPUT_DIR):
    _folder.mkdir(exist_ok=True)

# ---------- API (Open-Meteo: free, no API key needed) ----------
API_URL = "https://api.open-meteo.com/v1/forecast"

# city -> (latitude, longitude). Add or remove cities freely.
CITIES = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
}

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "wind_speed_10m",
    "weather_code",
]

PAST_DAYS = 7  # how many days of history to pull (gives the chart data on the first run)

# ---------- Reliability ----------
REQUEST_TIMEOUT = 15      # seconds
MAX_RETRIES = 3           # retries per failed API call
BACKOFF_FACTOR = 1.5      # wait 0s, 1.5s, 3s ... between retries

# ---------- Scheduling ----------
SCHEDULE_EVERY_MINUTES = 60

# ---------- Display ----------
DISPLAY_TIMEZONE = "Asia/Kolkata"  # data is stored in UTC; charts are shown in this zone
