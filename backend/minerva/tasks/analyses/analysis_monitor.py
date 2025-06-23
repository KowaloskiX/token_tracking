import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from minerva.tasks.analyses.analysis_queue import AnalysisQueue
from minerva.core.database.database import db
from bson import ObjectId
import pytz

logger = logging.getLogger(__name__)

class AnalysisMonitor:
    def __init__(self):
        self.queue = AnalysisQueue(os.getenv("REDIS_URL", "redis://localhost:6379/1"))
        self.processed_analyses = set()
        self.last_check = datetime.utcnow().isoformat()
        self.daily_summary_sent = False
    
    async def monitor_completions(self):
        """Monitor for completed analyses and send emails"""
        logger.info("Starting analysis completion monitor")
        
        while True:
            try:
                # Check for newly completed analyses
                completed_tasks = await self.queue.get_completed_tasks_since(self.last_check)
                
                for task_id, task_data in completed_tasks.items():
                    if task_id not in self.processed_analyses:
                        await self._handle_completed_analysis(task_data)
                        self.processed_analyses.add(task_id)
                
                # Update last check time
                self.last_check = datetime.utcnow().isoformat()
                
                # Send daily summary if it's time
                await self._check_and_send_daily_summary()
                
                # Log queue stats periodically
                await self._log_queue_stats()
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in analysis monitor: {e}", exc_info=True)
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _handle_completed_analysis(self, task_data: dict):
        """Log completed analysis (emails disabled - only daily summary)"""
        try:
            # Parse analysis doc from string
            analysis_doc_str = task_data.get("analysis_doc", "{}")
            analysis_doc = json.loads(analysis_doc_str)
            analysis_id = analysis_doc["_id"]
            analysis_name = analysis_doc.get("name", "Unnamed Analysis")
            
            logger.info(f"Analysis completed: {analysis_name} (ID: {analysis_id})")
            
            # Get analysis results count for logging
            results_count = await db.tender_analysis_results.count_documents({
                "tender_analysis_id": ObjectId(analysis_id)
            })
            
            logger.info(f"Analysis {analysis_name} completed with {results_count} results")
            
            # Individual emails disabled - only daily summary will be sent
                
        except Exception as e:
            logger.error(f"Error handling completed analysis: {e}", exc_info=True)
    
    async def _check_and_send_daily_summary(self):
        """Check if all analyses are done and send daily summary"""
        try:
            current_time = datetime.now(pytz.timezone("Europe/Warsaw"))
            current_hour = current_time.hour
            
            # Send summary at 23:00 if there are completed analyses and we haven't sent today's summary
            if current_hour == 23 and not self.daily_summary_sent:
                stats = await self.queue.get_queue_stats()
                if stats.get("completed", 0) > 0:
                    await self._send_detailed_daily_summary()
                    self.daily_summary_sent = True
            
            # Reset flag at midnight
            if current_hour == 0:
                self.daily_summary_sent = False
                
        except Exception as e:
            logger.error(f"Error checking daily summary: {e}")
    
    async def _send_detailed_daily_summary(self):
        """Send detailed daily summary email with comprehensive analysis information"""
        try:
            import resend
            
            target_date = datetime.now(pytz.timezone("Europe/Warsaw")).strftime("%Y-%m-%d")
            
            # Get all completed tasks for today
            completed_tasks = await self.queue.get_all_completed_tasks()
            
            if not completed_tasks:
                logger.info("No completed analyses found for daily summary")
                return
            
            # Build detailed analysis information
            analysis_details = []
            total_final_tenders = 0
            
            for task_id, task_data in completed_tasks.items():
                try:
                    # Parse analysis doc
                    analysis_doc_str = task_data.get("analysis_doc", "{}")
                    analysis_doc = json.loads(analysis_doc_str)
                    analysis_id = analysis_doc["_id"]
                    
                    # Get user information
                    user_doc = await db.users.find_one({"_id": ObjectId(analysis_doc["user_id"])})
                    user_email = user_doc.get("email", "Unknown") if user_doc else "Unknown"
                    user_name = user_doc.get("name", "Unknown") if user_doc else "Unknown"
                    
                    # Get analysis statistics from task data
                    analysis_stats = task_data.get("analysis_stats", {})
                    
                    # Get final results from database
                    final_results = await db.tender_analysis_results.find({
                        "tender_analysis_id": ObjectId(analysis_id)
                    }).to_list(None)
                    
                    # Get tender names from final results
                    tender_names = []
                    for result in final_results:
                        tender_name = "Unknown"
                        if result.get("tender_metadata") and result["tender_metadata"].get("name"):
                            tender_name = result["tender_metadata"]["name"]
                        elif result.get("tender_description"):
                            # Use first 50 chars of description if no name
                            tender_name = result["tender_description"][:50] + "..."
                        tender_names.append(tender_name)
                    
                    analysis_detail = {
                        "analysis_name": analysis_doc.get("name", "Unnamed Analysis"),
                        "user_email": user_email,
                        "user_name": user_name,
                        "total_searched": analysis_stats.get("total_searched", 0),
                        "after_initial_filtering": analysis_stats.get("after_initial_filtering", 0),
                        "after_pipeline_processing": analysis_stats.get("after_pipeline_processing", 0),
                        "final_results": len(final_results),
                        "tender_names": tender_names,
                        "search_phrase": analysis_doc.get("search_phrase", "Not specified"),
                        "sources": analysis_doc.get("sources", [])
                    }
                    
                    analysis_details.append(analysis_detail)
                    total_final_tenders += len(final_results)
                    
                except Exception as e:
                    logger.error(f"Error processing analysis details for task {task_id}: {e}")
                    continue
            
            if not analysis_details:
                logger.warning("No valid analysis details found for daily summary")
                return
            
            # Create detailed HTML email
            html_content = self._create_detailed_html_email(target_date, analysis_details, total_final_tenders)
            
            email_data = {
                "from": "piotr@asystent.ai",
                "to": "peter@yepp.ai",
                "subject": f"Detailed Analysis Summary for {target_date} - {len(analysis_details)} analyses, {total_final_tenders} total tenders",
                "html": html_content
            }
            
            resend.api_key = os.getenv("RESEND_API_KEY")
            if resend.api_key:
                resend.Emails.send(email_data)
                logger.info(f"Detailed daily summary email sent successfully for {len(analysis_details)} analyses")
            else:
                logger.warning("RESEND_API_KEY not set, skipping summary email")
                
        except Exception as e:
            logger.error(f"Error sending detailed daily summary: {e}", exc_info=True)
    
    def _create_detailed_html_email(self, target_date: str, analysis_details: list, total_final_tenders: int) -> str:
        """Create detailed HTML email content"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .analysis {{ border: 1px solid #dee2e6; margin-bottom: 20px; border-radius: 5px; }}
                .analysis-header {{ background-color: #e9ecef; padding: 15px; font-weight: bold; }}
                .analysis-content {{ padding: 15px; }}
                .stats-table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                .stats-table th, .stats-table td {{ border: 1px solid #dee2e6; padding: 8px; text-align: left; }}
                .stats-table th {{ background-color: #f8f9fa; }}
                .tender-list {{ margin: 10px 0; }}
                .tender-item {{ margin: 5px 0; padding: 5px; background-color: #f8f9fa; border-radius: 3px; }}
                .summary {{ background-color: #d4edda; padding: 15px; border-radius: 5px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Detailed Analysis Summary for {target_date}</h1>
                <p><strong>Total Analyses:</strong> {len(analysis_details)}</p>
                <p><strong>Total Final Tenders:</strong> {total_final_tenders}</p>
            </div>
        """
        
        for analysis in analysis_details:
            html += f"""
            <div class="analysis">
                <div class="analysis-header">
                    {analysis['analysis_name']} - {analysis['user_name']} ({analysis['user_email']})
                </div>
                <div class="analysis-content">
                    <p><strong>Search Phrase:</strong> {analysis['search_phrase']}</p>
                    <p><strong>Sources:</strong> {', '.join(analysis['sources']) if analysis['sources'] else 'All sources'}</p>
                    
                    <table class="stats-table">
                        <tr>
                            <th>Stage</th>
                            <th>Count</th>
                            <th>Description</th>
                        </tr>
                        <tr>
                            <td>Initial Search</td>
                            <td>{analysis['total_searched']}</td>
                            <td>Total tenders found in search</td>
                        </tr>
                        <tr>
                            <td>After AI Filtering</td>
                            <td>{analysis['after_initial_filtering']}</td>
                            <td>Tenders that passed initial AI relevance filtering</td>
                        </tr>
                        <tr>
                            <td>After Pipeline Processing</td>
                            <td>{analysis['after_pipeline_processing']}</td>
                            <td>Tenders successfully processed (file extraction + criteria analysis)</td>
                        </tr>
                        <tr style="background-color: #d4edda;">
                            <td><strong>Final Results</strong></td>
                            <td><strong>{analysis['final_results']}</strong></td>
                            <td><strong>Tenders that passed description filtering (final output)</strong></td>
                        </tr>
                    </table>
                    
                    <h4>Final Tender Names ({analysis['final_results']} tenders):</h4>
                    <div class="tender-list">
            """
            
            if analysis['tender_names']:
                for i, tender_name in enumerate(analysis['tender_names'], 1):
                    html += f'<div class="tender-item">{i}. {tender_name}</div>'
            else:
                html += '<div class="tender-item">No tenders in final results</div>'
            
            html += """
                    </div>
                </div>
            </div>
            """
        
        html += f"""
            <div class="summary">
                <h3>Summary</h3>
                <p>Successfully completed {len(analysis_details)} analyses on {target_date}</p>
                <p>Total tenders delivered to users: <strong>{total_final_tenders}</strong></p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    async def _log_queue_stats(self):
        """Log queue statistics periodically"""
        try:
            current_minute = datetime.now().minute
            if current_minute % 15 == 0:  # Log every 15 minutes
                stats = await self.queue.get_queue_stats()
                logger.info(f"Queue stats: {stats}")
        except Exception as e:
            logger.error(f"Error logging queue stats: {e}")

async def main():
    """Main entry point for the monitor"""
    monitor = AnalysisMonitor()
    await monitor.monitor_completions()

if __name__ == "__main__":
    asyncio.run(main()) 