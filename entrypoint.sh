#!/bin/bash

set -e

# Create cron job for scraper
echo "Setting up scraper cron job..."
echo '0 8 * * * cd /app && python3 casino_scraper.py >> /app/logs/scraper_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1' > /etc/cron.d/scraper

# Create cron job for cleanup (runs daily at 2 AM)
echo "Setting up cleanup cron job..."
echo '0 2 * * * /app/cleanup.sh >> /app/logs/cleanup_$(date +\%Y\%m\%d).log 2>&1' >> /etc/cron.d/scraper

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