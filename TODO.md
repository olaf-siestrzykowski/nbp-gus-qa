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
- [ ] Fix RPP scraper — fetch NBP interest rate decision texts (most interesting content)
- [ ] NBP inflation reports (Raport o inflacji) — PDF scrape
- [ ] Historical CPI timeseries from GUS BDL API (bdl.stat.gov.pl/api/v1)
- [ ] Employment / wages data (GUS BDL API)
- [ ] NBP gold price (find correct endpoint or scrape the HTML page)

### Features
- [ ] Chart generation: LLM picks chart type + data, backend renders it
- [ ] Streaming responses (FastAPI + SSE, frontend EventSource)
- [ ] Markdown rendering in answer box
- [ ] Follow-up question context (conversation history in /ask)
- [ ] "Analyst mode" system prompt: opinionated, cites numbers, draws comparisons

### Deploy
- [ ] Sprawdzić `/status` na Render czy baza zaindeksowana po redeploy
- [ ] Dodać link do portfolio / cv.html jako projekt
