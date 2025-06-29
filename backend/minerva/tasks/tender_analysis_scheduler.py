import asyncio
import logging
import os
from datetime import datetime, timedelta

from minerva.tasks.analysis_runner import run_tender_analysis_for_user_and_date
from minerva.config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("minerva.tender_analysis_scheduler")

# --- CONFIGURATION ---

USER_ID = "6841db8e05c692b0289a70e0"    
ANALYSIS_ID = "6841e02305c692b0289a70e1" 
DATES = [
    "2025-06-13",
    "2025-06-16",
    "2025-06-17",
    "2025-06-18",
    "2025-06-20",
    "2025-06-23",
    "2025-06-24",
    "2025-06-25",
    "2025-06-26",
    "2025-06-27"
]  #dates, run all concurrently

# --- MAIN SCHEDULER LOGIC ---

async def run_analysis_for_date(date: str):
    """Run analysis for a specific date"""
    logger.info(f"Starting analysis for date {date} (analysis_id={ANALYSIS_ID}, user_id={USER_ID})")
    
    try:
        result = await run_tender_analysis_for_user_and_date(
            user_id=USER_ID,
            analysis_id=ANALYSIS_ID,
            target_date=date
        )
        logger.info(f"Analysis completed for {date}: {result}")
        return {"date": date, "result": result, "success": True}
    except Exception as e:
        logger.error(f"Analysis failed for {date}: {str(e)}")
        return {"date": date, "error": str(e), "success": False}

async def main():
    logger.info(f"Starting concurrent analysis for {len(DATES)} dates: {DATES}")
    
    # Run all dates concurrently
    tasks = [run_analysis_for_date(date) for date in DATES]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Log summary
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
    failed = len(results) - successful
    
    logger.info(f"Analysis summary: {successful} successful, {failed} failed")
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Unexpected error: {result}")
        elif not result.get("success", False):
            logger.error(f"Failed analysis for {result.get('date', 'unknown')}: {result.get('error', 'unknown error')}")

if __name__ == "__main__":
    asyncio.run(main())