import asyncio
from datetime import datetime
import pytz
import logging
from typing import Dict, Any
from minerva.tasks.services.tender_insert_service import TenderInsertConfig
from minerva.tasks.sources.tender_source_manager import TenderSourceManager
from minerva.core.models.request.tender_extract import ExtractionRequest
import resend
import os

logger = logging.getLogger("minerva.tasks.scraping_tasks")

# Configuration for tender insertion services
tender_insert_config = TenderInsertConfig.create_default(
    pinecone_index="tenders",
    pinecone_namespace="",
    embedding_model="text-embedding-3-large",
    elasticsearch_index="tenders"
)

source_manager = TenderSourceManager(tender_insert_config)

async def scrape_and_embed_all_sources(
    max_pages: int = 100,
    start_date: str = None,
    worker_index: int = 0,
    total_workers: int = 1
) -> Dict[str, Any]:
    target_date = start_date or datetime.now(pytz.timezone('Europe/Warsaw')).strftime('%Y-%m-%d')
    extraction_request = ExtractionRequest(max_pages=max_pages, start_date=target_date)
    active_sources = source_manager.get_active_sources()

    if not active_sources:
        logger.info("No active sources to process.")
        return {
            "date": target_date,
            "processed_results": {},
            "total_processed": 0,
            "elasticsearch_results": {}
        }

    # Split sources among workers
    chunk_size = len(active_sources) // total_workers
    start_index = worker_index * chunk_size
    end_index = start_index + chunk_size if worker_index < total_workers - 1 else len(active_sources)
    worker_sources = active_sources[start_index:end_index]

    logger.info(f"Worker {worker_index + 1} of {total_workers} processing sources {start_index} to {end_index}")

    processed_results = {}
    elasticsearch_results = {}
    total_processed = 0
    
    for source in worker_sources:
        try:
            # Create the TenderInsertService for this source
            service = source_manager.create_tender_insert_service(source)
            
            # Process tenders for both Pinecone and Elasticsearch
            result = await service.process_tenders(extraction_request)
            
            # Extract results
            pinecone_result = result.get("embedding_result", {})
            es_result = result.get("elasticsearch_result", {})
            
            # Update results tracking
            processed_count = pinecone_result.get("processed_count", 0)
            processed_results[source.value] = f"Processed {processed_count} tenders."
            total_processed += processed_count
            elasticsearch_results[source.value] = es_result
            
        except Exception as e:
            logger.error(f"Error processing source {source.value}: {str(e)}")
            processed_results[source.value] = f"Error: {str(e)}"
            elasticsearch_results[source.value] = {"error": str(e)}

    return {
        "date": target_date,
        "processed_results": processed_results,
        "total_processed": total_processed,
        "elasticsearch_results": elasticsearch_results
    }

async def send_scraping_summary_email(scraping_summary: Dict[str, Any], worker_index: int, total_workers: int) -> Dict[str, Any]:
    html_lines = [
        f"<h2>Scraping & Insertion Summary for {scraping_summary['date']} (Worker {worker_index + 1} of {total_workers})</h2>",
        "<ul>"
    ]

    for source, summary in scraping_summary['processed_results'].items():
        es_result = scraping_summary.get('elasticsearch_results', {}).get(source, {})
        es_stored = es_result.get('stored_count', 0)
        
        html_lines.append(f"<li><strong>{source}</strong>: {summary} Elasticsearch: {es_stored} stored.</li>")

    html_lines.append("</ul>")
    html_lines.append(
        f"<p><strong>Total tenders processed by Worker {worker_index + 1}:</strong> {scraping_summary['total_processed']}</p>"
    )
    html_content = "\n".join(html_lines)

    email_data = {
        "from": "piotr@asystent.ai",
        "to": "peter@yepp.ai",
        "subject": f"Scraping & Insertion Summary for {scraping_summary['date']} - Worker {worker_index + 1} of {total_workers}",
        "html": html_content
    }

    try:
        resend.api_key = os.getenv("RESEND_API_KEY")
        email_response = resend.Emails.send(email_data)
        logger.info(f"Summary email sent successfully for worker {worker_index + 1}: {email_response}")
        return email_response
    except Exception as e:
        logger.error(f"Error sending summary email for worker {worker_index + 1}: {str(e)}")
        raise e