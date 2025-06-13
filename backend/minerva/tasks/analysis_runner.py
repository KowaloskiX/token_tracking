import asyncio
import logging
from datetime import datetime
import pytz
import os
from minerva.api.routes.extensions.tenders.tender_analysis_routes import DEFAULT_CRITERIA
from minerva.core.models.extensions.tenders.tender_analysis import (
    AnalysisCriteria,
    TenderAnalysis,
    TenderAnalysisResult,
)
from minerva.tasks.sources.helpers import assign_order_numbers
import resend
from bson import ObjectId
from typing import Dict, List, Optional, Any
from minerva.core.database.database import db
from minerva.core.models.user import User
from minerva.core.utils.email_utils import (
    handle_send_email,
    build_tender_results_email_html,
)
from minerva.tasks.services.analysis_service import analyze_relevant_tenders_with_our_rag, run_partial_tender_analyses
from minerva.tasks.services.tender_initial_ai_filtering_service import get_saved_initial_ai_filter_results
from minerva.tasks.services.tender_description_filtering_service import get_saved_description_filter_results
from minerva.config import logging_config

# Initialize logging
logging_config.setup_logging()
logger = logging.getLogger("minerva.tasks.analysis_tasks")

async def send_summary_email(html_content: str):
    """Helper function to send the summary email."""
    email_data = {
        "from": "piotr@asystent.ai",
        "to": "peter@yepp.ai",
        "subject": f"Tender Analysis Summary for {datetime.now(pytz.timezone('Europe/Warsaw')).strftime('%Y-%m-%d')} (Worker {os.getenv('WORKER_INDEX', 'Unknown')})",
        "html": html_content
    }
    try:
        resend.api_key = os.getenv("RESEND_API_KEY")
        if not resend.api_key:
            raise ValueError("RESEND_API_KEY environment variable is not set")
        resend.Emails.send(email_data)
        logger.info("Analysis summary email sent successfully")
    except Exception as e:
        logger.error(f"Error sending analysis summary email: {str(e)}")


async def send_user_result_email(user_email: str, analysis_name: str, analysis_id: str, tenders: List[TenderAnalysisResult]):
    """Send an individualized email with tender links and descriptions."""
    try:
        html_content = build_tender_results_email_html(
            analysis_name=analysis_name,
            analysis_id=analysis_id,
            tenders=tenders,
        )

        await handle_send_email(
            user_email,
            f"Nowe przetargi - {analysis_name}",
            html_content,
        )
        logger.info(
            f"Sent tender summary email to {user_email} for {analysis_name}"
        )
    except Exception as exc:
        logger.error(
            f"Error sending tender summary email to {user_email}: {exc}"
        )

async def send_emails_to_recipients(recipient_user_ids: List[str], analysis_name: str, analysis_id: str, tenders: List[TenderAnalysisResult]):
    """Send emails to multiple recipients based on their user IDs."""
    if not recipient_user_ids:
        logger.info(f"No email recipients configured for analysis {analysis_name}")
        return
    
    for user_id in recipient_user_ids:
        try:
            user_data = await db.users.find_one({"_id": ObjectId(user_id)})
            if not user_data:
                logger.warning(f"User {user_id} not found for email notification")
                continue
                
            await send_user_result_email(
                user_email=user_data["email"],
                analysis_name=analysis_name,
                analysis_id=analysis_id,
                tenders=tenders,
            )
            logger.info(f"Email sent to {user_data['email']} for {analysis_name} - {len(tenders)} tenders found")
        except Exception as exc:
            logger.error(f"Failed to send email to user {user_id}: {exc}")

