# RAG evaluation report

Generated 2026-09-27 by `python -m eval.run_eval` - model `openai/gpt-oss-120b`, top_k=5, 26 questions with answers computed from `data/docs.json`.

| Category | Questions | Retrieval hit@k | Answer correct | Refused when it should |
|---|---|---|---|---|
| cpi_year | 7 | 7/7 (100%) | 7/7 (100%) | - |
| trend | 2 | 2/2 (100%) | 2/2 (100%) | - |
| unemployment_year | 4 | 4/4 (100%) | 4/4 (100%) | - |
| wages_year | 3 | 3/3 (100%) | 3/3 (100%) | - |
| cpi_category | 3 | 3/3 (100%) | 3/3 (100%) | - |
| rpp_rate | 3 | 3/3 (100%) | 3/3 (100%) | - |
| out_of_scope | 4 | - | - | 3/3 (100%) |
| **total** | **26** | **22/22 (100%)** | **22/22 (100%)** | **3/3 (100%)** |

1 question(s) got no answer because of an API error (e.g. provider quota) and are excluded from the answer metrics:
- Ile kosztował metr kwadratowy mieszkania w Warszawie w 2024 roku?
