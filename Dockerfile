# Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application files
COPY casino_scraper.py .
COPY run_scraper.sh .

# Make scripts executable
RUN chmod +x run_scraper.sh

# Create directories for outputs and logs
RUN mkdir -p /app/output /app/logs /app/archive

# Set timezone (optional - adjust to your timezone)
ENV TZ=Asia/Manila
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Health check
HEALTHCHECK --interval=1h --timeout=10s --start-period=5s --retries=3 \
    CMD test -f /app/logs/scraper_$(date +%Y%m%d)*.log || exit 1

# Default command
CMD ["python", "casino_scraper.py"]