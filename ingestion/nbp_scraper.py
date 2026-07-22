"""
Scraper for NBP (Narodowy Bank Polski) press releases:
- RPP interest rate decisions (komunikaty po posiedzeniach RPP)
- Inflation reports summaries
"""

import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

RPP_INDEX = "https://www.nbp.pl/home.aspx?f=/polityka_pieniezna/dokumenty/komunikaty_po_posiedzeniach_rpp.html"
NBP_BASE = "https://www.nbp.pl"

_session = requests.Session()
_session.headers.update(HEADERS)


def _get_soup(url: str) -> BeautifulSoup:
    r = _session.get(url, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")


def _pdf_to_text(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    text_parts = []
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _parse_date(text: str) -> str:
    patterns = [
        r"(\d{1,2})\s+(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)\s+(\d{4})",
        r"(\d{4})-(\d{2})-(\d{2})",
        r"(\d{2})\.(\d{2})\.(\d{4})",
    ]
    months_pl = {
        "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04",
        "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08",
        "września": "09", "października": "10", "listopada": "11", "grudnia": "12",
    }
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            g = m.groups()
            if len(g) == 3 and g[1] in months_pl:
                return f"{g[2]}-{months_pl[g[1]]}-{int(g[0]):02d}"
            elif len(g) == 3:
                return f"{g[0]}-{g[1]}-{g[2]}"
    return ""


def scrape_rpp_communications(limit: int = 20) -> list[dict]:
    """Fetch RPP interest rate decision press releases."""
    logger.info("Fetching RPP communications index...")
    soup = _get_soup(RPP_INDEX)
    docs = []

    links = soup.select("a[href*='.pdf'], a[href*='komunikat']")
    seen = set()

    for link in links:
        href = link.get("href", "")
        text = link.get_text(strip=True)

        if not href or href in seen:
            continue
        seen.add(href)

        url = href if href.startswith("http") else NBP_BASE + "/" + href.lstrip("/")

        try:
            if href.endswith(".pdf"):
                logger.info(f"Fetching PDF: {url}")
                content = _pdf_to_text(url)
            else:
                logger.info(f"Fetching HTML: {url}")
                page_soup = _get_soup(url)
                content = page_soup.get_text(separator="\n", strip=True)

            date = _parse_date(text) or _parse_date(content[:500])
            docs.append({
                "text": content,
                "metadata": {
                    "source": "NBP - RPP",
                    "title": text or "Komunikat po posiedzeniu RPP",
                    "url": url,
                    "date": date,
                    "type": "rpp_decision",
                },
            })

            if len(docs) >= limit:
                break

        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            continue

    logger.info(f"Fetched {len(docs)} RPP documents.")
    return docs


def scrape_nbp_press_releases(limit: int = 20) -> list[dict]:
    """Fetch general NBP monetary policy press releases."""
    year = datetime.now().year
    url = f"https://www.nbp.pl/home.aspx?f=/aktualnosci/wiadomosci_{year}.html"
    docs = []

    try:
        soup = _get_soup(url)
        items = soup.select(".news-item, .aktualnosc, article, .news")

        for item in items[:limit]:
            title_el = item.select_one("h2, h3, .title, a")
            link_el = item.select_one("a[href]")
            if not link_el:
                continue

            href = link_el["href"]
            page_url = href if href.startswith("http") else NBP_BASE + "/" + href.lstrip("/")
            title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)

            try:
                page_soup = _get_soup(page_url)
                content_el = page_soup.select_one("main, .content, article, #content")
                content = content_el.get_text(separator="\n", strip=True) if content_el else page_soup.get_text(separator="\n", strip=True)
                date = _parse_date(content[:500])
                docs.append({
                    "text": content,
                    "metadata": {
                        "source": "NBP - Aktualności",
                        "title": title,
                        "url": page_url,
                        "date": date,
                        "type": "nbp_news",
                    },
                })
            except Exception as e:
                logger.warning(f"Failed {page_url}: {e}")

    except Exception as e:
        logger.warning(f"NBP press releases index failed: {e}")

    logger.info(f"Fetched {len(docs)} NBP news documents.")
    return docs
