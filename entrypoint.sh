#!/bin/bash
# entrypoint.sh

set -e

# Create cron job
echo "Setting up cron job..."
echo '0 8 * * * cd /app && python casino_scraper.py >> /app/logs/scraper_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1' > /etc/cron.d/scraper

# Set permissions
chmod 0644 /etc/cron.d/scraper

# Apply cron job
crontab /etc/cron.d/scraper

# Start cron in foreground
echo "Starting cron..."
cron

# Keep container running
echo "Cron started. Container will keep running..."
tail -f /dev/null