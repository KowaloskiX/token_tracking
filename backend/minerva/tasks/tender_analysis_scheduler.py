import asyncio
import logging
import os
from datetime import datetime, timedelta

from minerva.tasks.services.analysis_service import analyze_relevant_tenders_with_our_rag
from minerva.core.database.database import db
from minerva.core.models.user import User
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis
from minerva.config.logging_config import setup_logging
from bson import ObjectId

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

# --- HELPER FUNCTION ---

async def run_tender_analysis_for_user_and_date(
    user_id: str,
    analysis_id: str,
    target_date: str
):
    """Run tender analysis for a specific user, analysis, and target date."""
    try:
        # Fetch user from database
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            error_msg = f"User not found for ID: {user_id}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}

        current_user = User(**user_doc)

        # Fetch analysis from database
        analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(analysis_id)})
        if not analysis_doc:
            error_msg = f"Analysis not found for ID: {analysis_id}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}

        tender_analysis = TenderAnalysis(**analysis_doc)
        criteria_definitions = tender_analysis.criteria

        # Set up filter conditions for the target date
        filter_conditions = [
            {"field": "initiation_date", "op": "eq", "value": target_date}
        ]
        
        # Add source filters if specified in the analysis
        if analysis_doc.get("sources"):
            filter_conditions.append({
                "field": "source_type",
                "op": "in",
                "value": analysis_doc["sources"]
            })

        logger.info(f"Running analysis {analysis_id} for user {user_id} on date {target_date}")

        # Run the analysis
        result = await analyze_relevant_tenders_with_our_rag(
            analysis_id=analysis_id,
            tender_names_index_name="tenders",
            rag_index_name="files-rag-23-04-2025",
            embedding_model="text-embedding-3-large",
            elasticsearch_index_name="tenders",
            score_threshold=0.5,
            top_k=30,
            current_user=current_user,
            filter_conditions=filter_conditions,
            criteria_definitions=criteria_definitions
        )

        # Update the analysis last_run timestamp
        current_time = datetime.utcnow()
        await db.tender_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {
                "last_run": current_time,
                "updated_at": current_time
            }}
        )

        logger.info(f"Analysis {analysis_id} completed successfully. Analyzed {result.total_tenders_analyzed} tenders for date {target_date}")

        return {
            "success": True,
            "analysis_id": analysis_id,
            "user_id": user_id,
            "target_date": target_date,
            "total_tenders_analyzed": result.total_tenders_analyzed,
            "query": result.query
        }

    except Exception as e:
        error_msg = f"Error running analysis {analysis_id} for user {user_id} on date {target_date}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg, "success": False}

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