---
title: NBP GUS QA
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# NBP/GUS Economic Q&A

RAG-based Q&A over official Polish economic documents — NBP monetary policy decisions and GUS statistical releases.

**Stack:** FastAPI · ChromaDB · sentence-transformers · Groq (llama-3.3-70b)

**Data sources:** NBP exchange rates, RPP interest rate decisions, GUS CPI and GDP flash estimates.

> Ingestion runs automatically on startup (~2–3 min). Ask questions in Polish or English.
