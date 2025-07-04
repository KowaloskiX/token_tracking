from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from bson import ObjectId
import logging

from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.core.services.tender_notification_service import TenderNotificationService
from minerva.core.utils.notification_utils import send_notification
from minerva.core.utils.notification_translations import get_translation

router = APIRouter(prefix="/test", tags=["test-notifications"])
logger = logging.getLogger(__name__)

@router.post("/send-example-tender-notification")
async def send_example_tender_notification(
    tender_analysis_id: str = Query(..., description="Tender analysis ID (e.g., 683ea8188b55c8a9fc2616f5)"),
    tender_result_id: str = Query(..., description="Tender result ID (e.g., 68646bcc43d9ab005d07fbf7)"),
    notification_type: str = Query(default="outcome", description="Type of notification: 'update' or 'outcome'"),
    user_language: Optional[str] = Query(default=None, description="Override user language (pl, en, de)"),
    current_user: User = Depends(get_current_user)
):
    """
    Send an example tender notification to the current user for testing purposes.
    
    This endpoint is useful for testing how notifications render in different languages
    and seeing the actual content that users receive.
    """
    try:
        # Initialize the notification service
        service = TenderNotificationService()
        
        # Get the tender analysis result
        tender_result = await db.tender_analysis_results.find_one(
            {"_id": ObjectId(tender_result_id)}
        )
        
        if not tender_result:
            raise HTTPException(status_code=404, detail=f"Tender result {tender_result_id} not found")
        
        # Verify the analysis ID matches
        if str(tender_result["tender_analysis_id"]) != tender_analysis_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Tender analysis ID mismatch. Expected {tender_analysis_id}, got {tender_result['tender_analysis_id']}"
            )
        
        # Get user's language preference (or use override)
        if user_language:
            user_lang = user_language
        else:
            user_lang = await service.get_user_language(str(current_user.id))
        
        # Get tender metadata
        tender_metadata = tender_result.get("tender_metadata", {})
        tender_name = tender_metadata.get("name", get_translation(user_lang, "unknown_tender"))
        organization = tender_metadata.get("organization", get_translation(user_lang, "unknown_organization"))
        tender_url = tender_result.get("tender_url", "")
        
        # Create notification based on type
        if notification_type == "update":
            # Create example update notification with tender name
            update_prefix = get_translation(user_lang, "update_prefix")
            notification_title = f"{update_prefix}: {tender_name}" if tender_name else get_translation(user_lang, "tender_update_title")
            
            # Create example content based on user language
            if user_lang == "en":
                overall_summary = "Example summary of tender changes. New documents added and technical specification updated."
                file_summaries = [
                    {"filename": "technical_specification_v2.pdf", "summary": "Updated technical requirements and added new device parameters."},
                    {"filename": "offer_form.doc", "summary": "Fixed errors in the form and added new fields to fill."}
                ]
                files_uploaded = [
                    {"filename": "additional_documents.zip", "blob_url": "https://example.com/files/additional_documents.zip", "url": "https://example.com/files/additional_documents.zip"},
                    {"filename": "annex_1.pdf", "blob_url": "https://example.com/files/annex_1.pdf", "url": "https://example.com/files/annex_1.pdf"},
                    {"filename": "clarifications.pdf", "blob_url": "https://example.com/files/clarifications.pdf", "url": "https://example.com/files/clarifications.pdf"}
                ]
            elif user_lang == "de":
                overall_summary = "Beispielzusammenfassung der Ausschreibungsänderungen. Neue Dokumente hinzugefügt und technische Spezifikation aktualisiert."
                file_summaries = [
                    {"filename": "technische_spezifikation_v2.pdf", "summary": "Technische Anforderungen aktualisiert und neue Geräteparameter hinzugefügt."},
                    {"filename": "angebotsformular.doc", "summary": "Fehler im Formular behoben und neue Felder zum Ausfüllen hinzugefügt."}
                ]
                files_uploaded = [
                    {"filename": "zusaetzliche_dokumente.zip", "blob_url": "https://example.com/files/zusaetzliche_dokumente.zip", "url": "https://example.com/files/zusaetzliche_dokumente.zip"},
                    {"filename": "anhang_1.pdf", "blob_url": "https://example.com/files/anhang_1.pdf", "url": "https://example.com/files/anhang_1.pdf"},
                    {"filename": "klaerungen.pdf", "blob_url": "https://example.com/files/klaerungen.pdf", "url": "https://example.com/files/klaerungen.pdf"}
                ]
            else:  # Default to Polish
                overall_summary = "Przykładowe podsumowanie zmian w przetargu. Dodano nowe dokumenty i zaktualizowano specyfikację techniczną."
                file_summaries = [
                    {"filename": "specyfikacja_techniczna_v2.pdf", "summary": "Zaktualizowano wymagania techniczne i dodano nowe parametry urządzeń."},
                    {"filename": "formularz_oferty.doc", "summary": "Poprawiono błędy w formularzu i dodano nowe pola do wypełnienia."}
                ]
                files_uploaded = [
                    {"filename": "dokumenty_dodatkowe.zip", "blob_url": "https://example.com/files/dokumenty_dodatkowe.zip", "url": "https://example.com/files/dokumenty_dodatkowe.zip"},
                    {"filename": "aneks_nr_1.pdf", "blob_url": "https://example.com/files/aneks_nr_1.pdf", "url": "https://example.com/files/aneks_nr_1.pdf"},
                    {"filename": "wyjaśnienia.pdf", "blob_url": "https://example.com/files/wyjaśnienia.pdf", "url": "https://example.com/files/wyjaśnienia.pdf"}
                ]
            
            notification_content = service._create_update_notification_content(
                overall_summary=overall_summary,
                file_summaries=file_summaries,
                files_uploaded=files_uploaded,
                user_language=user_lang,
                tender_analysis_id=tender_analysis_id,
                tender_result_id=tender_result_id,
                tender_name=tender_name,
                organization=organization,
                original_tender_url=tender_url
            )
        elif notification_type == "outcome":
            # Create example outcome notification with tender name
            outcome_prefix = get_translation(user_lang, "outcome_prefix")
            notification_title = f"{outcome_prefix}: {tender_name}"
            # Example extended outcome details
            outcome_details = {
                "completion_status": get_translation(user_lang, "tender_completed"),
                "winner_name": "Example Winner Sp. z o.o.",
                "winner_location": "Warszawa, PL",
                "winning_price": "1 500 000 PLN",
                "total_offers": 5,
                "lowest_price": "1 350 000 PLN",
                "highest_price": "1 950 000 PLN",
                "contract_value": "1 500 000 PLN"
            }
            notification_content = service._create_outcome_notification_content(
                tender_name=tender_name,
                organization=organization,
                user_language=user_lang,
                tender_analysis_id=tender_analysis_id,
                tender_result_id=tender_result_id,
                outcome_details=outcome_details
            )
        else:
            raise HTTPException(status_code=400, detail="notification_type must be 'update' or 'outcome'")
        
        # Send the notification
        await send_notification(
            user_id=str(current_user.id),
            title=f"{notification_title}",
            content=notification_content,
            notif_type=notification_type,  # Use "update" or "outcome" directly
            org_id=current_user.org_id
        )
        
        return {
            "success": True,
            "message": f"Example {notification_type} notification sent successfully",
            "tender_analysis_id": tender_analysis_id,
            "tender_result_id": tender_result_id,
            "notification_type": notification_type,
            "language": user_lang,
            "tender_name": tender_name,
            "organization": organization,
            "platform_url": service._construct_platform_url(tender_analysis_id, tender_result_id)
        }
        
    except Exception as e:
        logger.error(f"Failed to send example notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")

