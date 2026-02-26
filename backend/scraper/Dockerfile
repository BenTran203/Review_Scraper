FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + ALL required system dependencies.
# playwright install --with-deps handles most libs, but we also install
# the three X11 libs that are missing on slim images for safety.
RUN playwright install --with-deps chromium \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       libxcomposite1 libxfixes3 libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "-m", "src.worker"]
