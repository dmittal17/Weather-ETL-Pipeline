"""EXTRACT: pull raw hourly weather JSON from the Open-Meteo API."""
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

log = logging.getLogger(__name__)


def build_session() -> requests.Session:
    """Session that automatically retries on timeouts / 429 / 5xx errors."""
    retry = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=config.BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_city(session: requests.Session, city: str, lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(config.HOURLY_VARIABLES),
        "past_days": config.PAST_DAYS,
        "forecast_days": 1,
        "timezone": "UTC",
    }
    response = session.get(config.API_URL, params=params, timeout=config.REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if "hourly" not in data or "time" not in data["hourly"]:
        raise ValueError(f"Unexpected API response for {city}: missing 'hourly' data")
    return data


def extract_all() -> dict:
    """Return {city: raw_json}. A failing city is logged and skipped."""
    session = build_session()
    results = {}
    for city, (lat, lon) in config.CITIES.items():
        try:
            results[city] = fetch_city(session, city, lat, lon)
            log.info("Extracted %s (%d hourly rows)", city, len(results[city]["hourly"]["time"]))
        except (requests.RequestException, ValueError) as exc:
            log.error("Extraction failed for %s: %s", city, exc)
    if not results:
        raise RuntimeError("Extraction failed for ALL cities - check internet connection / API status")
    return results
