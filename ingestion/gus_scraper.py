"""
Scraper for GUS (Główny Urząd Statystyczny) press releases:
- CPI flash estimates (szybki szacunek inflacji)
- Monthly price index communications
- GDP flash estimates
"""

import io
import logging
import re

import pdfplumber
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (research bot; contact: portfolio project)"}
GUS_BASE = "https://stat.gov.pl"

GUS_SOURCES = [
    {
        "url": "https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/szybki-szacunek-wskaznika-cen-towarow-i-uslug-konsumpcyjnych/",
        "source_label": "GUS - Szybki szacunek CPI",
        "type": "cpi_flash",
    },
    {
        "url": "https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/",
        "source_label": "GUS - Wskaźniki CPI",
        "type": "cpi_monthly",
    },
    {
        "url": "https://stat.gov.pl/obszary-tematyczne/rachunki-narodowe/kwartalne-rachunki-narodowe/",
        "source_label": "GUS - PKB rachunki kwartalne",
        "type": "gdp_flash",
    },
]


def _get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")


def _pdf_to_text(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    parts = []
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
    return "\n".join(parts)


def _parse_date(text: str) -> str:
    months_pl = {
        "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04",
        "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08",
        "września": "09", "października": "10", "listopada": "11", "grudnia": "12",
        "styczeń": "01", "luty": "02", "marzec": "03", "kwiecień": "04",
        "maj": "05", "czerwiec": "06", "lipiec": "07", "sierpień": "08",
        "wrzesień": "09", "październik": "10", "listopad": "11", "grudzień": "12",
    }
    pat = r"(\d{1,2})\s+(" + "|".join(months_pl.keys()) + r")\s+(\d{4})"
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        return f"{m.group(3)}-{months_pl[m.group(2).lower()]}-{int(m.group(1)):02d}"
    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return ""


def _scrape_source(source_cfg: dict, limit: int) -> list[dict]:
    docs = []
    try:
        soup = _get_soup(source_cfg["url"])
        links = soup.select("a[href$='.pdf'], a[href*='komunikat'], a[href*='szacunek'], a[href*='wskaznik']")
        seen = set()

        for link in links:
            href = link.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)

            url = href if href.startswith("http") else GUS_BASE + "/" + href.lstrip("/")
            title = link.get_text(strip=True)

            try:
                if href.endswith(".pdf"):
                    logger.info(f"Fetching GUS PDF: {url}")
                    content = _pdf_to_text(url)
                else:
                    logger.info(f"Fetching GUS page: {url}")
                    page_soup = _get_soup(url)
                    content_el = page_soup.select_one("main, .content, article, #content, .komunikat")
                    content = content_el.get_text(separator="\n", strip=True) if content_el else page_soup.get_text(separator="\n", strip=True)

                if len(content) < 100:
                    continue

                date = _parse_date(title) or _parse_date(content[:500])
                docs.append({
                    "text": content,
                    "metadata": {
                        "source": source_cfg["source_label"],
                        "title": title,
                        "url": url,
                        "date": date,
                        "type": source_cfg["type"],
                    },
                })

                if len(docs) >= limit:
                    break

            except Exception as e:
                logger.warning(f"Failed {url}: {e}")

    except Exception as e:
        logger.warning(f"GUS index failed for {source_cfg['url']}: {e}")

    return docs


def scrape_gus(limit_per_source: int = 15) -> list[dict]:
    all_docs = []
    for src in GUS_SOURCES:
        docs = _scrape_source(src, limit_per_source)
        logger.info(f"{src['source_label']}: {len(docs)} docs")
        all_docs.extend(docs)
    return all_docs
