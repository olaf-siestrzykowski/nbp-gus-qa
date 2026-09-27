"""Evaluate the RAG pipeline against questions whose answers are computed from the data.

Expected answers are derived from data/docs.json (the same documents the app indexes),
never typed by hand, so the golden set stays correct when the data is refreshed.

Metrics per question:
- retrieval_hit  - a chunk from the expected source is among the top-k retrieved
- answer_correct - the expected number / year appears in the answer (numeric tolerance)
- refused        - for questions the data cannot answer: the model says so instead of guessing

Usage:
    python -m eval.run_eval                  # all questions, writes eval/REPORT.md
    python -m eval.run_eval --limit 5        # quick smoke run
"""
import argparse
import json
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from app.config import settings
from app.rag import answer, retrieve

EVAL_DIR = Path(__file__).resolve().parent
DOCS_FILE = EVAL_DIR.parent / "data" / "docs.json"

MONTHS_PL = {
    1: "styczniu", 2: "lutym", 3: "marcu", 4: "kwietniu", 5: "maju", 6: "czerwcu",
    7: "lipcu", 8: "sierpniu", 9: "wrześniu", 10: "październiku", 11: "listopadzie", 12: "grudniu",
}
# "we wrześniu" - the preposition changes before "w" + consonant
PREPOSITION = {
    9: "we",
}
# "Brak dostępnych danych", "nie ma informacji o...", "kontekst nie zawiera..."
REFUSAL_RE = re.compile(
    r"\bbrak\b[^.]{0,30}(?:danych|informacj)|\bnie (?:ma|mam|posiadam|dysponuję)\b[^.]{0,40}(?:danych|informacj)"
    r"|nie zawiera|nie obejmuj|niewystarczając|poza zakresem|nie da się|nie można (?:podać|określić)"
)


def _series(text: str) -> dict[int, float]:
    """Parse "  2022: 114.4" / "  2022: 6706 PLN (+11.7% r/r)" lines into {year: value}."""
    return {int(y): float(v) for y, v in re.findall(r"^\s+(20\d\d):\s*([\d.]+)", text, flags=re.M)}


