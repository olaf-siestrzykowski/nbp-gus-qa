"""
Main ingestion script - run once to populate the vector store.
Usage: python -m ingestion.ingest
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.nbp_api import fetch_exchange_rates, fetch_reference_rate, fetch_gold_price
from ingestion.nbp_scraper import scrape_rpp_communications, scrape_nbp_press_releases
from ingestion.gus_scraper import scrape_gus
from ingestion.chunker import chunk_text
from app.vectorstore import add_documents, collection_count

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(nbp_limit: int = 20, gus_limit: int = 15):
    logger.info("=== Starting ingestion ===")

    all_docs = []

    logger.info("--- NBP API: Exchange rates ---")
    all_docs.extend(fetch_exchange_rates(last_n=30))

    logger.info("--- NBP API: Interest rates ---")
    all_docs.extend(fetch_reference_rate())

    logger.info("--- NBP API: Gold prices ---")
    all_docs.extend(fetch_gold_price(last_n=30))

    logger.info("--- NBP: RPP communications (scraping) ---")
    all_docs.extend(scrape_rpp_communications(limit=nbp_limit))

    logger.info("--- NBP: Press releases (scraping) ---")
    all_docs.extend(scrape_nbp_press_releases(limit=10))

    logger.info("--- GUS: Economic statistics (scraping) ---")
    all_docs.extend(scrape_gus(limit_per_source=gus_limit))

    logger.info(f"Total documents fetched: {len(all_docs)}")

    all_chunks = []
    for i, doc in enumerate(all_docs):
        doc_id = f"doc_{i}"
        chunks = chunk_text(doc["text"], doc_id, doc["metadata"])
        all_chunks.extend(chunks)

    logger.info(f"Total chunks to index: {len(all_chunks)}")

    if not all_chunks:
        logger.warning("No chunks to index. Check scrapers.")
        return

    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        n = add_documents(batch)
        logger.info(f"Indexed {i + n}/{len(all_chunks)} chunks")

    logger.info(f"=== Done. Total in DB: {collection_count()} chunks ===")


if __name__ == "__main__":
    run()
