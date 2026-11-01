"""
Weather ETL pipeline - entry point.

Usage:
    python pipeline.py              # run once
    python pipeline.py --schedule   # run now, then repeat every hour (Ctrl+C to stop)
"""
import argparse
import logging
import time

import schedule

import config
from analyze import analyze
from extract import extract_all
from load import export_csv, load
from logger_setup import setup_logging
from transform import transform

log = logging.getLogger("pipeline")


def run_once() -> None:
    log.info("=== Pipeline run started ===")
    try:
        raw = extract_all()            # E
        clean = transform(raw)         # T
        load(clean)                    # L
        export_csv()                   # CSV copy of the database
        analyze()                      # chart + daily summary
        log.info("=== Pipeline run finished successfully ===")
    except Exception:
        # Log full traceback but don't crash the scheduler
        log.exception("Pipeline run FAILED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Weather ETL pipeline")
    parser.add_argument("--schedule", action="store_true",
                        help=f"repeat every {config.SCHEDULE_EVERY_MINUTES} minutes")
    args = parser.parse_args()

    setup_logging()
    run_once()

    if args.schedule:
        schedule.every(config.SCHEDULE_EVERY_MINUTES).minutes.do(run_once)
        log.info("Scheduler started: running every %d minutes. Press Ctrl+C to stop.",
                 config.SCHEDULE_EVERY_MINUTES)
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Scheduler stopped by user")


if __name__ == "__main__":
    main()
