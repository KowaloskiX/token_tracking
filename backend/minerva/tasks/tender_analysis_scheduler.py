import asyncio
import logging
import os
from datetime import datetime, timedelta

from minerva.tasks.analysis_runner import run_tender_analysis_for_user_and_date
from minerva.config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("minerva.tender_analysis_scheduler")

# --- CONFIGURATION ---

USER_ID = "67c6cb742fee91862e135247"    
ANALYSIS_ID = "680eb345e1189b4f5ce9dd32" 
DATES = [
    "2025-04-28",
]  #dates, one for each worker

# --- MAIN SCHEDULER LOGIC ---

async def main():
    worker_index = int(os.getenv("WORKER_INDEX", 0))
    if worker_index >= len(DATES):
        logger.error(f"WORKER_INDEX {worker_index} out of range for DATES list")
        return

    target_date = DATES[worker_index]
    logger.info(f"Worker {worker_index} running analysis for date {target_date} (analysis_id={ANALYSIS_ID}, user_id={USER_ID})")

    # Call the function to run the analysis for this user, analysis_id, and date
    result = await run_tender_analysis_for_user_and_date(
        user_id=USER_ID,
        analysis_id=ANALYSIS_ID,
        target_date=target_date
    )
    logger.info(f"Analysis result for {target_date}: {result}")

if __name__ == "__main__":
    asyncio.run(main())