# RAG evaluation report - baseline (vector search only, before routing)

Generated 2026-09-27 by `python -m eval.run_eval` - model `openai/gpt-oss-120b`, top_k=5, 26 questions with answers computed from `data/docs.json`.

| Category | Questions | Retrieval hit@k | Answer correct | Refused when it should |
|---|---|---|---|---|
| cpi_year | 7 | 6/7 (86%) | 6/7 (86%) | - |
| trend | 2 | 2/2 (100%) | 2/2 (100%) | - |
| unemployment_year | 4 | 2/4 (50%) | 2/4 (50%) | - |
| wages_year | 3 | 3/3 (100%) | 3/3 (100%) | - |
| cpi_category | 3 | 3/3 (100%) | 3/3 (100%) | - |
| rpp_rate | 3 | 3/3 (100%) | 3/3 (100%) | - |
| out_of_scope | 4 | - | - | 3/4 (75%) |
| **total** | **26** | **19/22 (86%)** | **19/22 (86%)** | **3/4 (75%)** |

## Failures

- **Jaka była inflacja CPI w Polsce w 2023 roku?** expected `11.4`, retrieved: NBP - RPP, NBP - RPP, GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne  
  > **Odpowiedź:** Na podstawie udostępnionego kontekstu nie ma informacji o wartości wskaźnika CPI (inflacji konsumenckiej) w Polsce za rok 2023. Dostarczone materiały zawierają jedynie: - decyzje Rady Polityki Pieniężnej N
- **Ile wynosiła stopa bezrobocia rejestrowanego w Polsce w 2013 roku?** expected `13.4`, retrieved: GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne, NBP - RPP  
  > **Odpowiedź:** W dostarczonym kontekście nie ma informacji dotyczących stopy bezrobocia rejestrowanego w Polsce w 2013 roku. Aby podać dokładną wartość, potrzebne byłyby dane z GUS (np. raport „Bezrobocie – wskaźniki” z 
- **Ile wynosiła stopa bezrobocia rejestrowanego w Polsce w 2023 roku?** expected `5.1`, retrieved: NBP - RPP, NBP - RPP, NBP - RPP, NBP - RPP, NBP - RPP  
  > **Odpowiedź:** W dostarczonym kontekście nie ma informacji o stopie bezrobocia rejestrowanego w Polsce w 2023 roku. Aby podać dokładną wartość, potrzebne byłyby dane z GUS (np. z Bazy Danych Lokalnych) lub innego oficjal
- **Jaki był wzrost PKB Niemiec w 2023 roku?** expected `refusal`, retrieved: GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne, GUS - PKB rachunki kwartalne  
  > **Brak dostępnych danych** W przedstawionym kontekście znajdują się wyłącznie informacje o produkcie krajowym brutto (PKB) Polski w poszczególnych kwartałach 2024 r. oraz o metodologii szacowania tych wskaźników. Nie ma 
