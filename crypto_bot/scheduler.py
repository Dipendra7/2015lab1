"""
Scheduler for Crypto Daily Suggestion Bot
Runs the bot every day at 9:00 AM local time.

Usage:
    python scheduler.py

Keep this process running (e.g. via nohup, screen, tmux, or a systemd service).
"""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from bot import run_daily_suggestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    scheduler = BlockingScheduler()

    scheduler.add_job(
        run_daily_suggestion,
        trigger=CronTrigger(hour=9, minute=0),
        id="crypto_daily_suggestion",
        name="Crypto Daily Suggestion Bot",
        misfire_grace_time=300,  # allow up to 5 min late if system was asleep
    )

    logger.info("Scheduler started. Bot will run every day at 09:00 AM.")
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
