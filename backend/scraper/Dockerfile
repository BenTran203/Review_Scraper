FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser binary
RUN playwright install chromium

# Install system dependencies for Chromium on Bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       # X11 / display libs
       libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxkbcommon0 \
       libgbm1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
       libpango-1.0-0 libcairo2 libnss3 libnspr4 libdbus-1-3 \
       libdrm2 libxshmfence1 libglib2.0-0 \
       # Fonts (required to render pages correctly)
       fonts-liberation fonts-noto-color-emoji fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "-m", "src.worker"]
