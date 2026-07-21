# Monday.com BI Agent

An AI-powered conversational BI agent that connects to Monday.com boards, cleans messy real-world data, computes business metrics programmatically, and uses Gemini AI to generate natural language insights.

## Architecture

```
Founder → React Chat UI → POST /api/chat → Flask Backend
    → Intent Extraction (Gemini OR Keyword Fallback)
    → Monday.com GraphQL API (Dynamic discovery OR Local Excel Fallback)
    → Data Cleaning (Pandas)
    → Business Calculations (Pandas — never the LLM)
    → LLM Explanation (Gemini OR Python Fallback Formatter)
    → Response → React UI
```

### Key Design Principle
> **The LLM never computes business metrics.** All numbers are calculated deterministically using Pandas. The LLM only explains and narrates pre-computed results.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite, Vanilla CSS |
| Backend | Flask (Python) |
| Data Processing | Pandas, rapidfuzz |
| AI/LLM | Google Gemini 2.0 Flash |
| Data Source | Monday.com GraphQL API |
| Deployment | Render (backend), Vercel (frontend) |

## Project Structure

```
backend/
├── app.py                  # Flask app factory
├── requirements.txt
├── routes/
│   ├── chat.py             # POST /api/chat — main conversation endpoint
│   └── monday.py           # Board health, preview, summary endpoints
├── services/
│   ├── monday_client.py    # Monday.com API client (dynamic discovery, pagination)
│   ├── cleaner.py          # Data cleaning pipeline with quality reporting
│   ├── insights.py         # Business calculation engine (ALL metrics here)
│   └── llm.py              # Gemini integration (intent extraction + explanation)
├── prompts/
│   └── system_prompt.txt   # System prompt for Gemini
└── utils/
    ├── normalizer.py       # Company name & sector normalization
    └── parser.py           # Currency & percentage formatting

frontend/
├── src/
│   ├── App.jsx
│   ├── index.css           # Complete design system
│   ├── api/api.js          # Backend API client
│   ├── components/
│   │   ├── ChatWindow.jsx
│   │   ├── ChatInput.jsx
│   │   ├── MessageBubble.jsx
│   │   ├── MetricCard.jsx
│   │   ├── SuggestedQuestions.jsx
│   │   └── Dashboard.jsx
│   └── pages/
│       └── Home.jsx
├── index.html
├── vite.config.js
└── package.json
```

## Monday.com Board Schema

### Work Orders (176 rows, 38 columns)
Key columns: `Deal name masked`, `Customer Name Code`, `Serial #`, `Nature of Work`, `Execution Status`, `Sector`, `Amount in Rupees (Excl of GST) (Masked)`, dates, billing fields

### Deals (346 rows, 12 columns)
Key columns: `Deal Name`, `Client Code`, `Deal Status`, `Masked Deal value`, `Deal Stage`, `Sector/service`, `Closure Probability`, dates

## Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- Monday.com API token
- Google Gemini API key

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python app.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
```
MONDAY_API_TOKEN=        # Monday.com API token
GEMINI_API_KEY=          # Google AI Studio API key
WORK_ORDERS_BOARD_NAME=  # Default: "Work Orders"
DEALS_BOARD_NAME=        # Default: "Deals"
# Optional: hardcode board IDs as safety net
# WORK_ORDERS_BOARD_ID=
# DEALS_BOARD_ID=
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Backend health check |
| GET | `/api/monday/health` | Monday.com connectivity test |
| GET | `/api/monday/boards` | List accessible boards |
| GET | `/api/monday/preview/<board_key>` | Preview board schema + sample rows |
| GET | `/api/monday/summary` | Full leadership summary |
| POST | `/api/chat` | Main conversation endpoint |
| POST | `/api/refresh` | Force re-fetch from Monday.com |

## Data Cleaning Pipeline

The cleaner handles real-world messiness:
- **Header-row pollution**: Column names appearing as data values
- **Date normalization**: Multiple formats → consistent datetime
- **Sector normalization**: Fuzzy matching inconsistent names
- **Currency parsing**: Strip symbols, handle Cr/Lakh suffixes
- **Missing values**: Per-column-type strategies (numeric→0, text→"Unknown", dates→NaT)
- **Dedup**: Serial # for work orders, composite key for deals

Every fix is tracked in a quality report returned alongside the cleaned data.

## Business Metrics

All computed in `insights.py` using Pandas:
- Total Revenue, Revenue by Sector
- Pipeline Value (raw + probability-weighted)
- Conversion Rate
- Average Deal Size
- Delayed Work Orders
- Work Orders by Status/Sector
- Billing & Collection Summary
- Top Clients (cross-board)
- Cross-Board Analysis (deals-only vs WO-only clients)
- Leadership Summary (aggregated KPIs)
