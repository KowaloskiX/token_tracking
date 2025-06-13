import logging
from typing import Dict

from minerva.tasks.sources.logintrade.logintrade_base import LogintradeBase
from minerva.tasks.sources.logintrade.logintrade_net_extractor import LogintradeNetExtractor
from minerva.tasks.sources.logintrade.logintrade_old_extractor import LogintradeOldExtractor

from minerva.core.models.request.tender_extract import ExtractorMetadata


class LoginTradeExtractor(LogintradeBase):

    def __init__(
        self,
        source_type: str = "logintrade"
    ):
        self.source_type = source_type

    async def execute(self, inputs: Dict) -> Dict:
        logging.info("[LoginTradeExtractor] Starting execution with both extractors")
        
        logintrade_old_extractor = LogintradeOldExtractor()
        logintrade_net_extractor = LogintradeNetExtractor()
        
        logging.info("[LoginTradeExtractor] Running old extractor")
        logintrade_old_result = await logintrade_old_extractor.execute_self(inputs)
        logging.info(f"[LoginTradeExtractor] Old extractor found {len(logintrade_old_result['tenders'])} tenders")
        
        logging.info("[LoginTradeExtractor] Running net extractor")
        logintrade_net_result = await logintrade_net_extractor.execute_self(inputs)
        logging.info(f"[LoginTradeExtractor] Net extractor found {len(logintrade_net_result['tenders'])} tenders")
        
        # Merge tenders from both results
        all_tenders = logintrade_old_result["tenders"] + logintrade_net_result["tenders"]
        logging.info(f"[LoginTradeExtractor] Total tenders before deduplication: {len(all_tenders)}")
        
        # Remove duplicates based on details_url
        seen_urls = set()
        unique_tenders = []
        for tender in all_tenders:
            if tender.details_url not in seen_urls:
                seen_urls.add(tender.details_url)
                unique_tenders.append(tender)
        
        logging.info(f"[LoginTradeExtractor] Total unique tenders after deduplication: {len(unique_tenders)}")
        logging.info(f"[LoginTradeExtractor] Removed {len(all_tenders) - len(unique_tenders)} duplicate tenders")
        
        # Create metadata based on the merged list
        metadata = ExtractorMetadata(
            total_tenders=len(unique_tenders),
            pages_scraped=max(
                logintrade_old_result["metadata"].pages_scraped,
                logintrade_net_result["metadata"].pages_scraped
            )
        )
        
        logging.info(f"[LoginTradeExtractor] Final metadata - total_tenders: {metadata.total_tenders}, pages_scraped: {metadata.pages_scraped}")
        
        return {
            "tenders": unique_tenders,
            "metadata": metadata
        }