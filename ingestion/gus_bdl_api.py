"""
GUS BDL (Bank Danych Lokalnych) API client.
Fetches structured historical timeseries: CPI, wages, unemployment.
API docs: https://bdl.stat.gov.pl/api/v1/
"""

import logging

import requests

logger = logging.getLogger(__name__)

BDL_API = "https://bdl.stat.gov.pl/api/v1"
HEADERS = {"Accept": "application/json"}

# Variable IDs confirmed from BDL API
_CPI_VARS = {
    217230: "ogółem",
    217231: "żywność i napoje bezalkoholowe",
    217232: "napoje alkoholowe i wyroby tytoniowe",
    217233: "odzież i obuwie",
    217234: "mieszkanie",
    217235: "zdrowie",
    217236: "transport",
    217237: "rekreacja i kultura",
    217238: "edukacja",
}
_WAGES_VAR = 64428       # Przeciętne miesięczne wynagrodzenia brutto ogółem (PLN)
_UNEMPLOY_VAR = 60270    # Stopa bezrobocia rejestrowanego ogółem (%)

_YEARS = list(range(2010, 2026))


def _get(var_id: int, years: list[int]) -> list[dict] | None:
    year_params = "&".join(f"year={y}" for y in years)
    url = f"{BDL_API}/data/by-variable/{var_id}?unit-level=0&{year_params}&format=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("results", [{}])[0].get("values", [])
    except Exception as e:
        logger.warning(f"BDL API call failed for var {var_id}: {e}")
        return None


def _vals_to_table(values: list[dict]) -> str:
    return "\n".join(
        f"  {v['year']}: {v['val']}"
        for v in sorted(values, key=lambda x: x["year"])
        if v.get("val") is not None
    )


def fetch_cpi_timeseries() -> list[dict]:
    """Annual CPI index (rok poprzedni = 100) for Poland, 2010-2025."""
    docs = []

    # Overall CPI as a rich narrative doc
    overall = _get(217230, _YEARS)
    if not overall:
        return docs

    rows = {v["year"]: v["val"] for v in overall if v.get("val") is not None}

    # Find peak and recent trend
    peak_year = max(rows, key=rows.get)
    recent_years = sorted(rows)[-5:]
    recent = {y: rows[y] for y in recent_years if y in rows}

    lines = [
        "Wskaźnik cen towarów i usług konsumpcyjnych (CPI) - Polska",
        "Źródło: GUS Bank Danych Lokalnych",
        "Metodologia: rok poprzedni = 100 (wartość 105 oznacza inflację 5%)",
        "",
        "Dane roczne (rok poprzedni = 100):",
        _vals_to_table(overall),
        "",
        f"Szczyt inflacji: {peak_year} ({rows[peak_year]})",
        "Ostatnie 5 lat: " + ", ".join(f"{y}: {rows[y]}" for y in recent_years if y in rows),
    ]

    docs.append({
        "text": "\n".join(lines),
        "metadata": {
            "source": "GUS BDL - CPI",
            "title": "Inflacja CPI Polska 2010-2025 (dane roczne)",
            "date": "2025",
            "url": "https://bdl.stat.gov.pl",
            "type": "cpi_timeseries",
        },
    })

    # One combined doc with all CPI categories
    cat_lines = [
        "Składowe inflacji CPI według kategorii - Polska (rok poprzedni = 100)",
        "Źródło: GUS Bank Danych Lokalnych",
        "",
    ]
    for var_id, label in list(_CPI_VARS.items())[1:]:  # skip ogółem
        vals = _get(var_id, _YEARS[-6:])  # last 6 years for categories
        if vals:
            recent_vals = sorted(vals, key=lambda x: x["year"])[-3:]
            cat_lines.append(
                f"{label}: " + ", ".join(f"{v['year']}: {v['val']}" for v in recent_vals)
            )

    docs.append({
        "text": "\n".join(cat_lines),
        "metadata": {
            "source": "GUS BDL - CPI kategorie",
            "title": "Inflacja CPI Polska - składowe (żywność, mieszkanie, transport...)",
            "date": "2025",
            "url": "https://bdl.stat.gov.pl",
            "type": "cpi_categories",
        },
    })

    logger.info(f"Fetched {len(docs)} CPI docs from GUS BDL")
    return docs