@router.get("/preview-tender-notification")
async def preview_tender_notification(
    tender_analysis_id: str = Query(..., description="Tender analysis ID (e.g., 683ea8188b55c8a9fc2616f5)"),
    tender_result_id: str = Query(..., description="Tender result ID (e.g., 68646bcc43d9ab005d07fbf7)"),
    notification_type: str = Query(default="outcome", description="Type of notification: 'update' or 'outcome'"),
    user_language: Optional[str] = Query(default="pl", description="Language (pl, en, de)"),
    current_user: User = Depends(get_current_user)
):
    """
    Preview the HTML content of a tender notification without sending it.
    """
    try:
        # Initialize the notification service
        service = TenderNotificationService()
        
        # Get the tender analysis result
        tender_result = await db.tender_analysis_results.find_one(
            {"_id": ObjectId(tender_result_id)}
        )
        
        if not tender_result:
            raise HTTPException(status_code=404, detail=f"Tender result {tender_result_id} not found")
        
        # Verify the analysis ID matches
        if str(tender_result["tender_analysis_id"]) != tender_analysis_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Tender analysis ID mismatch. Expected {tender_analysis_id}, got {tender_result['tender_analysis_id']}"
            )
        
        # Get tender metadata
        tender_metadata = tender_result.get("tender_metadata", {})
        tender_name = tender_metadata.get("name", get_translation(user_language, "unknown_tender"))
        organization = tender_metadata.get("organization", get_translation(user_language, "unknown_organization"))
        tender_url = tender_result.get("tender_url", "")
        
        # Create notification content based on type
        if notification_type == "update":
            update_prefix = get_translation(user_language, "update_prefix")
            notification_title = f"{update_prefix}: {tender_name}" if tender_name else get_translation(user_language, "tender_update_title")
            
            # Create example content based on user language
            if user_language == "en":
                overall_summary = "Example summary of tender changes. New documents added and technical specification updated."
                file_summaries = [
                    {"filename": "technical_specification_v2.pdf", "summary": "Updated technical requirements and added new device parameters."},
                    {"filename": "offer_form.doc", "summary": "Fixed errors in the form and added new fields to fill."}
                ]
                files_uploaded = [
                    {"filename": "additional_documents.zip", "blob_url": "https://example.com/files/additional_documents.zip", "url": "https://example.com/files/additional_documents.zip"},
                    {"filename": "annex_1.pdf", "blob_url": "https://example.com/files/annex_1.pdf", "url": "https://example.com/files/annex_1.pdf"},
                    {"filename": "clarifications.pdf", "blob_url": "https://example.com/files/clarifications.pdf", "url": "https://example.com/files/clarifications.pdf"}
                ]
            elif user_language == "de":
                overall_summary = "Beispielzusammenfassung der Ausschreibungsänderungen. Neue Dokumente hinzugefügt und technische Spezifikation aktualisiert."
                file_summaries = [
                    {"filename": "technische_spezifikation_v2.pdf", "summary": "Technische Anforderungen aktualisiert und neue Geräteparameter hinzugefügt."},
                    {"filename": "angebotsformular.doc", "summary": "Fehler im Formular behoben und neue Felder zum Ausfüllen hinzugefügt."}
                ]
                files_uploaded = [
                    {"filename": "zusaetzliche_dokumente.zip", "blob_url": "https://example.com/files/zusaetzliche_dokumente.zip", "url": "https://example.com/files/zusaetzliche_dokumente.zip"},
                    {"filename": "anhang_1.pdf", "blob_url": "https://example.com/files/anhang_1.pdf", "url": "https://example.com/files/anhang_1.pdf"},
                    {"filename": "klaerungen.pdf", "blob_url": "https://example.com/files/klaerungen.pdf", "url": "https://example.com/files/klaerungen.pdf"}
                ]
            else:  # Default to Polish
                overall_summary = "Przykładowe podsumowanie zmian w przetargu. Dodano nowe dokumenty i zaktualizowano specyfikację techniczną."
                file_summaries = [
                    {"filename": "specyfikacja_techniczna_v2.pdf", "summary": "Zaktualizowano wymagania techniczne i dodano nowe parametry urządzeń."},
                    {"filename": "formularz_oferty.doc", "summary": "Poprawiono błędy w formularzu i dodano nowe pola do wypełnienia."}
                ]
                files_uploaded = [
                    {"filename": "dokumenty_dodatkowe.zip", "blob_url": "https://example.com/files/dokumenty_dodatkowe.zip", "url": "https://example.com/files/dokumenty_dodatkowe.zip"},
                    {"filename": "aneks_nr_1.pdf", "blob_url": "https://example.com/files/aneks_nr_1.pdf", "url": "https://example.com/files/aneks_nr_1.pdf"},
                    {"filename": "wyjaśnienia.pdf", "blob_url": "https://example.com/files/wyjaśnienia.pdf", "url": "https://example.com/files/wyjaśnienia.pdf"}
                ]
            
            notification_content = service._create_update_notification_content(
                overall_summary=overall_summary,
                file_summaries=file_summaries,
                files_uploaded=files_uploaded,
                user_language=user_language,
                tender_analysis_id=tender_analysis_id,
                tender_result_id=tender_result_id,
                tender_name=tender_name,
                organization=organization,
                original_tender_url=tender_url
            )
        elif notification_type == "outcome":
            outcome_prefix = get_translation(user_language, "outcome_prefix")
            notification_title = f"{outcome_prefix}: {tender_name}"
            outcome_details = {
                "completion_status": get_translation(user_language, "tender_completed"),
                "winner_name": "Example Winner Sp. z o.o.",
                "winner_location": "Warszawa, PL",
                "winning_price": "1 500 000 PLN",
                "total_offers": 5,
                "lowest_price": "1 350 000 PLN",
                "highest_price": "1 950 000 PLN",
                "contract_value": "1 500 000 PLN"
            }
            notification_content = service._create_outcome_notification_content(
                tender_name=tender_name,
                organization=organization,
                user_language=user_language,
                tender_analysis_id=tender_analysis_id,
                tender_result_id=tender_result_id,
                outcome_details=outcome_details
            )
        else:
            raise HTTPException(status_code=400, detail="notification_type must be 'update' or 'outcome'")
        
        return {
            "title": notification_title,
            "content": notification_content,
            "platform_url": service._construct_platform_url(tender_analysis_id, tender_result_id),
            "tender_name": tender_name,
            "organization": organization,
            "language": user_language,
            "notification_type": notification_type
        }
        
    except Exception as e:
        logger.error(f"Failed to preview notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to preview notification: {str(e)}")

@router.get("/tender-info/{tender_result_id}")
async def get_tender_info(
    tender_result_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get information about a specific tender for testing purposes.
    """
    try:
        tender_result = await db.tender_analysis_results.find_one(
            {"_id": ObjectId(tender_result_id)}
        )
        
        if not tender_result:
            raise HTTPException(status_code=404, detail=f"Tender result {tender_result_id} not found")
        
        # Convert ObjectId to string for JSON serialization
        tender_result["_id"] = str(tender_result["_id"])
        tender_result["tender_analysis_id"] = str(tender_result["tender_analysis_id"])
        
        return {
            "tender_result": tender_result,
            "analysis_id": str(tender_result["tender_analysis_id"]),
            "result_id": tender_result_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get tender info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get tender info: {str(e)}") 