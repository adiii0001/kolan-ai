# Kolan AI Shop Assistant

AI-powered shopping chatbot for [Kolan](https://kolan.co.in) — a pet store.

## Tech Stack

- **Backend:** FastAPI (Python 3.12)
- **Database:** SQLite
- **AI Models:** Groq (LLaMA 3.3 70B) for speed, Claude Sonnet 4 for complex reasoning
- **Frontend:** Vanilla JavaScript widget
- **Deployment:** Vercel (serverless)

## Architecture

```
Shopify Webhooks → /webhook/update → SQLite
Customer Chat   → POST /chat       → AI Router → Tool Calls → SQLite → Response
```

The catalog is synced from Shopify via webhooks into local SQLite. The AI never queries Shopify during conversations. All factual data comes from SQLite via tool calls.

## Directory Structure

```
kolan-ai/
├── api/index.py           # Vercel entry point
├── app/
│   ├── main.py            # FastAPI app
│   ├── core/
│   │   ├── config.py      # Environment settings
│   │   ├── database.py    # SQLite connection & init
│   │   └── security.py    # CORS configuration
│   ├── routes/
│   │   ├── chat.py        # POST /chat
│   │   ├── webhook.py     # POST /webhook/update
│   │   └── health.py      # GET /health
│   ├── services/
│   │   ├── ai_router.py   # Routes to Groq or Claude
│   │   ├── groq_service.py
│   │   ├── claude_service.py
│   │   └── shopify_sync.py
│   ├── tools/
│   │   ├── search_catalog.py
│   │   └── get_policy.py
│   └── models/
│       ├── product.py
│       └── policy.py
├── static/
│   ├── widget.js
│   └── widget.css
├── data/
│   └── kolan.db
├── requirements.txt
├── vercel.json
├── .env.example
└── README.md
```

## Installation

```bash
git clone <repo>
cd kolan-ai
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Environment Setup

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Required variables:

| Variable                | Description                          |
| ----------------------- | ------------------------------------ |
| `GROQ_API_KEY`          | Groq API key for fast inference      |
| `CLAUDE_API_KEY`        | Anthropic API key for complex chats  |
| `SHOPIFY_WEBHOOK_SECRET`| Shopify webhook verification secret  |
| `DATABASE_URL`          | Path to SQLite file                  |
| `ALLOWED_ORIGINS`       | Comma-separated allowed origins      |

## Local Development

```bash
uvicorn app.main:app --reload --port 8000
```

Server runs at `http://localhost:8000`.

## Deploying to Vercel

1. Push the repository to GitHub.
2. Import the project in [Vercel](https://vercel.com).
3. Set the **Root Directory** to `kolan-ai`.
4. Add all environment variables in the Vercel dashboard.
5. Deploy.

The app will be available at `https://ai.kolan.co.in`.

## Adding Shopify Webhooks

In your Shopify admin, go to **Settings → Notifications → Webhooks** and add:

| Event               | URL                                  | Format |
| ------------------- | ------------------------------------ | ------ |
| Product creation    | `https://ai.kolan.co.in/webhook/update` | JSON   |
| Product update      | `https://ai.kolan.co.in/webhook/update` | JSON   |
| Product deletion    | `https://ai.kolan.co.in/webhook/update` | JSON   |

Set the **Webhook secret** in `.env` to match the one in Shopify for HMAC verification.

## Integrating the Widget

In your Shopify theme, add this before `</body>`:

```html
<script src="https://ai.kolan.co.in/static/widget.js" defer></script>
```

The widget will auto-inject a floating chat button.

## API Endpoints

### GET /health

Check server status.

### POST /chat

Send a chat message.

**Request:**
```json
{
  "message": "What is the price of Pet Wipes?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "answer": "Pet Wipes are ₹249.00 and currently in stock!",
  "products": [
    {
      "title": "Pet Wipes",
      "price": 249.0,
      "image_url": "https://...",
      "handle": "pet-wipes",
      "available": true
    }
  ]
}
```

### POST /webhook/update

Receives Shopify product webhooks. Requires HMAC signature verification.

## Testing Endpoints

```bash
# Health check
curl https://ai.kolan.co.in/health

# Chat
curl -X POST https://ai.kolan.co.in/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Do you have dog shampoo?"}'
```

## Security

- CORS is restricted to `https://kolan.co.in` and `https://www.kolan.co.in`
- Shopify webhooks are verified via HMAC-SHA256
- No API keys are exposed to the frontend
- SQLite is the single source of truth — the AI never fabricates data
