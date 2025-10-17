#!/bin/bash
# run_scraper.sh

cd /app

# Log file with timestamp
LOG_FILE="/app/logs/scraper_$(date +%Y%m%d_%H%M%S).log"

echo "========================================" | tee -a "$LOG_FILE"
echo "Scraper started at: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Run the scraper
python casino_scraper.py 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

echo "========================================" | tee -a "$LOG_FILE"
echo "Scraper finished at: $(date)" | tee -a "$LOG_FILE"
echo "Exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Cleanup old logs (keep last 30 days)
find /app/logs -name "scraper_*.log" -type f -mtime +30 -delete

exit $EXIT_CODE