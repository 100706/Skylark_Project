# Decision Log — AI BI Agent for Monday.com

## Assumptions

1. **Monday.com boards are the single source of truth.** No local database. Data is fetched live from the API on each session (cached in memory for the duration).

2. **Data was imported as text columns intentionally** to demonstrate the cleaning pipeline against real-world messiness. We do not "fix" this at the Monday.com level.

3. **Read-only access.** The agent never writes back to Monday.com.

4. **Masked/anonymized data.** Company names are coded (COMPANY089, WOCOMPANY_002). Deal values are masked but proportional. All business logic works on the masked data.

5. **Board names may vary.** Dynamic discovery via fuzzy matching handles board name variations. Env overrides exist as a demo-day safety net.

## Key Trade-offs

| Decision | Alternative | Why This Choice |
|----------|-------------|-----------------|
| **Pandas for all metrics** vs LLM computing numbers | Could have let Gemini calculate from raw data | Deterministic, auditable, no hallucination risk. LLM only narrates. |
| **In-memory cache** vs Database/Redis | Could use SQLite or Redis | No sync logic needed; Monday.com is source of truth. Cache is session-scoped. |
| **Gemini 2.0 Flash** vs GPT-4 / Claude | Could use OpenAI | Free tier, fast latency, sufficient for explanation tasks. |
| **Vanilla CSS** vs TailwindCSS | Could use Tailwind utility classes | Faster initial setup without build config; full design control. |
| **Flask** vs FastAPI / Express | Could use async framework | 6-hour constraint; Flask is the fastest to MVP for this team. |
| **Keyword fallback** for intent | Could rely solely on LLM | Resilience against API failures or slow responses. |
| **rapidfuzz** for fuzzy matching | Could use exact string matching | Real-world data has inconsistent naming. Fuzzy matching handles this. |
| **No database** | Could persist conversations | Unnecessary complexity. Monday.com is the source of truth. |
| **Single system prompt** vs multiple specialized prompts | Could have separate prompts per intent | Simpler to maintain, sufficient for current scope. |

## What I'd Do Differently With More Time

1. **Streaming responses** — Use SSE/WebSocket for real-time LLM output instead of waiting for full response.
2. **Conversation persistence** — Store chat history in a lightweight DB (SQLite) for cross-session context.
3. **Chart generation** — Render actual charts (via Chart.js or Recharts) instead of text-based breakdowns.
4. **PDF export** — Generate downloadable leadership reports.
5. **Rate limiting** — Add request throttling to protect Monday.com and Gemini APIs.
6. **Unit tests** — Test the cleaning pipeline and business engine with edge cases.
7. **CI/CD** — GitHub Actions for lint, test, build, deploy.
8. **Multi-board support** — Extend beyond Work Orders + Deals to arbitrary boards.
9. **Caching with TTL** — Use Redis with time-based invalidation instead of in-memory cache.
10. **Data quality scoring** — Surface the quality report more prominently in the UI with visual indicators.

## Leadership Updates Interpretation

The "Leadership Update" is designed as an executive briefing that:
- Surfaces the 4-5 most important KPIs at a glance
- Highlights anomalies (delayed projects, collection gaps)
- Provides 2-3 actionable recommendations
- Flags data quality issues that could affect decision-making
- Is generated on-demand, not on a schedule, because the underlying data changes in Monday.com

This is different from a static dashboard — it's a **narrative** summary that adapts its emphasis based on what the data reveals.
