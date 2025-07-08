import os
from pprint import pprint
import sys
import logging
from datetime import datetime
import asyncio
from typing import List

from minerva.core.models.extensions.tenders.tender_analysis import FileExtractionStatus, TenderAnalysisResult, TenderLocation, TenderMetadata
from minerva.core.helpers.biznespolska_oferent_shared import get_best_tender_url
from minerva.tasks.sources.biznespolska.extract_tenders import BiznesPolskaReportExtractor
from minerva.tasks.sources.oferent.extract_tenders import OferentReportExtractor
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from minerva.core.database.database import db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("external_scraping_runner")


async def extract_oferent(user_id, analysis_id, date):
    account_num = os.getenv(f"ANALYSIS_{analysis_id}_OFERENT_ACCOUNT_NUMBER")
    email = os.getenv(f"ANALYSIS_{analysis_id}_OFERENT_EMAIL")
    if not account_num or not email:
        logger.warning(f"Missing Oferent credentials for user {user_id}.")
        return None
    extractor = OferentReportExtractor()
    try:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {date}. Use YYYY-MM-DD")
            return None
        inputs = {"target_date": date, "account_number": account_num, "email": email}
        result = await extractor.execute(inputs)
        logger.info(f"Oferent extraction complete for analysis {analysis_id}. Tenders: {len(result.get('tenders', []))}")
        return result
    except Exception as e:
        logger.error(f"Extraction failed for Oferent: {str(e)}")
        return None

async def extract_biznespolska(user_id, analysis_id, date, profile=None):
    username = os.getenv(f"ANALYSIS_{analysis_id}_BIZNESPOLSKA_USERNAME")
    password = os.getenv(f"ANALYSIS_{analysis_id}_BIZNESPOLSKA_PASSWORD")
    if not profile:
        profile = os.getenv(f"ANALYSIS_{analysis_id}_BIZNESPOLSKA_PROFILE")
    if not username or not password or not profile:
        logger.warning(f"Missing BiznesPolska credentials for user {user_id}.")
        return None
    extractor = BiznesPolskaReportExtractor()
    try:
        inputs = {
            "username": username,
            "password": password,
            "profile_name": profile,
            "date_from": date,
            "date_to": date,
        }
        result = await extractor.execute(inputs)
        logger.info(f"BiznesPolska extraction complete for analysis {analysis_id}. Tenders: {len(result.get('tenders', []))}")
        return result
    except Exception as e:
        logger.error(f"Extraction failed for BiznesPolska: {str(e)}")
        return None

async def save_results_to_db(result, source_name, user_id, analysis_id):
    if not result:
        logger.warning(f"No results to save for {source_name} analysis {analysis_id} for user {user_id}.")
        return
    tenders = result.get('tenders', [])
    results_cnt = 0
    for tender in tenders:
        tender = tender.model_dump(by_alias=True)
        tender_metadata = TenderMetadata(
            name=tender.get('name', ''),
            organization=tender.get('organization', ''),
            submission_deadline=tender.get('submission_deadline', ''),
            procedure_type=tender.get('procedure_type', None),
            initiation_date=tender.get('initiation_date', None)
        )
        location = TenderLocation(
            country="Polska",
            voivodeship=tender.get('regoin', ''),
            city=tender.get('city', '')
        )
        file_extraction_status = FileExtractionStatus(
            user_id=user_id,
            files_processed=0,
            files_uploaded=0,
            status="not_extracted"
        )
        result = TenderAnalysisResult(
            user_id=ObjectId(user_id),
            tender_analysis_id=ObjectId(analysis_id),
            tender_url=tender.get('details_url', ''),
            source=source_name,
            location=location,
            tender_score=None,
            tender_metadata=tender_metadata,
            tender_description=tender.get('description', None),
            file_extraction_status=file_extraction_status,
            criteria_analysis=[],
            criteria_analysis_archive=None,
            criteria_analysis_edited=False,
            company_match_explanation="",
            assistant_id=None,
            pinecone_config=None,
            tender_pinecone_id=None,
            uploaded_files=[],
            updates=[],
            status="external",
            updated_at=None,
            created_at=datetime.utcnow(),
            opened_at=None,
            order_number=None,
            language=None,
            external_best_url=get_best_tender_url(tender)
        )
        # Save to DB
        await db.tender_analysis_results.insert_one(result.model_dump(by_alias=True))
        results_cnt += 1
    logger.info(f"Saved {results_cnt} results to DB for {source_name} analysis {analysis_id} for user {user_id}.")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python external_scraping_runner.py <date>")
        sys.exit(1)
    date = sys.argv[1]
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        print(f"Invalid date format: {date}. Use YYYY-MM-DD")
        sys.exit(1)

    analyses: List[dict] = await db.tender_analysis.find({"include_external_sources": True}).to_list(length=None)
    if not analyses:
        print("No analyses with include_external_sources=True found.")
        return
    for analysis in analyses:
        analysis_id = str(analysis["_id"])
        user_id = str(analysis["user_id"])
        # Oferent
        oferent_result = await extract_oferent(user_id, analysis_id, date)
        await save_results_to_db(oferent_result, "oferent", user_id, analysis_id)
        # BiznesPolska
        profile = analysis.get("profile") or None
        biznespolska_result = await extract_biznespolska(user_id, analysis_id, date, profile)
        await save_results_to_db(biznespolska_result, "biznespolska", user_id, analysis_id)

if __name__ == "__main__":
    asyncio.run(main())
