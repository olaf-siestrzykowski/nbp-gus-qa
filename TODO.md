# TODO - NBP/GUS Q&A

## Deployed
- [x] Render free tier deploy (Docker)
- [x] Jina AI embeddings (no local model, ~100MB RAM)
- [x] Pre-collected docs.json (98 docs / 436 chunks): exchange rates, GUS CPI, GDP quarterly

## Next: Pivot to Economic Analyst with Visuals

Reframe: instead of generic Q&A, make it an **opinionated economic analyst** that:
- Answers questions with historical context and trend commentary
- Generates inline charts (matplotlib/plotly → base64 PNG, or Chart.js via LLM-generated config)
- Compares current data to historical periods ("similar to 2008", "worst since 1993")

### Data to add
- [ ] Fix RPP scraper — NBP site behind Incapsula WAF (blocks all bots), needs Playwright or manual HTML fetch
- [ ] NBP inflation reports (Raport o inflacji) — PDF scrape (also blocked by Incapsula)
- [x] Historical CPI timeseries from GUS BDL API (bdl.stat.gov.pl/api/v1) — variable 217230, 2003-2025
- [x] Employment / wages data (GUS BDL API) — variable 64428 (wages), 60270 (unemployment)
- [x] NBP gold price — fixed endpoint: /api/cenyzlota/last/{n}/ (was /api/cennik/zloto/ which was removed)

### Features
- [ ] Chart generation: LLM picks chart type + data, backend renders it
- [ ] Streaming responses (FastAPI + SSE, frontend EventSource)
- [ ] Markdown rendering in answer box
- [ ] Follow-up question context (conversation history in /ask)
- [ ] "Analyst mode" system prompt: opinionated, cites numbers, draws comparisons

### Deploy
- [ ] Sprawdzić `/status` na Render czy baza zaindeksowana po redeploy
- [ ] Dodać link do portfolio / cv.html jako projekt
