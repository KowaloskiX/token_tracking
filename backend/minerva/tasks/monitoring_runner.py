import asyncio
import logging
from datetime import datetime
from minerva.config import logging_config
from minerva.tasks.services.monitoring_service import get_updates_for_tenders

# Initialize logging
logging_config.setup_logging()
logger = logging.getLogger("minerva.tasks.monitoring_tasks")

async def run_monitoring_task(worker_index: int, total_workers: int):
    """Run a portion of the monitoring tasks based on worker index and total workers."""
    logger.info(f"Starting monitoring task for worker {worker_index + 1} of {total_workers}")

    try:
        # Use today's date for monitoring
        date = datetime.today().strftime("%Y-%m-%d")
        result = await get_updates_for_tenders(
            date=date,
            worker_index=worker_index,
            total_workers=total_workers
        )
        logger.info(f"Monitoring completed for worker {worker_index + 1}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in monitoring task for worker {worker_index + 1}: {str(e)}", exc_info=True)
        raise

async def main(worker_index: int, total_workers: int, logger=None):
    """Main entry point for the script, compatible with APScheduler."""
    if logger is None:
        logger = logging.getLogger("minerva.tasks.monitoring_tasks")
        logging_config.setup_logging()

    result = await run_monitoring_task(worker_index=worker_index, total_workers=total_workers)
    logger.info(f"Monitoring task completed for worker {worker_index + 1}: {result}")

if __name__ == "__main__":
    import sys
    worker_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    total_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    asyncio.run(main(worker_index, total_workers))