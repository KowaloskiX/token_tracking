import asyncio
import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from minerva.config.logging_config import setup_logging
from minerva.tasks.scraping_runner import main as scraping_main
from minerva.tasks.monitoring_runner import main as monitoring_main
from minerva.tasks.cleanup_runner import main as cleanup_main
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import nltk
from pathlib import Path

load_dotenv()

setup_logging()
logger = logging.getLogger("minerva.tasks.scheduler")

# Set a writable NLTK data directory
NLTK_DATA_DIR = Path("/home/vscode/nltk_data")  # Adjust based on your environment
if not NLTK_DATA_DIR.exists():
    NLTK_DATA_DIR.mkdir(parents=True, exist_ok=True)
nltk.data.path.append(str(NLTK_DATA_DIR))

# Download NLTK punkt_tab resource3
def download_nltk_data():
    try:
        # Check if punkt_tab is already downloaded
        if not nltk.data.find('tokenizers/punkt_tab'):
            logger.info("Downloading NLTK punkt_tab resource...")
            nltk.download('punkt_tab', download_dir=str(NLTK_DATA_DIR), raise_on_error=True)
            logger.info("Successfully downloaded NLTK punkt_tab resource")
        else:
            logger.info("NLTK punkt_tab resource already present")
    except Exception as e:
        logger.error(f"Failed to download NLTK punkt_tab resource: {str(e)}", exc_info=True)
        raise RuntimeError(f"Cannot proceed without NLTK punkt_tab: {str(e)}")

# Run the download at startup
download_nltk_data()

def configure_scheduler(loop):
    logger.info("Configuring APScheduler...")
    scheduler = AsyncIOScheduler(event_loop=loop)

    def run_coroutine(coro):
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result()
        except Exception as e:
            logger.error(f"Error running coroutine: {str(e)}", exc_info=True)
            raise

    def get_today():
        return datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d")

    # New helper – previous week's same weekday
    def get_last_week_date():
        return (datetime.now(pytz.timezone("Europe/Warsaw")).date() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Use WORKER_INDEX, TOTAL_*_WORKERS, and WORKER_TYPE from environment
    worker_index = int(os.getenv("WORKER_INDEX", 0))
    total_scraping_workers = int(os.getenv("TOTAL_SCRAPING_WORKERS", 12))
    total_cleanup_workers = int(os.getenv("TOTAL_CLEANUP_WORKERS", 1))
    worker_type = os.getenv("WORKER_TYPE", "scraping")  # Default to scraping if not set

    # Schedule jobs based on worker type
    if worker_type == "scraping":
        scheduler.add_job(
            lambda: run_coroutine(scraping_main(worker_index, total_scraping_workers, "2025-06-27", None)),
            trigger=CronTrigger(hour=11, minute=12, day_of_week='mon-sun', timezone="Europe/Warsaw"),
            name=f"scraping_worker_{worker_index}",
            replace_existing=True
        )
    elif worker_type == "analysis_producer":
        from minerva.tasks.analyses.analysis_task_producer import main as producer_main
        scheduler.add_job(
            lambda: run_coroutine(producer_main()),
            trigger=CronTrigger(hour=22, minute=30, day_of_week='mon-fri', timezone="Europe/Warsaw"),
            name="analysis_task_producer",
            replace_existing=True
        )
    elif worker_type == "analysis":
        # NEW: Analysis workers run continuously, no cron needed
        logger.info("Analysis workers now run continuously via simple_analysis_worker")
    elif worker_type == "monitoring" and worker_index == 0:
        scheduler.add_job(
            lambda: run_coroutine(monitoring_main(0, 1, None)),
            trigger=CronTrigger(hour=19, minute=30, day_of_week='mon-fri', timezone="Europe/Warsaw"),
            name="monitoring_worker_0",
            replace_existing=True
        )
    elif worker_type == "cleanup":
        scheduler.add_job(
            lambda: run_coroutine(cleanup_main(worker_index, total_cleanup_workers, get_last_week_date())),
            trigger=CronTrigger(hour=12, minute=0, day_of_week='mon-fri', timezone="Europe/Warsaw"),
            name=f"cleanup_worker_{worker_index}",
            replace_existing=True
        )

    for job in scheduler.get_jobs():
        logger.info(f"Scheduled job: {job.name} with trigger {job.trigger}")
    return scheduler

async def main():
    logger.info(f"Starting tasks_app.py with WORKER_INDEX={os.getenv('WORKER_INDEX', 0)}, WORKER_TYPE={os.getenv('WORKER_TYPE', 'scraping')}...")
    loop = asyncio.get_event_loop()
    scheduler = configure_scheduler(loop)
    scheduler.start()
    logger.info("APScheduler started successfully")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down APScheduler...")
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