def build_golden(docs: list[dict]) -> list[dict]:
    by_source = defaultdict(list)
    for doc in docs:
        by_source[doc["metadata"].get("source")].append(doc)

    def only(source):
        return by_source[source][0]["text"]

    golden = []

    cpi = _series(only("GUS BDL - CPI"))
    for year in (2012, 2015, 2019, 2021, 2022, 2023, 2024):
        golden.append({
            "category": "cpi_year", "source": "GUS BDL - CPI",
            "question": f"Jaka była inflacja CPI w Polsce w {year} roku?",
            "expected": round(cpi[year] - 100, 1), "tolerance": 0.05,
        })
    peak = max(cpi, key=cpi.get)
    golden.append({
        "category": "trend", "source": "GUS BDL - CPI",
        "question": f"W którym roku w latach {min(cpi)}-{max(cpi)} inflacja CPI w Polsce była najwyższa?",
        "expected_year": peak,
    })

    unemployment = _series(only("GUS BDL - Bezrobocie"))
    for year in (2013, 2019, 2023, 2025):
        golden.append({
            "category": "unemployment_year", "source": "GUS BDL - Bezrobocie",
            "question": f"Ile wynosiła stopa bezrobocia rejestrowanego w Polsce w {year} roku?",
            "expected": unemployment[year], "tolerance": 0.05,
        })
    high = max(unemployment, key=unemployment.get)
    golden.append({
        "category": "trend", "source": "GUS BDL - Bezrobocie",
        "question": (f"W którym roku w latach {min(unemployment)}-{max(unemployment)} "
                     "bezrobocie w Polsce było najwyższe?"),
        "expected_year": high,
    })

    wages = _series(only("GUS BDL - Wynagrodzenia"))
    for year in (2015, 2020, 2024):
        golden.append({
            "category": "wages_year", "source": "GUS BDL - Wynagrodzenia",
            "question": f"Ile wynosiło przeciętne miesięczne wynagrodzenie brutto w Polsce w {year} roku?",
            "expected": wages[year], "tolerance": 1.0,
        })

    categories = only("GUS BDL - CPI kategorie")
    for label, name, year in (
        ("żywność i napoje bezalkoholowe", "żywności i napojów bezalkoholowych", 2023),
        ("transport", "transportu", 2025),
        ("mieszkanie", "mieszkania (użytkowania mieszkania i nośników energii)", 2024),
    ):
        value = float(re.search(rf"{re.escape(label)}:.*?{year}: ([\d.]+)", categories).group(1))
        golden.append({
            "category": "cpi_category", "source": "GUS BDL - CPI kategorie",
            "question": f"O ile procent zmieniły się ceny {name} w Polsce w {year} roku?",
            "expected": round(value - 100, 1), "tolerance": 0.05,
        })

    rpp = sorted(by_source["NBP - RPP"], key=lambda d: d["metadata"].get("date", ""))
    rates = []
    for doc in rpp:
        m = re.search(r"stop[aę] referencyjn\w*\s+(?:na poziomie\s+)?(\d+,\d+)\s*%", doc["text"])
        if m:
            rates.append((doc["metadata"]["date"], float(m.group(1).replace(",", "."))))
    picks = {rates[-1][0]}  # latest decision
    picks.add(max(rates, key=lambda r: r[1])[0])  # peak of the cycle
    picks.update(d for d, _ in rates[len(rates) // 3: len(rates) // 3 + 1])
    picks.update(d for d, _ in rates[2 * len(rates) // 3: 2 * len(rates) // 3 + 1])
    for doc_date, rate in rates:
        if doc_date in picks:
            d = date.fromisoformat(doc_date)
            when = f"{PREPOSITION.get(d.month, 'w')} {MONTHS_PL[d.month]} {d.year}"
            golden.append({
                "category": "rpp_rate", "source": "NBP - RPP",
                "question": f"Ile wynosiła stopa referencyjna NBP po posiedzeniu RPP {when} roku?",
                "expected": rate, "tolerance": 0.001,
            })

    for question in (
        "Jaki był wzrost PKB Niemiec w 2023 roku?",
        "Ile wynosiła inflacja w Czechach w 2022 roku?",
        "Jaka będzie stopa referencyjna NBP w 2030 roku?",
        "Ile kosztował metr kwadratowy mieszkania w Warszawie w 2024 roku?",
    ):
        golden.append({"category": "out_of_scope", "source": None, "question": question, "expect_refusal": True})

    return golden


def _numbers(text: str) -> list[float]:
    cleaned = re.sub(r"(?<=\d)[\s\u00a0\u202f](?=\d{3}\b)", "", text)  # "8 630" -> "8630"
    return [float(n.replace(",", ".")) for n in re.findall(r"-?\d+(?:[.,]\d+)?", cleaned)]


def score(item: dict, answer_text: str, retrieved_sources: list[str]) -> dict:
    lowered = answer_text.lower()
    result = {"retrieval_hit": None, "answer_correct": None, "refused": None}
    if item.get("source"):
        result["retrieval_hit"] = item["source"] in retrieved_sources
    if item.get("expect_refusal"):
        result["refused"] = bool(REFUSAL_RE.search(lowered))
    elif "expected_year" in item:
        result["answer_correct"] = str(item["expected_year"]) in answer_text
    else:
        expected, tol = item["expected"], item["tolerance"]
        # Deflation is often written as "spadek o 0,9%" rather than "-0,9%"
        candidates = [expected, abs(expected)] if expected < 0 else [expected]
        result["answer_correct"] = any(abs(n - c) <= tol for n in _numbers(answer_text) for c in candidates)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pause", type=float, default=8.0, help="seconds between questions (free-tier rate limits)")
    parser.add_argument("--report-only", action="store_true", help="rebuild REPORT.md from eval/results.jsonl")
    args = parser.parse_args()

    if args.report_only:
        rows = [json.loads(line) for line in (EVAL_DIR / "results.jsonl").read_text().splitlines() if line]
        write_report(rows)
        return

    golden = build_golden(json.loads(DOCS_FILE.read_text()))
    (EVAL_DIR / "golden.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in golden) + "\n"
    )
    golden = golden[: args.limit] if args.limit else golden

    rows = []
    for i, item in enumerate(golden, 1):
        retrieved = [c["metadata"].get("source") for c in retrieve(item["question"])]
        for attempt in range(3):
            try:
                answer_text = answer(item["question"])["answer"]
                break
            except Exception as e:  # rate limits / transient 5xx on free tiers
                print(f"  retry after error: {e}")
                time.sleep(30)
        else:
            answer_text = None
        if answer_text is None:
            # API failure (e.g. daily quota) - not a wrong answer, excluded from the metrics
            row = {**item, "retrieved": retrieved, "answer": "", "api_error": True,
                   "retrieval_hit": item["source"] in retrieved if item.get("source") else None,
                   "answer_correct": None, "refused": None}
        else:
            row = {**item, "retrieved": retrieved, "answer": answer_text, **score(item, answer_text, retrieved)}
        rows.append(row)
        verdict = "refused" if item.get("expect_refusal") else "correct"
        print(f"[{i}/{len(golden)}] {item['category']:18} retrieval={row['retrieval_hit']} "
              f"{verdict}={row['refused'] if item.get('expect_refusal') else row['answer_correct']}", flush=True)
        time.sleep(args.pause)

    (EVAL_DIR / "results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    )
    write_report(rows)


def _pct(values) -> str:
    values = [v for v in values if v is not None]
    return f"{sum(values)}/{len(values)} ({sum(values) / len(values):.0%})" if values else "-"


def write_report(rows: list[dict]):
    by_category = defaultdict(list)
    for r in rows:
        by_category[r["category"]].append(r)
    lines = [
        "# RAG evaluation report",
        "",
        f"Generated {date.today().isoformat()} by `python -m eval.run_eval` - model `{settings.groq_model}`, "
        f"top_k={settings.top_k}, {len(rows)} questions with answers computed from `data/docs.json`.",
        "",
        "| Category | Questions | Retrieval hit@k | Answer correct | Refused when it should |",
        "|---|---|---|---|---|",
    ]
    for category, items in by_category.items():
        lines.append(
            f"| {category} | {len(items)} | {_pct(r['retrieval_hit'] for r in items)} | "
            f"{_pct(r['answer_correct'] for r in items)} | {_pct(r['refused'] for r in items)} |"
        )
    lines.append(
        f"| **total** | **{len(rows)}** | **{_pct(r['retrieval_hit'] for r in rows)}** | "
        f"**{_pct(r['answer_correct'] for r in rows)}** | **{_pct(r['refused'] for r in rows)}** |"
    )
    errors = [r for r in rows if r.get("api_error")]
    if errors:
        lines += ["", f"{len(errors)} question(s) got no answer because of an API error (e.g. provider quota) "
                  "and are excluded from the answer metrics:"]
        lines += [f"- {r['question']}" for r in errors]
    failures = [r for r in rows if r["answer_correct"] is False or r["refused"] is False]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            expected = r.get("expected", r.get("expected_year", "refusal"))
            snippet = re.sub(r"\s+", " ", r["answer"])[:220]
            lines.append(f"- **{r['question']}** expected `{expected}`, retrieved: {', '.join(r['retrieved'])}  ")
            lines.append(f"  > {snippet}")
    (EVAL_DIR / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
