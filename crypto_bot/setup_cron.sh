#!/bin/bash
# Alternative: set up a system cron job instead of running scheduler.py as a daemon.
# Adds a cron entry to run the bot at 9 AM every day.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(which python3)
CRON_JOB="0 9 * * * cd $SCRIPT_DIR && ANTHROPIC_API_KEY=\$ANTHROPIC_API_KEY $PYTHON bot.py >> $SCRIPT_DIR/logs/cron.log 2>&1"

echo "Adding cron job: $CRON_JOB"

# Add to crontab if not already present
(crontab -l 2>/dev/null | grep -v "crypto_bot/bot.py"; echo "$CRON_JOB") | crontab -

echo "Done. Run 'crontab -l' to verify."
