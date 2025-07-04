import asyncio
import logging
from datetime import datetime
from minerva.config import logging_config
from minerva.core.services.tender_notification_service import notify_tender_outcomes
from minerva.tasks.services.historical_tender_service import HistoricalTenderService
from minerva.tasks.services.tender_insert_service import TenderInsertConfig

# Initialize logging
logging_config.setup_logging()
logger = logging.getLogger("minerva.tasks.historical_tasks")

async def run_historical_task(date: str = None):
    """Run historical tender processing for a specific date."""
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")
    
    logger.info(f"Starting historical tender processing for date: {date}")

    try:
        # Create service configuration
        historical_config = TenderInsertConfig.create_default(
            pinecone_index="historical-tenders",
            pinecone_namespace="",
            embedding_model="text-embedding-3-large",
            elasticsearch_index="historical-tenders"
        )
        
        historical_service = HistoricalTenderService(config=historical_config)
        
        # Step 1: Fetch and embed historical tenders for the current day
        logger.info(f"Step 1: Fetching and embedding historical tenders for {date}")
        extraction_inputs = {
            'start_date': date,
            'end_date': date,
            'max_pages': 150
        }
        
        extraction_result = await historical_service.process_historical_tenders(extraction_inputs)
        
        # Log extraction results
        embedding_count = extraction_result.get("embedding_result", {}).get("processed_count", 0)
        elasticsearch_count = extraction_result.get("elasticsearch_result", {}).get("stored_count", 0)
        
        logger.info(f"Extraction completed - Embedded: {embedding_count}, Elasticsearch: {elasticsearch_count}")
        
        # Step 2: Query by initiation date and update finished_id in TenderAnalysisResults
        logger.info(f"Step 2: Querying historical tenders and updating TenderAnalysisResults for {date}")
        
        update_result = await historical_service.query_by_initiation_date_and_update_finished_id(
            initiation_date=date,
            top_k=1200,  # Get all tenders for the date
            embedding_model="text-embedding-3-large",
            score_threshold=0.0
        )
        
        # Log update results
        total_found = update_result.get("total_results", 0)
        updated_with_url = len(update_result.get("updated_with_url", []))
        updated_without_url = len(update_result.get("updated_without_url", []))
        not_matched_primary = len(update_result.get("not_matched_primary", []))
        not_matched_fallback = len(update_result.get("not_matched_fallback", []))
        updated_tender_analysis_ids = len(update_result.get("updated_tender_analysis_ids", []))
        
        logger.info(
            f"Update completed - Found: {total_found}, "
            f"Updated (URL match): {updated_with_url}, "
            f"Updated (semantic match): {updated_without_url}, "
            f"Total updated tender analysis IDs: {updated_tender_analysis_ids}, "
            f"Not matched (primary): {not_matched_primary}, "
            f"Not matched (fallback): {not_matched_fallback}"
        )
        
        # Prepare summary result
        result = {
            "date": date,
            "extraction": {
                "embedded_count": embedding_count,
                "elasticsearch_count": elasticsearch_count,
                "metadata": extraction_result.get("metadata")
            },
            "updates": {
                "total_found": total_found,
                "updated_with_url": updated_with_url,
                "updated_without_url": updated_without_url,
                "not_matched_primary": not_matched_primary,
                "not_matched_fallback": not_matched_fallback,
                "updated_tender_analysis_ids": update_result.get("updated_tender_analysis_ids", [])  # Pass the actual IDs for notifications
            }
        }
        
        # Send notifications to users for tenders with outcomes
        try:
            # Check if any tender analysis results were actually updated (more reliable than URL counts)
            updated_tender_analysis_ids = update_result.get("updated_tender_analysis_ids", [])
            if len(updated_tender_analysis_ids) > 0:
                logger.info(f"Sending notifications for {len(updated_tender_analysis_ids)} updated tenders")
                notification_results = await notify_tender_outcomes(result)
                logger.info(f"Outcome notification results: {notification_results}")
            else:
                logger.info("No tender analysis results were updated - skipping notifications")
        except Exception as e:
            logger.error(f"Failed to send notifications for tender outcomes: {str(e)}")
        
        logger.info(f"Historical tender processing completed successfully for {date}")
        return result
        
    except Exception as e:
        logger.error(f"Error in historical tender processing for {date}: {str(e)}", exc_info=True)
        raise

async def main(date: str = None, logger=None):
    """Main entry point for the script, compatible with APScheduler."""
    if logger is None:
        logger = logging.getLogger("minerva.tasks.historical_tasks")
        logging_config.setup_logging()

    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    result = await run_historical_task(date=date)
    logger.info(f"Historical task completed for {date}: {result}")

if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(date)) 