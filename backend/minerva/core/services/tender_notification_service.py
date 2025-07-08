import logging
import os
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from bson import ObjectId

from minerva.core.database.database import db
from minerva.core.utils.notification_utils import send_notification
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from minerva.core.models.user import User
from minerva.core.utils.notification_translations import get_translation
from minerva.core.services.vectorstore.pinecone.query import QueryTool, QueryConfig

logger = logging.getLogger(__name__)

class TenderNotificationService:
    """Service for sending notifications related to tender monitoring updates and outcomes"""
    
    def _construct_platform_url(self, tender_analysis_id: str, tender_result_id: str) -> str:
        """
        Construct URL to view tender on the Minerva platform.
        
        Args:
            tender_analysis_id: The tender analysis ID
            tender_result_id: The tender analysis result ID
            
        Returns:
            Full URL to the tender page on the platform
        """
        # Get base URL from environment variable, fallback to localhost for development
        base_url = os.getenv("FRONTEND_URL", "https://asystent.ai")
        return f"{base_url}/dashboard/tender/{tender_result_id}"
    
    async def get_user_language(self, user_id: str) -> str:
        """
        Get user's preferred language, defaulting to Polish if not found or not set.
        
        Args:
            user_id: The user ID to fetch language preference for
            
        Returns:
            Language code (pl, en, de), defaults to 'pl' if not found
        """
        try:
            user = await User.get_by_id(user_id)
            if user and user.preferred_language:
                return user.preferred_language
            return "pl"  # Default to Polish
        except Exception as e:
            logger.error(f"Error fetching user language for user {user_id}: {str(e)}")
            return "pl"  # Default to Polish on error
    
    async def notify_tender_updates(self, updates_summary: List[Dict]) -> Dict[str, Any]:
        """
        Send notifications to users for tender monitoring updates
        
        Args:
            updates_summary: List of update summaries from TenderMonitoringService
            
        Returns:
        Dict containing notification results
        """
        notification_results = {
            "notifications_sent": 0,
            "failed_notifications": 0,
            "users_notified": set(),
            "errors": []
        }
        
        for update in updates_summary:
            try:
                tender_id = update.get("tender_id")
                if not tender_id:
                    continue
                    
                # Get the tender analysis result to extract analysis_id - only if active
                tender_result = await db.tender_analysis_results.find_one(
                    {"_id": ObjectId(tender_id), "status": "active"}
                )
                
                if not tender_result:
                    logger.warning(f"Active tender analysis result {tender_id} not found for update notification")
                    continue
                    
                # Get users who should be notified for this tender
                users_to_notify = await self._get_users_for_tender_by_id(tender_id)
                
                # Get the actual update data with File objects from the database
                update_id = update.get("update_id")
                if update_id:
                    try:
                        update_data = await db.tender_analysis_updates.find_one(
                            {"_id": ObjectId(update_id)}
                        )
                        if update_data:
                            # Use the actual File objects from the database
                            files_uploaded = update_data.get("updated_files", [])
                            overall_summary = update_data.get("overall_summary", "")
                            file_summaries = update_data.get("file_summaries", [])
                        else:
                            # Fallback to summary data if update not found
                            overall_summary = update.get("overall_summary", "")
                            file_summaries = update.get("file_summaries", [])
                            files_uploaded = []
                            logger.warning(f"Update data {update_id} not found, using summary data")
                    except Exception as e:
                        logger.error(f"Error fetching update data {update_id}: {str(e)}")
                        # Fallback to summary data
                        overall_summary = update.get("overall_summary", "")
                        file_summaries = update.get("file_summaries", [])
                        files_uploaded = []
                else:
                    # Fallback to summary data if no update_id
                    overall_summary = update.get("overall_summary", "")
                    file_summaries = update.get("file_summaries", [])
                    files_uploaded = []
                
                # Extract IDs for platform URL
                tender_analysis_id = str(tender_result["tender_analysis_id"])
                tender_result_id = str(tender_result["_id"])
                
                # Get tender metadata for notification title
                tender_metadata = tender_result.get("tender_metadata", {})
                tender_name = tender_metadata.get("name", "")
                
                # Send notifications to all relevant users
                for user_info in users_to_notify:
                    try:
                        # Get user's preferred language
                        user_language = await self.get_user_language(user_info["user_id"])
                        
                        # Create localized notification title with tender name
                        update_prefix = get_translation(user_language, "update_prefix")  # "Aktualizacja"
                        notification_title = f"{update_prefix}: {tender_name}" if tender_name else get_translation(user_language, "tender_update_title")
                        notification_content = self._create_update_notification_content(
                            overall_summary, file_summaries, files_uploaded, user_language,
                            tender_analysis_id, tender_result_id, tender_name, 
                            tender_metadata.get("organization", ""),
                            tender_result.get("tender_url", "")
                        )
                        
                        await send_notification(
                            user_id=user_info["user_id"],
                            title=notification_title,
                            content=notification_content,
                            notif_type="update",
                            org_id=user_info.get("org_id")
                        )
                        notification_results["notifications_sent"] += 1
                        notification_results["users_notified"].add(user_info["user_id"])
                        
                    except Exception as e:
                        logger.error(f"Failed to send notification to user {user_info['user_id']}: {str(e)}")
                        notification_results["failed_notifications"] += 1
                        notification_results["errors"].append({
                            "user_id": user_info["user_id"],
                            "error": str(e)
                        })
                        
            except Exception as e:
                logger.error(f"Failed to process update for tender {tender_id}: {str(e)}")
                notification_results["errors"].append({
                    "tender_id": tender_id,
                    "error": str(e)
                })
        
        # Convert set to list for JSON serialization
        notification_results["users_notified"] = list(notification_results["users_notified"])
        
        logger.info(f"Tender update notifications: {notification_results['notifications_sent']} sent, "
                   f"{notification_results['failed_notifications']} failed")
        
        return notification_results
    
    async def notify_tender_outcomes(self, outcome_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send notifications to users for completed tenders (historical results)
        
        Args:
            outcome_results: Results from historical tender processing
            
        Returns:
            Dict containing notification results
        """
        notification_results = {
            "notifications_sent": 0,
            "failed_notifications": 0,
            "users_notified": set(),
            "errors": []
        }
        
        try:
            # Check if we have tender analysis result IDs directly (more efficient)
            updated_tender_analysis_ids = outcome_results.get("updates", {}).get("updated_tender_analysis_ids", [])
            
            if updated_tender_analysis_ids:
                # Use the direct IDs approach - more efficient, no URL lookups needed
                await self._notify_outcomes_by_ids(updated_tender_analysis_ids, notification_results)
            else:
                # Fallback to URL-based approach for backward compatibility
                logger.info("No tender analysis IDs provided, falling back to URL-based notification lookup")
                await self._notify_outcomes_by_urls(outcome_results, notification_results)
                    
        except Exception as e:
            logger.error(f"Failed to process tender outcomes: {str(e)}")
            notification_results["errors"].append({
                "general_error": str(e)
            })
        
        # Convert set to list for JSON serialization
        notification_results["users_notified"] = list(notification_results["users_notified"])
        
        logger.info(f"Tender outcome notifications: {notification_results['notifications_sent']} sent, "
                   f"{notification_results['failed_notifications']} failed")
        
        return notification_results
    
    async def _notify_outcomes_by_ids(self, tender_analysis_ids: List[str], notification_results: Dict[str, Any]):
        """
        Notify users about tender outcomes using direct tender analysis result IDs.
        This is more efficient as it avoids URL-based lookups.
        Only considers active TenderAnalysisResult objects.
        """
        logger.info(f"Notifying outcomes for {len(tender_analysis_ids)} tender analysis results by ID")
        
        for tender_id in tender_analysis_ids:
            try:
                # Get the tender analysis result directly - only if active
                tender_result = await db.tender_analysis_results.find_one(
                    {"_id": ObjectId(tender_id), "status": "active"}
                )
                
                if not tender_result:
                    logger.warning(f"Active tender analysis result {tender_id} not found")
                    continue
                
                # Get users who should be notified for this tender
                users_to_notify = await self._get_users_for_tender_by_url(tender_result["tender_url"])
                
                if not users_to_notify:
                    logger.info(f"No users to notify for tender {tender_id}")
                    continue
                
                # Get tender metadata for notification
                tender_metadata = tender_result.get("tender_metadata", {})
                tender_name = tender_metadata.get("name", "")
                organization = tender_metadata.get("organization", "")
                
                # Extract IDs for platform URL
                tender_analysis_id = str(tender_result["tender_analysis_id"])
                tender_result_id = str(tender_result["_id"])
                
                # Attempt to fetch additional outcome metadata from Pinecone using finished_id
                outcome_details: Dict[str, Any] = {}
                finished_id = tender_result.get("finished_id")
                if finished_id:
                    try:
                        query_tool = QueryTool(QueryConfig(index_name="historical-tenders", embedding_model="text-embedding-3-large"))
                        pinecone_result = await query_tool.query_by_id(finished_id)
                        if pinecone_result.get("matches"):
                            outcome_details = pinecone_result["matches"][0].get("metadata", {}) or {}
                    except Exception as e:
                        logger.error(f"Failed to fetch outcome metadata for finished_id {finished_id}: {str(e)}")
                
                # Send notifications to all relevant users
                for user_info in users_to_notify:
                    try:
                        # Get user's preferred language
                        user_language = await self.get_user_language(user_info["user_id"])
                        
                        # Use fallback names if not provided
                        localized_tender_name = tender_name or get_translation(user_language, "unknown_tender")
                        localized_organization = organization or get_translation(user_language, "unknown_organization")
                        
                        # Create localized notification title with tender name
                        outcome_prefix = get_translation(user_language, "outcome_prefix")  # "Wynik"
                        notification_title = f"{outcome_prefix}: {localized_tender_name}"
                        notification_content = self._create_outcome_notification_content(
                            localized_tender_name,
                            localized_organization,
                            user_language,
                            tender_analysis_id,
                            tender_result_id,
                            outcome_details if outcome_details else None
                        )
                        
                        await send_notification(
                            user_id=user_info["user_id"],
                            title=notification_title,
                            content=notification_content,
                            notif_type="outcome",
                            org_id=user_info.get("org_id")
                        )
                        notification_results["notifications_sent"] += 1
                        notification_results["users_notified"].add(user_info["user_id"])
                        
                    except Exception as e:
                        logger.error(f"Failed to send outcome notification to user {user_info['user_id']}: {str(e)}")
                        notification_results["failed_notifications"] += 1
                        notification_results["errors"].append({
                            "user_id": user_info["user_id"],
                            "error": str(e)
                        })
                        
            except Exception as e:
                logger.error(f"Failed to process outcome for tender ID {tender_id}: {str(e)}")
                notification_results["errors"].append({
                    "tender_id": tender_id,
                    "error": str(e)
                })

    async def _notify_outcomes_by_urls(self, outcome_results: Dict[str, Any], notification_results: Dict[str, Any]):
        """
        Notify users about tender outcomes using URL-based lookup (fallback method).
        This is less efficient but maintains backward compatibility.
        Only considers active TenderAnalysisResult objects.
        """
        logger.info("Using URL-based notification lookup for tender outcomes")
        
        # Get updated tender analysis results that now have finished_id
        updated_with_url = outcome_results.get("updates", {}).get("updated_with_url", [])
        updated_without_url = outcome_results.get("updates", {}).get("updated_without_url", [])
        
        # Collect all tender URLs that were updated
        all_updated_urls = set(updated_with_url)
        for update_info in updated_without_url:
            if isinstance(update_info, dict) and "a" in update_info:
                url = update_info["a"].get("id")
                if url:
                    all_updated_urls.add(url)
        
        # Process each completed tender
        for tender_url in all_updated_urls:
            try:
                # Get users who should be notified for this tender URL
                users_to_notify = await self._get_users_for_tender_by_url(tender_url)
                
                if not users_to_notify:
                    logger.info(f"No users to notify for tender URL {tender_url}")
                    continue
                
                # Get tender metadata from any active result with this URL (they should all have the same metadata)
                tender_result = await db.tender_analysis_results.find_one(
                    {"tender_url": tender_url, "status": "active"}
                )
                
                if not tender_result:
                    logger.warning(f"No active tender analysis result found for URL {tender_url} despite having users to notify")
                    continue
                
                # Get tender metadata for notification
                tender_metadata = tender_result.get("tender_metadata", {})
                tender_name = tender_metadata.get("name", "")
                organization = tender_metadata.get("organization", "")
                
                # Extract IDs for platform URL
                tender_analysis_id = str(tender_result["tender_analysis_id"])
                tender_result_id = str(tender_result["_id"])
                
                # Attempt to fetch additional outcome metadata from Pinecone using finished_id
                outcome_details: Dict[str, Any] = {}
                finished_id = tender_result.get("finished_id")
                if finished_id:
                    try:
                        query_tool = QueryTool(QueryConfig(index_name="historical-tenders", embedding_model="text-embedding-3-large"))
                        pinecone_result = await query_tool.query_by_id(finished_id)
                        if pinecone_result.get("matches"):
                            outcome_details = pinecone_result["matches"][0].get("metadata", {}) or {}
                    except Exception as e:
                        logger.error(f"Failed to fetch outcome metadata for finished_id {finished_id}: {str(e)}")
                
                # Send notifications to all relevant users
                for user_info in users_to_notify:
                    try:
                        # Get user's preferred language
                        user_language = await self.get_user_language(user_info["user_id"])
                        
                        # Use fallback names if not provided
                        localized_tender_name = tender_name or get_translation(user_language, "unknown_tender")
                        localized_organization = organization or get_translation(user_language, "unknown_organization")
                        
                        # Create localized notification title with tender name
                        outcome_prefix = get_translation(user_language, "outcome_prefix")  # "Wynik"
                        notification_title = f"{outcome_prefix}: {localized_tender_name}"
                        notification_content = self._create_outcome_notification_content(
                            localized_tender_name,
                            localized_organization,
                            user_language,
                            tender_analysis_id,
                            tender_result_id,
                            outcome_details if outcome_details else None
                        )
                        
                        await send_notification(
                            user_id=user_info["user_id"],
                            title=notification_title,
                            content=notification_content,
                            notif_type="outcome",
                            org_id=user_info.get("org_id")
                        )
                        notification_results["notifications_sent"] += 1
                        notification_results["users_notified"].add(user_info["user_id"])
                        
                    except Exception as e:
                        logger.error(f"Failed to send outcome notification to user {user_info['user_id']}: {str(e)}")
                        notification_results["failed_notifications"] += 1
                        notification_results["errors"].append({
                            "user_id": user_info["user_id"],
                            "error": str(e)
                        })
                        
            except Exception as e:
                logger.error(f"Failed to process outcome for tender {tender_url}: {str(e)}")
                notification_results["errors"].append({
                    "tender_url": tender_url,
                    "error": str(e)
                })
    
    async def _get_users_for_tender_by_id(self, tender_id: str) -> List[Dict[str, Any]]:
        """
        Get all users who should receive notifications for a specific tender by result ID
        
        Args:
            tender_id: The tender analysis result ID
            
        Returns:
            List of user information dictionaries
        """
        try:
            # Get the tender analysis result to extract the URL - only if active
            tender_result = await db.tender_analysis_results.find_one(
                {"_id": ObjectId(tender_id), "status": "active"}
            )
            
            if not tender_result:
                logger.warning(f"Active tender analysis result {tender_id} not found")
                return []
            
            tender_url = tender_result.get("tender_url")
            if not tender_url:
                logger.warning(f"Tender analysis result {tender_id} has no tender_url")
                return []
            
            # Use the URL-based method to find all users monitoring this tender
            return await self._get_users_for_tender_by_url(tender_url)
            
        except Exception as e:
            logger.error(f"Error getting users for tender {tender_id}: {str(e)}")
            return []

    async def _get_users_for_tender_by_url(self, tender_url: str) -> List[Dict[str, Any]]:
        """
        Get all users who should receive notifications for a specific tender by URL.
        
        IMPORTANT: The same tender can have multiple TenderAnalysisResult instances - 
        one for each different client who is monitoring that tender. This method
        finds ALL such instances and collects users from ALL associated TenderAnalysis
        configurations to ensure every stakeholder gets notified.
        
        Only considers active TenderAnalysisResult objects (status: "active") and
        active TenderAnalysis objects (active: true).
        
        Args:
            tender_url: The tender URL to search for
            
        Returns:
            List of unique user information dictionaries (deduplicated across all configurations)
        """
        try:
            # Find ALL active tender analysis results with this URL
            tender_results_cursor = db.tender_analysis_results.find(
                {"tender_url": tender_url, "status": "active"}
            )
            tender_results = await tender_results_cursor.to_list(length=None)
            
            if not tender_results:
                logger.warning(f"No active tender analysis results found for URL {tender_url}")
                return []
            
            logger.info(f"Found {len(tender_results)} active tender analysis results for URL {tender_url}")
            
            # Collect all unique tender_analysis_ids
            analysis_ids = list(set(result["tender_analysis_id"] for result in tender_results))
            
            # Get all associated active tender analysis configurations
            tender_analyses_cursor = db.tender_analysis.find(
                {"_id": {"$in": analysis_ids}, "active": True}
            )
            tender_analyses = await tender_analyses_cursor.to_list(length=None)
            
            if not tender_analyses:
                logger.warning(f"No active tender analysis configurations found for URL {tender_url}")
                return []
            
            logger.info(f"Found {len(tender_analyses)} active tender analysis configurations for URL {tender_url}")
            
            # Collect all unique users from all configurations
            all_users = {}  # Use dict to avoid duplicates, key = user_id
            
            for tender_analysis in tender_analyses:
                # Add the owner
                owner_id = str(tender_analysis.get("user_id"))
                if owner_id and owner_id != "None":
                    all_users[owner_id] = {
                        "user_id": owner_id,
                        "org_id": tender_analysis.get("org_id"),
                        "role": "owner",
                        "analysis_name": tender_analysis.get("name", "")
                    }
                
                # Add assigned users
                assigned_users = tender_analysis.get("assigned_users", [])
                for user_id in assigned_users:
                    user_id_str = str(user_id)
                    if user_id_str and user_id_str != "None":
                        all_users[user_id_str] = {
                            "user_id": user_id_str,
                            "org_id": tender_analysis.get("org_id"),
                            "role": "assigned",
                            "analysis_name": tender_analysis.get("name", "")
                        }
                
                # Add email recipients
                email_recipients = tender_analysis.get("email_recipients", [])
                for user_id in email_recipients:
                    user_id_str = str(user_id)
                    if user_id_str and user_id_str != "None":
                        # Only add if not already present (to preserve the primary role)
                        if user_id_str not in all_users:
                            all_users[user_id_str] = {
                                "user_id": user_id_str,
                                "org_id": tender_analysis.get("org_id"),
                                "role": "email_recipient",
                                "analysis_name": tender_analysis.get("name", "")
                            }
            
            users_to_notify = list(all_users.values())
            logger.info(f"Found {len(users_to_notify)} unique users to notify for active tender URL {tender_url}")
            
            return users_to_notify
            
        except Exception as e:
            logger.error(f"Error getting users for tender URL {tender_url}: {str(e)}")
            return []
    
    def _create_update_notification_content(
        self, 
        overall_summary: str, 
        file_summaries: List[Dict], 
        files_uploaded: List[Dict],  # Changed to List[Dict] to accept File objects
        user_language: str,
        tender_analysis_id: str,
        tender_result_id: str,
        tender_name: str = "",
        organization: str = "",
        original_tender_url: str = ""
    ) -> str:
        """Create HTML content for tender update notification"""
        
        content_parts = [
            "<div style='font-family: \"Satoshi\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif; line-height: 1.6; color: #534B46; max-width: 600px; border-radius: 8px;'>"
        ]
        
        # Tender details header
        # if tender_name or organization:
        #     content_parts.append("<div style='margin-bottom: 20px; padding: 20px; background-color:rgba(255, 255, 255, 0.25); border-radius: 8px;'>")
            
        #     if tender_name:
        #         tender_label = get_translation(user_language, "tender_label")
        #         content_parts.append("<div style='margin-bottom: 12px;'>")
        #         content_parts.append(f"<strong style='color: #696255; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 4px;'>{tender_label}</strong>")
        #         content_parts.append(f"<span style='color: #4E3B31; font-size: 14px; font-weight: 600;'>{tender_name}</span>")
        #         content_parts.append("</div>")
            
        #     if organization:
        #         organization_label = get_translation(user_language, "organization_label")
        #         content_parts.append("<div style='margin-bottom: 0;'>")
        #         content_parts.append(f"<strong style='color: #696255; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 4px;'>{organization_label}</strong>")
        #         content_parts.append(f"<span style='color: #4E3B31; font-size: 14px; font-weight: 600;'>{organization}</span>")
        #         content_parts.append("</div>")
            
        #     content_parts.append("</div>")
        # else:
        #     # Fallback to generic update status if no tender details available
        #     tender_updated = get_translation(user_language, "tender_updated")
        #     content_parts.append("<div style='margin-bottom: 20px; padding: 16px; background-color:rgba(255, 255, 255, 0.25); border-left: 2px solid #4E3B31; border-radius: 8px;'>")
        #     content_parts.append(f"<p style='margin: 0; color: #4E3B31; font-weight: 600; font-size: 12px;'>{tender_updated}</p>")
        #     content_parts.append("</div>")
        
        if overall_summary:
            content_parts.append("<div style='margin-bottom: 20px; padding: 20px; background-color:rgba(255, 255, 255, 0.25); border-radius: 8px;'>")
            content_parts.append(f"<strong style='color: #696255; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 8px;'>{get_translation(user_language, 'summary_changes')}</strong>")
            content_parts.append(f"<p style='margin: 0; color: #4E3B31; font-size: 14px; font-weight: 400;'>{overall_summary}</p>")
            content_parts.append("</div>")
        
        if files_uploaded:
            new_files_label = get_translation(user_language, "new_files")
            download_file_label = get_translation(user_language, "download_file")
            content_parts.append("<div style='margin-bottom: 20px; padding: 20px; background-color:rgba(255, 255, 255. 0.2); border-radius: 8px;'>")
            content_parts.append(f"<strong style='color: #696255; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 8px;'>{new_files_label} ({len(files_uploaded)})</strong>")
            content_parts.append("<div style='margin: 0; color: #4E3B31;'>")
            for file_obj in files_uploaded:
                # Extract filename and download URL from file object
                filename = file_obj.get("filename", "Unknown file")
                download_url = file_obj.get("blob_url") or file_obj.get("url")
                
                content_parts.append(f"<div style='margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;'>")
                content_parts.append(f"<span style='font-size: 14px; flex: 1;'>{filename}</span>")
                
                if download_url:
                    content_parts.append(f"<a href='{download_url}' target='_blank' style='margin-left: 12px; color: #4E3B31; text-decoration: none; font-size: 12px; font-weight: 600; border: 1px solid #4E3B31; padding: 4px 8px; border-radius: 4px; transition: all 0.2s ease;' onmouseover='this.style.backgroundColor=\"#4E3B31\"; this.style.color=\"#F5EFE4\";' onmouseout='this.style.backgroundColor=\"transparent\"; this.style.color=\"#4E3B31\";'>{download_file_label}</a>")
                else:
                    # Fallback if no download URL available
                    not_available_text = get_translation(user_language, 'not_available')
                    content_parts.append(f"<span style='margin-left: 12px; color: #696255; font-size: 12px; font-style: italic;'>{get_translation(user_language, 'download_file')} {not_available_text}</span>")
                
                content_parts.append("</div>")
            content_parts.append("</div>")
            content_parts.append("</div>")
        
        if file_summaries and len(file_summaries) > 0:
            content_parts.append("<div style='margin-bottom: 20px; padding: 20px; background-color:rgba(255, 255, 255. 0.2); border-radius: 8px;'>")
            content_parts.append(f"<strong style='color: #696255; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 12px;'>{get_translation(user_language, 'file_details')}</strong>")
            for i, file_summary in enumerate(file_summaries):
                filename = file_summary.get("filename", "Unknown file")
                summary = file_summary.get("summary", "No summary available")
                margin_style = "margin-bottom: 16px;" if i < len(file_summaries) - 1 else "margin-bottom: 0;"
                content_parts.append(f"<div style='{margin_style}'>")
                content_parts.append(f"<strong style='color: #4E3B31; font-size: 14px; font-weight: 600; display: block; margin-bottom: 4px;'>{filename}</strong>")
                content_parts.append(f"<span style='color: #696255; font-size: 14px;'>{summary}</span>")
                content_parts.append(f"</div>")
            content_parts.append("</div>")
        
        if not content_parts or len(content_parts) == 1:  # Only the opening div
            content_parts.append("<div style='margin-bottom: 20px; padding: 20px; background-color:rgba(255, 255, 255. 0.2); border-radius: 8px;'>")
            content_parts.append(f"<p style='margin: 0; color: #696255; font-size: 14px;'>{get_translation(user_language, 'update_detected')}</p>")
            content_parts.append("</div>")
    
        
        # Add platform link with button styling using brand colors
        platform_url = self._construct_platform_url(tender_analysis_id, tender_result_id)
        view_update_details = get_translation(user_language, 'view_update_details')
        content_parts.append("<div style='margin-top: 24px; text-align: center;'>")
        content_parts.append(
            f"<a href='{platform_url}' target='_blank' style='"
            "display: inline-block; "
            "background-color: #4E3B31; "
            "color: #F5EFE4; "
            "padding: 12px 24px; "
            "text-decoration: none; "
            "border-radius: 8px; "
            "font-weight: 600; "
            "font-size: 14px; "
            "text-transform: uppercase; "
            "letter-spacing: 0.5px; "
            "transition: all 0.2s ease; "
            "border: 2px solid #4E3B31;"
            "' onmouseover='this.style.backgroundColor=\"#B79C8A\"; this.style.borderColor=\"#B79C8A\"; this.style.color=\"#534B46\";' "
            "onmouseout='this.style.backgroundColor=\"#4E3B31\"; this.style.borderColor=\"#4E3B31\"; this.style.color=\"#F5EFE4\";'>"
            f"{view_update_details}</a>"
        )
        # Add original tender link if available
        if original_tender_url:
            view_original_tender = get_translation(user_language, 'view_original_tender')
            content_parts.append("<div style='margin-top: 20px; padding: 16px; background-color:rgba(255, 255, 255, 0.15); border-radius: 8px; text-align: center;'>")
            content_parts.append(f"<p style='margin: 0 0 8px 0; color: #696255; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;'>{get_translation(user_language, 'original_tender_link')}</p>")
            content_parts.append(f"<a href='{original_tender_url}' target='_blank' style='color: #4E3B31; text-decoration: none; font-size: 14px; font-weight: 600; border-bottom: 1px solid #4E3B31; transition: all 0.2s ease;' onmouseover='this.style.color=\"#B79C8A\"; this.style.borderBottomColor=\"#B79C8A\";' onmouseout='this.style.color=\"#4E3B31\"; this.style.borderBottomColor=\"#4E3B31\";'>{view_original_tender}</a>")
            content_parts.append("</div>")
        content_parts.append("</div>")
        
        content_parts.append("</div>")
        
        return "".join(content_parts)
    
    def _create_outcome_notification_content(
        self, 
        tender_name: str, 
        organization: str,
        user_language: str,
        tender_analysis_id: str,
        tender_result_id: str,
        outcome_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create HTML content for tender outcome notification with optional extended details"""
        
        tender_label = get_translation(user_language, "tender_label")
        organization_label = get_translation(user_language, "organization_label")
        tender_completed = get_translation(user_language, "tender_completed")
        view_tender_details = get_translation(user_language, "view_tender_details")
        
        # Construct platform URL
        platform_url = self._construct_platform_url(tender_analysis_id, tender_result_id)
        
        # Start main container
        content_parts: List[str] = [
            "<div style='font-family: \"Satoshi\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif; line-height: 1.6; color: #534B46; max-width: 600px; border-radius: 8px;'>"
        ]
        
        # Combined outcome details section
        if outcome_details or organization:
            content_parts.append("<div style='margin-bottom: 20px; padding: 20px; background-color:rgba(255, 255, 255, 0.25); border-radius: 8px;'>")
            
            # Add contracting authority first if available
            if organization:
                contracting_authority_label = get_translation(user_language, "contracting_authority")
                content_parts.append(f"<p style='margin: 0 0 8px 0; color: #4E3B31; font-size: 14px;'><strong>{contracting_authority_label}:</strong> {organization}</p>")
            
            # Add other outcome details
            if outcome_details:
                field_map = {
                    get_translation(user_language, "status_label"): "completion_status",
                    get_translation(user_language, "winner_label"): "winner_name",
                    get_translation(user_language, "winner_location_label"): "winner_location",
                    get_translation(user_language, "winning_price_label"): "winning_price",
                    get_translation(user_language, "total_offers_label"): "total_offers",
                    get_translation(user_language, "lowest_price_label"): "lowest_price",
                    get_translation(user_language, "highest_price_label"): "highest_price",
                    get_translation(user_language, "contract_value_label"): "contract_value",
                }
                for label, key in field_map.items():
                    value = outcome_details.get(key)
                    if value:
                        content_parts.append(f"<p style='margin: 0 0 8px 0; color: #4E3B31; font-size: 14px;'><strong>{label}:</strong> {value}</p>")
            
            content_parts.append("</div>")
        
        # Action button
        content_parts.extend([
            "<div style='margin-top: 24px; text-align: center;'>",
            f"<a href='{platform_url}' target='_blank' style='display: inline-block; background-color: #4E3B31; color: #F5EFE4; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; letter-spacing: 0.5px; transition: all 0.2s ease; border: 2px solid #4E3B31;' onmouseover='this.style.backgroundColor=\"#B79C8A\"; this.style.borderColor=\"#B79C8A\"; this.style.color=\"#534B46\";' onmouseout='this.style.backgroundColor=\"#4E3B31\"; this.style.borderColor=\"#4E3B31\"; this.style.color=\"#F5EFE4\";'>{view_tender_details}</a>",
            "</div>"
        ])
        
        # Close container
        content_parts.append("</div>")
        
        return "".join(content_parts)

# Convenience functions for use in other services
async def notify_tender_updates(updates_summary: List[Dict]) -> Dict[str, Any]:
    """Convenience function to send tender update notifications"""
    service = TenderNotificationService()
    return await service.notify_tender_updates(updates_summary)

async def notify_tender_outcomes(outcome_results: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to send tender outcome notifications"""
    service = TenderNotificationService()
    return await service.notify_tender_outcomes(outcome_results) 