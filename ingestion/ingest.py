"""
Main ingestion script.

Two modes:
  python -m ingestion.ingest          # scrape live + save docs.json + embed
  python -m ingestion.ingest --embed  # load saved docs.json + embed only (no scraping)

Production (Render) uses --embed mode from pre-committed docs.json.
Run without --embed locally to refresh the data, then commit data/docs.json.
"""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.chunker import chunk_text
from app.vectorstore import add_documents, collection_count
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DOCS_FILE = Path(settings.chroma_path).parent / "docs.json"


def scrape_all(nbp_limit: int = 20, gus_limit: int = 15) -> list[dict]:
    from ingestion.nbp_api import fetch_exchange_rates, fetch_reference_rate, fetch_gold_price
    from ingestion.nbp_scraper import scrape_rpp_communications, scrape_nbp_press_releases
    from ingestion.gus_scraper import scrape_gus
    from ingestion.gus_bdl_api import fetch_all_bdl

    all_docs = []
    logger.info("--- NBP API: Exchange rates ---")
    all_docs.extend(fetch_exchange_rates(last_n=30))
    logger.info("--- NBP API: Interest rates ---")
    all_docs.extend(fetch_reference_rate())
    logger.info("--- NBP API: Gold prices ---")
    all_docs.extend(fetch_gold_price(last_n=30))
    logger.info("--- NBP: RPP communications ---")
    all_docs.extend(scrape_rpp_communications(limit=nbp_limit))
    logger.info("--- NBP: Press releases ---")
    all_docs.extend(scrape_nbp_press_releases(limit=10))
    logger.info("--- GUS: Economic statistics (scrapers) ---")
    all_docs.extend(scrape_gus(limit_per_source=gus_limit))
    logger.info("--- GUS BDL API: CPI / wages / unemployment timeseries ---")
    all_docs.extend(fetch_all_bdl())
    return all_docs


def embed_and_index(all_docs: list[dict]):
    all_chunks = []
    for i, doc in enumerate(all_docs):
        chunks = chunk_text(doc["text"], f"doc_{i}", doc["metadata"])
        all_chunks.extend(chunks)

    logger.info(f"Total chunks to index: {len(all_chunks)}")
    if not all_chunks:
        logger.warning("No chunks to index.")
        return

    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        n = add_documents(batch)
        logger.info(f"Indexed {i + n}/{len(all_chunks)} chunks")

    logger.info(f"=== Done. Total in DB: {collection_count()} chunks ===")


def run(embed_only: bool = False):
    logger.info("=== Starting ingestion ===")

    if embed_only:
        if not DOCS_FILE.exists():
            logger.error(f"docs.json not found at {DOCS_FILE}. Run without --embed first.")
            return
        logger.info(f"Loading pre-collected docs from {DOCS_FILE}")
        with open(DOCS_FILE) as f:
            all_docs = json.load(f)
        logger.info(f"Loaded {len(all_docs)} documents")
    else:
        all_docs = scrape_all()
        logger.info(f"Total documents fetched: {len(all_docs)}")
        DOCS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DOCS_FILE, "w") as f:
            json.dump(all_docs, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved docs to {DOCS_FILE}")

    embed_and_index(all_docs)


if __name__ == "__main__":
    embed_only = "--embed" in sys.argv
    run(embed_only=embed_only)