async def run_all_tender_analyses_task(
    target_date: str = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d"),
    top_k: int = 30,
    score_threshold: float = 0.5,
    filter_conditions: Optional[List[Dict[str, Any]]] = None,
    worker_index: int = 0,
    total_workers: int = 1
):
    """Run a portion of all tender analyses based on worker index and total workers."""
    logger.info(f"Starting analysis task for worker {worker_index + 1} of {total_workers} for date {target_date}")

    analyses_cursor = db.tender_analysis.find({"active": True})
    all_analyses = await analyses_cursor.to_list(None)

    if not all_analyses:
        logger.info("No active TenderAnalysis found to run.")
        html_content = f"<h2>Tender Analysis Summary for {target_date} (Worker {worker_index})</h2><p>No active analyses found to process.</p>"
        await send_summary_email(html_content)
        return {"total_analyses": 0, "successful_analyses": 0, "failed_analyses": 0, "analysis_results": []}

    chunk_size = len(all_analyses) // total_workers
    start_index = worker_index * chunk_size
    end_index = start_index + chunk_size if worker_index < total_workers - 1 else len(all_analyses)
    analyses_to_process = all_analyses[start_index:end_index]

    logger.info(f"Worker {worker_index} processing {len(analyses_to_process)} analyses from index {start_index} to {end_index}")

    # Use default filter if none provided
    if filter_conditions is None:
        filter_conditions = [
            {"field": "initiation_date", "op": "eq", "value": target_date}
        ]

    result = await run_partial_tender_analyses(
        analyses=analyses_to_process,
        target_date=target_date,
        top_k=top_k,
        score_threshold=score_threshold,
        filter_conditions=filter_conditions
    )

    # Prepare email content for this worker's chunk
    html_lines = [f"<h2>Tender Analysis Summary for {target_date} (Worker {worker_index})</h2>"]
    html_lines.append(f"<p>Total Analyses Processed by Worker: {result.total_analyses}, Successful: {result.successful_analyses}, Failed: {result.failed_analyses}</p>")
    
    # Aggregate tenders per user/analysis
    analysis_details_list = [] # Changed from user_tender_counts to a list of detailed dicts

    for batch_result in result.analysis_results:
        analysis_id = batch_result.analysis_id
        analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(analysis_id)})
        if not analysis_doc:
            logger.warning(f"Analysis {analysis_id} not found in database.")
            continue
        
        analysis_name = analysis_doc.get("name", "Unnamed Analysis")

        user_id = analysis_doc.get("user_id")
        user_data = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user_data:
            logger.warning(f"User {user_id} not found for analysis {analysis_id}.")
            continue
        user_email = user_data.get("email", "unknown@example.com")

        # Get email recipients using TenderAnalysis model
        tender_analysis = TenderAnalysis(**analysis_doc)
        email_recipient_ids = tender_analysis.get_email_recipients()

        # Fetch filter stats
        initial_ai_filter_stats = None
        if batch_result.initial_ai_filter_id:
            initial_ai_filter_stats = await get_saved_initial_ai_filter_results(batch_result.initial_ai_filter_id)
        
        description_filter_stats = None
        if batch_result.description_filter_id:
            description_filter_stats = await get_saved_description_filter_results(batch_result.description_filter_id)

        tenders_after_initial_filter = initial_ai_filter_stats.get("filtered_tenders_count", "N/A") if initial_ai_filter_stats else "N/A"
        tenders_after_description_filter = description_filter_stats.get("total_filtered", "N/A") if description_filter_stats else "N/A"
        
        # Total processed in this context refers to tenders that made it to analysis_results for this batch
        total_processed_for_analysis = batch_result.total_tenders_analyzed 

        tender_names_list = [
            f"- {tender.tender_metadata.name}" if tender.tender_metadata and tender.tender_metadata.name else "- Unknown Tender"
            for tender in batch_result.analysis_results
        ]
        
        analysis_details_list.append({
            "analysis_name": analysis_name,
            "user_email": user_email,
            "total_processed_for_analysis": total_processed_for_analysis, # Tenders in the final list for this analysis config
            "tenders_after_initial_filter": tenders_after_initial_filter, # Tenders after AI relevance filter
            "tenders_after_description_filter": tenders_after_description_filter, # Tenders after description filter (final count)
            "tender_names_list_str": "<br>".join(tender_names_list) if tender_names_list else "No tenders found for this analysis."
        })
        # Only send email if at least one tender was found with score > 0.6
        qualifying_tenders = [
            tender for tender in batch_result.analysis_results 
            if getattr(tender, "tender_score", 0) > 0.6
        ]
        
        if qualifying_tenders and len(qualifying_tenders) > 0:
            await send_emails_to_recipients(
                recipient_user_ids=email_recipient_ids,
                analysis_name=analysis_name,
                analysis_id=analysis_id,
                tenders=batch_result.analysis_results,  # Send all results, filtering happens in email building
            )
            logger.info(f"Emails sent to {len(email_recipient_ids)} recipients for {analysis_name} - {len(qualifying_tenders)} qualifying tenders found (score > 0.6)")
        else:
            logger.info(f"No emails sent for {analysis_name} - no qualifying tenders found (all scores <= 0.6)")

    html_lines.append("<h3>Detailed Analysis Results (This Worker)</h3>")
    if not analysis_details_list:
        html_lines.append("<p>No analysis details available for this worker.</p>")
    else:
        html_lines.append("<ul>")
        for detail in analysis_details_list:
            html_lines.append(f"<li><strong>Analysis: {detail['analysis_name']}</strong> (User: {detail['user_email']})")
            html_lines.append("<ul>")
            html_lines.append(f"<li>Total Processed (final relevant tenders): {detail['total_processed_for_analysis']}</li>")
            html_lines.append(f"<li>Tenders after Initial AI Filter: {detail['tenders_after_initial_filter']}</li>")
            html_lines.append(f"<li>Tenders after Description Filter: {detail['tenders_after_description_filter']}</li>")
            html_lines.append("<li>Relevant Tenders Found:</li>")
            if detail["tender_names_list_str"] == "No tenders found for this analysis.":
                 html_lines.append(f"<ul><li>{detail['tender_names_list_str']}</li></ul>")
            else:
                 html_lines.append(f"<ul><li>{detail['tender_names_list_str'].replace('<br>', '<br>&nbsp;&nbsp;&nbsp;')}</li></ul>") # Indent list items
            html_lines.append("</ul></li>")
        html_lines.append("</ul>")
        
    html_content = "\n".join(html_lines)
    await send_summary_email(html_content)

    logger.info(f"Worker {worker_index} completed: {result.successful_analyses} successful, {result.failed_analyses} failed.")

    # --- Build lightweight payload to return (avoid huge file data) ---
    simplified_analysis_results = []
    for batch_result in result.analysis_results:
        simplified_tenders = [
            {
                "tender_url": tender.tender_url,
                "name": (tender.tender_metadata.get("name") if isinstance(tender.tender_metadata, dict) else getattr(tender.tender_metadata, "name", None)),
                "score": tender.tender_score,
            }
            for tender in batch_result.analysis_results
        ]
        simplified_batch = {
            "analysis_id": batch_result.analysis_id,
            "total_tenders_analyzed": batch_result.total_tenders_analyzed,
            "query": batch_result.query,
            "tenders": simplified_tenders,
        }
        simplified_analysis_results.append(simplified_batch)

    return {
        "total_analyses": result.total_analyses,
        "successful_analyses": result.successful_analyses,
        "failed_analyses": result.failed_analyses,
        "analysis_results": simplified_analysis_results,
    }

