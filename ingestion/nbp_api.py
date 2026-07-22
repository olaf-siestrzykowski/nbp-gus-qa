"""
NBP public JSON API - reliable, no scraping required.
Endpoints: https://api.nbp.pl/
Covers: exchange rates, reference interest rates, CPI data from NBP.
"""

import requests
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

NBP_API = "https://api.nbp.pl/api"
HEADERS = {"Accept": "application/json"}


def _get(url: str) -> dict | list | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"NBP API call failed {url}: {e}")
        return None


def _format_rate_doc(data: dict, table: str) -> dict | None:
    try:
        rates = data.get("rates", [])
        date = data.get("effectiveDate", "")
        # Table C has bid/ask; A and B have mid
        if table == "C":
            rates_str = ", ".join(
                f"{r['currency']} ({r['code']}): kupno {r.get('bid','?')} / sprzedaż {r.get('ask','?')}"
                for r in rates
            )
        else:
            rates_str = ", ".join(
                f"{r['currency']} ({r['code']}): {r.get('mid','?')}"
                for r in rates
            )
        text = (
            f"Tabela kursów walut NBP - Tabela {table}\n"
            f"Data: {date}\n"
            f"Numer tabeli: {data.get('no', '')}\n\n"
            f"Kursy walut:\n{rates_str}"
        )
        return {
            "text": text,
            "metadata": {
                "source": f"NBP API - Kursy walut tabela {table}",
                "title": f"Tabela kursów walut {table} z dnia {date}",
                "date": date,
                "url": "https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/",
                "type": "exchange_rates",
            },
        }
    except Exception as e:
        logger.warning(f"Failed to format rate doc: {e}")
        return None


def fetch_exchange_rates(last_n: int = 14) -> list[dict]:
    """Fetch last N exchange rate tables from NBP API. Table B max is 14 (weekly)."""
    docs = []
    limits = {"A": last_n, "B": min(last_n, 14), "C": last_n}
    for table in ["A", "B", "C"]:
        url = f"{NBP_API}/exchangerates/tables/{table}/last/{limits[table]}/?format=json"
        data = _get(url)
        if not data:
            continue
        for entry in data:
            doc = _format_rate_doc(entry, table)
            if doc:
                docs.append(doc)
    logger.info(f"Fetched {len(docs)} exchange rate table docs")
    return docs


def fetch_reference_rate() -> list[dict]:
    """Fetch NBP reference interest rate history."""
    # Correct endpoint: /api/cennik/
    url = f"{NBP_API}/cennik/?format=json"
    # NBP doesn't expose interest rate history via public API - return empty
    # Interest rate info comes from RPP scraping instead
    return []


def fetch_gold_price(last_n: int = 14) -> list[dict]:
    """Fetch gold price history from NBP API."""
    url = f"{NBP_API}/cennik/zloto/ostatnie/{last_n}/?format=json"
    data = _get(url)
    if not data:
        return []

    rows = "\n".join(f"  {d['data']}: {d['cena']} PLN/g" for d in data)
    text = f"Ceny złota NBP (ostatnie {last_n} notowań):\n{rows}"
    docs = [{
        "text": text,
        "metadata": {
            "source": "NBP API - Ceny złota",
            "title": f"Ceny złota NBP - ostatnie {last_n} notowań",
            "date": data[-1]["data"] if data else "",
            "url": "https://www.nbp.pl/home.aspx?f=/kursy/zloto.html",
            "type": "gold_price",
        },
    }]
    logger.info(f"Fetched gold price doc ({len(data)} entries)")
    return docs
