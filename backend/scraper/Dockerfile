FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + ALL required system dependencies automatically
RUN playwright install --with-deps chromium

COPY . .

CMD ["python", "-m", "src.worker"]
