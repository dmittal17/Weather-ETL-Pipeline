"""TRANSFORM: clean, validate and enrich the raw API data."""
import logging

import pandas as pd

log = logging.getLogger(__name__)

# WMO weather interpretation codes used by Open-Meteo
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

RENAME = {
    "time": "observed_at",
    "temperature_2m": "temperature_c",
    "relative_humidity_2m": "humidity_pct",
    "apparent_temperature": "feels_like_c",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
}

NUMERIC_COLS = [
    "temperature_c", "humidity_pct", "feels_like_c",
    "precipitation_mm", "wind_speed_kmh", "weather_code",
]

FINAL_COLUMNS = [
    "city", "observed_at", "temperature_c", "temperature_f", "feels_like_c",
    "humidity_pct", "precipitation_mm", "wind_speed_kmh", "wind_speed_ms",
    "weather_code", "weather_description", "feels_like_category",
    "is_rainy", "ingested_at",
]


def _describe(code) -> str:
    return WMO_CODES.get(int(code), "Unknown") if pd.notna(code) else "Unknown"


def transform_city(city: str, payload: dict, now_utc: pd.Timestamp) -> pd.DataFrame:
    df = pd.DataFrame(payload["hourly"]).rename(columns=RENAME)
    df["city"] = city

    # --- Types ---
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True, errors="coerce")
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Keep only hours that have already happened (API also returns the rest of today) ---
    df = df[df["observed_at"].notna() & (df["observed_at"] <= now_utc)]

    # --- Remove duplicates & rows missing essential values ---
    start_rows = len(df)
    df = df.drop_duplicates(subset=["observed_at"])
    df = df.dropna(subset=["temperature_c", "feels_like_c"])

    # --- Validation: drop physically impossible values ---
    valid = (
        df["temperature_c"].between(-60, 60)
        & (df["humidity_pct"].isna() | df["humidity_pct"].between(0, 100))
        & (df["wind_speed_kmh"].isna() | (df["wind_speed_kmh"] >= 0))
        & (df["precipitation_mm"].isna() | (df["precipitation_mm"] >= 0))
    )
    df = df[valid].copy()
    dropped = start_rows - len(df)
    if dropped:
        log.warning("%s: dropped %d invalid/incomplete rows", city, dropped)

    if df.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)

    # --- Handle nulls ---
    df["precipitation_mm"] = df["precipitation_mm"].fillna(0.0)
    df["weather_code"] = df["weather_code"].astype("Int64")

    # --- Unit conversions ---
    df["temperature_f"] = (df["temperature_c"] * 9 / 5 + 32).round(2)
    df["wind_speed_ms"] = (df["wind_speed_kmh"] / 3.6).round(2)

    # --- Derived fields ---
    df["weather_description"] = df["weather_code"].map(_describe)
    df["is_rainy"] = (df["precipitation_mm"] > 0).astype(int)
    df["feels_like_category"] = pd.cut(
        df["feels_like_c"],
        bins=[-float("inf"), 10, 18, 26, 32, 38, float("inf")],
        labels=["Cold", "Cool", "Comfortable", "Warm", "Hot", "Extreme heat"],
    ).astype(str)

    # --- Metadata + final formatting ---
    df["ingested_at"] = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    df["observed_at"] = df["observed_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[FINAL_COLUMNS]


def transform(raw: dict) -> pd.DataFrame:
    now_utc = pd.Timestamp.now(tz="UTC")
    frames = [transform_city(city, payload, now_utc) for city, payload in raw.items()]
    frames = [f for f in frames if not f.empty]
    if not frames:
        raise RuntimeError("Transformation produced no valid rows")
    combined = pd.concat(frames, ignore_index=True)
    log.info("Transformed %d clean rows across %d cities", len(combined), len(frames))
    return combined