def fetch_wages_timeseries() -> list[dict]:
    """Annual average gross monthly wages (PLN) for Poland, 2010-2025."""
    vals = _get(_WAGES_VAR, _YEARS)
    if not vals:
        return []

    rows = {v["year"]: v["val"] for v in vals if v.get("val") is not None}
    recent = sorted(rows)[-5:]

    # Compute YoY growth for recent years
    growth_lines = []
    sorted_years = sorted(rows)
    for i, y in enumerate(sorted_years):
        if i > 0:
            prev = sorted_years[i - 1]
            if prev in rows and rows[prev] > 0:
                pct = (rows[y] - rows[prev]) / rows[prev] * 100
                growth_lines.append(f"  {y}: {rows[y]:.0f} PLN (+{pct:.1f}% r/r)")
        else:
            growth_lines.append(f"  {y}: {rows[y]:.0f} PLN")

    text = "\n".join([
        "Przeciętne miesięczne wynagrodzenia brutto - Polska",
        "Źródło: GUS Bank Danych Lokalnych",
        "Jednostka: PLN (złotych) brutto",
        "",
        "Dane roczne:",
        *growth_lines,
        "",
        f"Wynagrodzenie w {recent[-1]}: {rows.get(recent[-1], '?')} PLN",
        f"Wzrost w ciągu 5 lat ({recent[0]}→{recent[-1]}): "
        f"{rows.get(recent[-1],0)/rows.get(recent[0],1)*100-100:.0f}%",
    ])

    logger.info("Fetched wages timeseries from GUS BDL")
    return [{
        "text": text,
        "metadata": {
            "source": "GUS BDL - Wynagrodzenia",
            "title": "Przeciętne wynagrodzenia brutto Polska 2010-2025",
            "date": "2025",
            "url": "https://bdl.stat.gov.pl",
            "type": "wages_timeseries",
        },
    }]


def fetch_unemployment_timeseries() -> list[dict]:
    """Annual registered unemployment rate (%) for Poland, 2010-2025."""
    vals = _get(_UNEMPLOY_VAR, _YEARS)
    if not vals:
        return []

    rows = {v["year"]: v["val"] for v in vals if v.get("val") is not None}
    peak_year = max(rows, key=rows.get)
    min_year = min(rows, key=rows.get)

    text = "\n".join([
        "Stopa bezrobocia rejestrowanego - Polska",
        "Źródło: GUS Bank Danych Lokalnych",
        "Jednostka: % (procent)",
        "",
        "Dane roczne:",
        _vals_to_table(vals),
        "",
        f"Szczyt bezrobocia w badanym okresie: {peak_year} ({rows[peak_year]}%)",
        f"Najniższe bezrobocie: {min_year} ({rows[min_year]}%)",
        f"Ostatni rok ({max(rows)}): {rows[max(rows)]}%",
    ])

    logger.info("Fetched unemployment timeseries from GUS BDL")
    return [{
        "text": text,
        "metadata": {
            "source": "GUS BDL - Bezrobocie",
            "title": "Stopa bezrobocia rejestrowanego Polska 2010-2025",
            "date": "2025",
            "url": "https://bdl.stat.gov.pl",
            "type": "unemployment_timeseries",
        },
    }]


def fetch_all_bdl() -> list[dict]:
    docs = []
    docs.extend(fetch_cpi_timeseries())
    docs.extend(fetch_wages_timeseries())
    docs.extend(fetch_unemployment_timeseries())
    logger.info(f"GUS BDL total: {len(docs)} documents")
    return docs
