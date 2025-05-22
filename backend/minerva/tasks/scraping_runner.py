# minerva/tasks/scraping_runner.py
import asyncio
import logging
from minerva.config import logging_config
from minerva.tasks.services.scraping_service import scrape_and_embed_all_sources, send_scraping_summary_email

# Initialize logging
logging_config.setup_logging()
logger = logging.getLogger("minerva.tasks.scraping_tasks")

async def run_scraping_task(worker_index: int, total_workers: int, target_date: str):
    """Run a portion of the scraping tasks based on worker index and total workers."""
    logger.info(f"Starting scraping task for worker {worker_index + 1} of {total_workers}")

    try:
        # Call the scraping service, passing worker_index and total_workers
        scraping_summary = await scrape_and_embed_all_sources(
            worker_index=worker_index,
            total_workers=total_workers,
            start_date=target_date
        )
        logger.info(f"Scraping completed for worker {worker_index + 1}: {scraping_summary}")

        # Send summary email for this worker’s results
        email_response = await send_scraping_summary_email(scraping_summary, worker_index, total_workers)
        logger.info(f"Email sent for worker {worker_index + 1}: {email_response}")

        return {
            "processed_results": scraping_summary.get("processed_results", []),
            "total_processed": scraping_summary.get("total_processed", 0),
            "email_response": email_response
        }
    except Exception as e:
        logger.error(f"Error in scraping task for worker {worker_index + 1}: {str(e)}", exc_info=True)
        raise

async def main(worker_index: int, total_workers: int, target_date: str, logger=None):
    """Main entry point for the script, compatible with APScheduler."""
    if logger is None:
        logger = logging.getLogger("minerva.tasks.scraping_tasks")
        logging_config.setup_logging()

    result = await run_scraping_task(worker_index=worker_index, total_workers=total_workers, target_date=target_date)
    logger.info(f"Scraping task completed for worker {worker_index + 1}: {result}")

if __name__ == "__main__":
    import sys
    worker_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    total_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    asyncio.run(main(worker_index, total_workers))