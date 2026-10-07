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
- [ ] Fix RPP scraper - NBP site behind Incapsula WAF (blocks all bots), needs Playwright or manual HTML fetch
- [ ] NBP inflation reports (Raport o inflacji) - PDF scrape (also blocked by Incapsula)
- [x] Historical CPI timeseries from GUS BDL API (bdl.stat.gov.pl/api/v1) - variable 217230, 2003-2025
- [x] Employment / wages data (GUS BDL API) - variable 64428 (wages), 60270 (unemployment)
- [x] NBP gold price - fixed endpoint: /api/cenyzlota/last/{n}/ (was /api/cennik/zloto/ which was removed)

### Features
- [x] Chart generation: LLM extracts Chart.js config, rendered inline after answer
- [x] Streaming responses (FastAPI + SSE, frontend EventSource)
- [x] Markdown rendering in answer box
- [x] Follow-up question context (conversation history in /ask)
- [x] "Analyst mode" system prompt: opinionated, cites numbers, draws comparisons

### Deploy
- [ ] Sprawdzić `/status` na Render czy baza zaindeksowana po redeploy
- [ ] Dodać link do portfolio / cv.html jako projekt

## Groq: przejście na plan Developer
- [ ] console.groq.com → Settings → Billing: upgrade do Developer, podpiąć kartę
- [ ] Ustawić limit wydatków w Billing, jeśli Groq go oferuje (np. $5/mies.); jeśli nie, alert mailowy na kwotę
- [ ] Settings → Limits: sprawdzić nowe limity dla `openai/gpt-oss-120b` i `gpt-oss-20b` (oczekiwane ~250K TPM, bez limitu dziennego)
- [ ] Klucz API zostaje ten sam (limity są na organizację), nic nie zmieniać na Render
- [ ] Zdecydować o fallbacku: `GROQ_FALLBACK_MODEL=openai/gpt-oss-20b` dalej ma sens przy wycofaniu modelu, przy dziennym limicie już nie
- [ ] Dokończyć ewal: `python -m eval.run_eval --retry-errors` oraz `--retry-errors --tag 20b`, uzupełnić tabelę w README (PR #3)
- [ ] Zmergować PR #3 (raporty o inflacji, 656 chunków) i sprawdzić `/status` na Render (RAM 512 MB)
- [ ] Po tygodniu: zużycie w Groq Usage; jeśli koszt rośnie, obniżyć `RATE_LIMIT_GLOBAL_PER_DAY` w env na Render (domyślnie 1000 pytań/dobę ≈ $1)