async def main(
    worker_index: int,
    total_workers: int,
    target_date: str = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d"),
    logger=None,
    filter_conditions: Optional[List[Dict[str, Any]]] = None
):
    """Main entry point for the script."""
    if logger is None:
        logger = logging.getLogger("minerva.tasks.analysis_tasks")
        logging_config.setup_logging()

    result = await run_all_tender_analyses_task(
        target_date=target_date,
        worker_index=worker_index,
        total_workers=total_workers,
        filter_conditions=filter_conditions
    )
    logger.info(f"Analysis task completed for worker {worker_index}: {result}")
    return result



async def run_tender_analysis_for_user_and_date(user_id: str, analysis_id: str, target_date: str):
    """
    Run tender analysis for a specific user, analysis_id, and date.
    """
    from minerva.core.models.user import User

    # Fetch user
    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        raise Exception(f"User {user_id} not found")
    user = User(**user_doc)

    # Fetch analysis config
    analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(analysis_id)})
    if not analysis_doc:
        raise Exception(f"Analysis {analysis_id} not found")
    # Prepare filter
    filter_conditions = [
        {"field": "initiation_date", "op": "eq", "value": target_date}
    ]
    if analysis_doc.get("sources"):
        filter_conditions.append({
            "field": "source_type",
            "op": "in",
            "value": analysis_doc["sources"]
        })

    # Prepare criteria
    tender_analysis = TenderAnalysis(**analysis_doc)
    if not tender_analysis.criteria or len(tender_analysis.criteria) == 0:
        tender_analysis.criteria = [AnalysisCriteria(**crit) for crit in DEFAULT_CRITERIA]
    else:
        updated_criteria = []
        for crit in tender_analysis.criteria:
            if crit.weight is None:
                default = next((d for d in DEFAULT_CRITERIA if d["name"].lower() == crit.name.lower()), None)
                crit.weight = default["weight"] if default else 3
            updated_criteria.append(crit)
        tender_analysis.criteria = updated_criteria

    # Call analysis
    result = await analyze_relevant_tenders_with_our_rag(
        analysis_id=analysis_id,
        current_user=user,
        top_k=30,
        score_threshold=0.5,
        filter_conditions=filter_conditions,
        tender_names_index_name="tenders",
        elasticsearch_index_name="tenders",
        embedding_model="text-embedding-3-large",
        rag_index_name="files-rag-23-04-2025",
        criteria_definitions=tender_analysis.criteria
    )
    await assign_order_numbers(ObjectId(analysis_id), user)
    return {
        "status": "Tender analysis completed",
        "result": result,
    }


if __name__ == "__main__":
    import sys
    worker_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    total_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    target_date = sys.argv[3] if len(sys.argv) > 3 else datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d")
    asyncio.run(main(worker_index, total_workers, target_date))