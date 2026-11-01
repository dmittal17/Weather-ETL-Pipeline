"""ANALYZE: daily summary table + temperature trend chart."""
import logging
import sqlite3
from contextlib import closing

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

import config

log = logging.getLogger(__name__)


def analyze() -> pd.DataFrame:
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        df = pd.read_sql_query("SELECT * FROM weather_readings ORDER BY observed_at", conn)
    if df.empty:
        log.warning("No data in database - skipping analysis")
        return df

    # Stored in UTC -> show in local timezone
    df["observed_at"] = (
        pd.to_datetime(df["observed_at"], utc=True)
        .dt.tz_convert(config.DISPLAY_TIMEZONE)
        .dt.tz_localize(None)
    )
    df["date"] = df["observed_at"].dt.date

    daily = (
        df.groupby(["city", "date"])
        .agg(
            avg_temp_c=("temperature_c", "mean"),
            min_temp_c=("temperature_c", "min"),
            max_temp_c=("temperature_c", "max"),
            avg_humidity_pct=("humidity_pct", "mean"),
            total_rain_mm=("precipitation_mm", "sum"),
            avg_wind_kmh=("wind_speed_kmh", "mean"),
            rainy_hours=("is_rainy", "sum"),
        )
        .round(2)
        .reset_index()
    )
    daily.to_csv(config.DAILY_CSV_PATH, index=False)
    log.info("Saved daily summary to %s", config.DAILY_CSV_PATH)

    # ---- Chart ----
    fig, ax = plt.subplots(figsize=(12, 6))
    for city, group in df.groupby("city"):
        ax.plot(group["observed_at"], group["temperature_c"], label=city, linewidth=1.5)
    ax.set_title(f"Hourly Temperature Trend ({config.DISPLAY_TIMEZONE} time)")
    ax.set_xlabel("Date / time")
    ax.set_ylabel("Temperature (°C)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(config.CHART_PATH, dpi=150)
    plt.close(fig)
    log.info("Saved chart to %s", config.CHART_PATH)

    # ---- Console summary of the latest day ----
    latest = daily[daily["date"] == daily["date"].max()]
    print("\n=== Latest daily summary ===")
    print(latest.to_string(index=False))
    return daily
