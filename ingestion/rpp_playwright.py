"""
Playwright-based scraper for NBP RPP interest rate decisions.
Requires headed (non-headless) Chromium to bypass Incapsula WAF on nbp.pl.
Run locally with a display (DISPLAY or WAYLAND_DISPLAY set), then push docs.json.
"""

import asyncio
import logging
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

RPP_ARCHIVE_URL = "https://nbp.pl/kategoria/aktualnosci/rpp/"

MONTHS_PL = {
    "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04",
    "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08",
    "września": "09", "października": "10", "listopada": "11", "grudnia": "12",
}


def _parse_date(text: str) -> str:
    m = re.search(
        r"(\d{1,2})\s+(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
        r"września|października|listopada|grudnia)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if m:
        day, month, year = m.groups()
        return f"{year}-{MONTHS_PL[month.lower()]}-{int(day):02d}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    return ""


async def _collect_article_links(page) -> list[str]:
    """Collect all unique /rpp-* article links, clicking through all pagination pages."""
    all_links: set[str] = set()
    page_num = 1

    while True:
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.filter(a => a.href.includes('/rpp-') || a.href.includes('/komunikat-prasowy-z-posiedzenia-rpp')).map(a => a.href)",
        )
        before = len(all_links)
        all_links.update(links)
        logger.info(f"Page {page_num}: +{len(all_links) - before} links (total {len(all_links)})")

        # Find "next" arrow button — disabled on last page
        next_btn = await page.query_selector("a.next.page-link:not([disabled])")
        if not next_btn:
            break

        # Check if it's truly disabled (parent li has 'disabled' class)
        parent_disabled = await next_btn.evaluate(
            "el => el.closest('li')?.classList.contains('disabled') ?? false"
        )
        if parent_disabled:
            break

        await next_btn.click()
        await page.wait_for_timeout(2500)
        page_num += 1

    return list(all_links)


async def scrape_rpp_playwright(limit: int = 20, year_filter: int = None) -> list[dict]:
    """
    Scrape RPP press releases from nbp.pl using headed Chromium.
    Must be run locally with a display — not on Render.
    """
    docs = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="pl-PL",
        )
        page = await ctx.new_page()

        url = RPP_ARCHIVE_URL
        if year_filter:
            url += f"?year={year_filter}"

        logger.info(f"Loading RPP archive: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(4000)

        if "incapsula" in (await page.content()).lower():
            logger.error("WAF still blocking in headed mode")
            await browser.close()
            return []

        article_links = await _collect_article_links(page)
        logger.info(f"Found {len(article_links)} article links")

        seen = set()
        for href in article_links:
            if len(docs) >= limit:
                break
            if href in seen:
                continue
            seen.add(href)

            try:
                sub = await ctx.new_page()
                await sub.goto(href, wait_until="networkidle", timeout=30000)
                await sub.wait_for_timeout(1500)

                title = await sub.title()
                content = await sub.inner_text("main") if await sub.query_selector("main") else await sub.inner_text("body")
                await sub.close()

                content = content.strip()
                if len(content) < 100:
                    continue

                date = _parse_date(content[:600])
                # fallback: extract date from URL slug like rpp-08-07-2026
                if not date:
                    m = re.search(r"rpp-(\d{2})-(\d{2})-(\d{4})", href)
                    if m:
                        day, month, year = m.groups()
                        date = f"{year}-{month}-{day}"

                docs.append({
                    "text": content,
                    "metadata": {
                        "source": "NBP - RPP",
                        "title": title.split("|")[0].strip() if title else "Komunikat RPP",
                        "url": href,
                        "date": date,
                        "type": "rpp_decision",
                    },
                })
                logger.info(f"OK [{date}] {title[:60]}")

            except Exception as e:
                logger.warning(f"Failed {href}: {e}")

        await browser.close()

    logger.info(f"Scraped {len(docs)} RPP documents")
    return docs


def scrape_rpp_communications_playwright(limit: int = 20) -> list[dict]:
    return asyncio.run(scrape_rpp_playwright(limit))
