import logging
from typing import Dict, List, Any
from minerva.tasks.services.tender_insert_service import TenderInsertConfig
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, UpsertTool
from minerva.tasks.sources.ezamowienia.extract_historical_tenders import HistoricalTenderExtractor, HistoricalTender

logger = logging.getLogger("minerva.tasks.historical_tenders")

class HistoricalTenderInsertService:    
    def __init__(self, config: TenderInsertConfig):
        self.config = config
        self.extractor = HistoricalTenderExtractor()
    
    async def process_historical_tenders(self, request_data: Dict) -> Dict[str, Any]:
        try:
            extraction_result = await self.extractor.execute(request_data)
            historical_tenders = extraction_result.get("tenders", [])
            
            if not historical_tenders:
                logger.info("No historical tenders found for the given criteria")
                return {
                    "embedding_result": {"processed_count": 0},
                    "elasticsearch_result": {"stored_count": 0},
                    "metadata": extraction_result.get("metadata")
                }
            
            logger.info(f"Found {len(historical_tenders)} historical tenders to process")
            
            tender_dicts = []
            for tender in historical_tenders:
                if isinstance(tender, HistoricalTender):
                    tender_dict = self._convert_historical_tender_to_dict(tender)
                    tender_dicts.append(tender_dict)
                else:
                    tender_dicts.append(tender)
            
            embedding_result = await self._process_embeddings(tender_dicts)
            
            elasticsearch_result = await self._process_elasticsearch(tender_dicts)
            
            return {
                "embedding_result": embedding_result,
                "elasticsearch_result": elasticsearch_result,
                "metadata": extraction_result.get("metadata")
            }
            
        except Exception as e:
            logger.error(f"Error processing historical tenders: {e}")
            raise e
    
    def _convert_historical_tender_to_dict(self, tender: HistoricalTender) -> Dict[str, Any]:
        """Convert HistoricalTender object to dictionary for embedding"""
        return {
            "name": tender.name,
            "organization": tender.organization,
            "location": tender.location,
            "submission_deadline": tender.announcement_date,
            "initiation_date": tender.announcement_date,
            "details_url": tender.details_url,
            "content_type": tender.content_type,
            "source_type": tender.source_type,
            
            "total_parts": tender.total_parts,
            "parts_summary": tender.parts_summary,
            
            "completion_status": tender.completion_status,
            "total_offers": tender.total_offers,
            "sme_offers": tender.sme_offers,
            "lowest_price": tender.lowest_price,
            "highest_price": tender.highest_price,
            "winning_price": tender.winning_price,
            "winner_name": tender.winner_name,
            "winner_location": tender.winner_location,
            "winner_size": tender.winner_size,
            "contract_date": tender.contract_date,
            "contract_value": tender.contract_value,
            "realization_period": tender.realization_period,
            "full_content": tender.full_content,
            
            "searchable_content": self._create_searchable_content(tender)
        }

    def _create_searchable_content(self, tender: HistoricalTender) -> str:
        """Create searchable text content from historical tender data"""
        content_parts = [
            f"Tender: {tender.name}",
            f"Organization: {tender.organization}",
            f"Location: {tender.location}"
        ]
        
        if tender.total_parts > 1:
            content_parts.append(f"Multi-part tender with {tender.total_parts} parts")
            if tender.parts_summary:
                content_parts.append(f"Parts: {tender.parts_summary}")
        
        if tender.winner_name:
            content_parts.append(f"Winner: {tender.winner_name}")
        if tender.winner_location:
            content_parts.append(f"Winner Location: {tender.winner_location}")
        if tender.contract_value:
            content_parts.append(f"Contract Value: {tender.contract_value}")
        if tender.winning_price:
            content_parts.append(f"Winning Price: {tender.winning_price}")
        if tender.completion_status:
            content_parts.append(f"Status: {tender.completion_status}")
        if tender.realization_period:
            content_parts.append(f"Realization Period: {tender.realization_period}")
        
        if tender.parts and len(tender.parts) > 0:
            parts_details = []
            for part in tender.parts:
                part_detail = f"Part {part.part_number}: {part.description}"
                if part.cpv_code:
                    part_detail += f" (CPV: {part.cpv_code})"
                if part.part_value:
                    part_detail += f" Value: {part.part_value}"
                if part.winner_name:
                    part_detail += f" Winner: {part.winner_name}"
                parts_details.append(part_detail)
            
            if parts_details:
                content_parts.append("Detailed parts: " + " | ".join(parts_details))
        
        if tender.full_content:
            truncated_content = tender.full_content[:2000] if len(tender.full_content) > 2000 else tender.full_content
            content_parts.append(f"Details: {truncated_content}")
        
        return " | ".join(content_parts)
    
    async def _process_embeddings(self, tender_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process embeddings for historical tenders"""
        try:
            embedding_config = EmbeddingConfig(
                index_name=self.config.pinecone_index,
                namespace=self.config.pinecone_namespace,
                embedding_model=self.config.embedding_model,
                batch_size=50
            )
            
            upsert_tool = UpsertTool(config=embedding_config)
            
            result = await upsert_tool.upsert_tenders_from_dict(tender_dicts)
            
            logger.info(f"Successfully processed {result.get('processed_count', 0)} historical tenders for embedding")
            return result
            
        except Exception as e:
            logger.error(f"Error processing embeddings for historical tenders: {e}")
            return {"processed_count": 0, "error": str(e)}
    
    async def _process_elasticsearch(self, tender_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process Elasticsearch storage for historical tenders (placeholder)"""
        try:
            stored_count = len(tender_dicts)
            
            logger.info(f"Historical tender Elasticsearch processing: {stored_count} tenders (placeholder)")
            return {"stored_count": stored_count}
            
        except Exception as e:
            logger.error(f"Error processing Elasticsearch for historical tenders: {e}")
            return {"stored_count": 0, "error": str(e)}