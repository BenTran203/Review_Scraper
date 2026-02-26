# ReviewPulse AI — Review Scraping & AI Analytics

Paste a product URL from Amazon, Shopee, eBay, Lazada, or Tiki and get an
AI-generated summary of customer reviews including pros, cons, and sentiment
analysis — in English, Vietnamese, Spanish, or Japanese.

## Architecture

| Layer | Tech |
|-------|------|
| Frontend | Next.js 15, React 19, Tailwind CSS v4, Recharts |
| API Gateway | Go (Gin), Redis, RabbitMQ |
| Scraper Workers | Python (Playwright, httpx, Beautiful Soup 4) |
| AI | OpenAI GPT-4o-mini (server-side only) |
| Queue | RabbitMQ / CloudAMQP |
| Cache / Sessions | Redis 7 |
| Hosting | Vercel (frontend), Railway (backend) |

## Quick Start (local development)

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Go 1.21+
- Python 3.11+
- An OpenAI API key

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start infrastructure

```bash
docker compose up -d redis rabbitmq
```

### 3. Start the Go gateway

```bash
cd backend/gateway
go mod tidy
go run ./cmd/server
```

### 4. Start the Python scraper

```bash
cd backend/scraper
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium
python -m src.worker
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

## Environment Variables

> **Security**: `OPENAI_API_KEY` must only be set on the Go gateway service
> (via Railway dashboard in production). It must **never** appear in
> frontend code, browser requests, or git history.

See [`.env.example`](.env.example) for the full list of variables.

## Deployment

- **Frontend** → Vercel (auto-deploys from `frontend/` directory)
- **Go Gateway** → Railway (Docker, set env vars via dashboard)
- **Python Scraper** → Railway (Docker, set env vars via dashboard)
- **Redis** → Railway managed Redis
- **RabbitMQ** → CloudAMQP free tier (Little Lemur)

## Legal

This tool respects `robots.txt`, rate-limits requests to target sites, and
strips all personally identifiable information from scraped data. Results are
for informational purposes only.
