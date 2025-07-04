import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from minerva.tasks.services.tender_insert_service import TenderInsertConfig
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, UpsertTool
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.tasks.sources.ezamowienia.extract_historical_tenders import HistoricalTenderExtractor, HistoricalTender
from minerva.core.database.database import db
from minerva.core.helpers.biznespolska_oferent_shared import is_same_tender

logger = logging.getLogger("minerva.tasks.historical_tenders")

class HistoricalTenderService:    
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

    async def query_multipart_tenders(
        self, 
        query: str, 
        top_k: int = 20, 
        embedding_model: Optional[str] = None,
        score_threshold: float = 0.0
    ) -> Dict[str, Any]:
        """Query historical tenders specifically filtering for multi-part tenders"""
        try:
            query_tool = QueryTool(config=QueryConfig(
                index_name="historical-tenders",
                embedding_model=embedding_model or "text-embedding-3-large"
            ))
            
            filter_conditions = {"total_parts": {"$gt": 1}}
            
            results = await query_tool.query_by_text(
                query_text=query,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_conditions=filter_conditions
            )
            
            return {
                "matches": results["matches"],
                "total_results": len(results["matches"]),
                "filters_applied": results.get("filter_applied"),
                "query": query,
                "index": "historical-tenders",
                "filter_note": "Filtered for multi-part tenders only (total_parts > 1)"
            }
        except Exception as e:
            logger.error(f"Error querying multi-part historical tenders: {e}")
            raise e

    async def query_by_initiation_date(
        self,
        initiation_date: str,
        top_k: int = 1000,
        embedding_model: Optional[str] = None,
        score_threshold: float = 0.0
    ) -> Dict[str, Any]:
        """Query all historical tenders with a given initiation_date"""
        try:
            # Validate date format
            datetime.strptime(initiation_date, "%Y-%m-%d")
            
            query_tool = QueryTool(config=QueryConfig(
                index_name="historical-tenders",
                embedding_model=embedding_model or "text-embedding-3-large"
            ))

            filter_conditions = {"initiation_date": {"$eq": initiation_date}}

            results = await query_tool.query_by_text(
                query_text="",  # Empty query to return all matches for the filter
                top_k=top_k,
                score_threshold=score_threshold,
                filter_conditions=filter_conditions
            )

            return {
                "matches": results["matches"],
                "total_results": len(results["matches"]),
                "filters_applied": results.get("filter_applied"),
                "query": f"All tenders with initiation_date={initiation_date}",
                "index": "historical-tenders"
            }
        except ValueError:
            raise ValueError("Invalid initiation_date format. Use YYYY-MM-DD.")
        except Exception as e:
            logger.error(f"Error querying historical tenders by initiation_date: {e}")
            raise e

    async def query_by_initiation_date_and_update_finished_id(
        self,
        initiation_date: str,
        top_k: int = 1000,
        embedding_model: Optional[str] = None,
        score_threshold: float = 0.0
    ) -> Dict[str, Any]:
        """
        Query all historical tenders with a given initiation_date, and for each result, find the corresponding
        tender_analysis_results in MongoDB by tender_url (matching original_tender_url), and set finished_id to Pinecone object id.
        """
        try:
            # Validate date format
            datetime.strptime(initiation_date, "%Y-%m-%d")
            
            # Query historical tenders
            hist_tool = QueryTool(QueryConfig(
                index_name="historical-tenders",
                embedding_model=embedding_model or "text-embedding-3-large",
            ))
            filter_conditions = {"initiation_date": {"$eq": initiation_date}}
            hist_results = await hist_tool.query_by_text(
                query_text="",       # empty → match all with the filter
                top_k=top_k,
                score_threshold=score_threshold,
                filter_conditions=filter_conditions,
            )

            # Process matches and update MongoDB
            update_result = await self._update_finished_ids(hist_results["matches"], embedding_model)
            
            return {
                "matches": hist_results["matches"],
                "total_results": len(hist_results["matches"]),
                "updated_with_url": update_result["updated_with_url"],
                "updated_without_url": update_result["updated_without_url"],
                "not_matched_primary": update_result["not_matched_primary"],
                "not_matched_fallback": update_result["not_matched_fallback"],
                "updated_tender_analysis_ids": update_result["updated_tender_analysis_ids"],
                "filters_applied": hist_results.get("filter_applied"),
                "query": f"All tenders with initiation_date={initiation_date}",
                "index": "historical-tenders",
            }
        except ValueError:
            raise ValueError("Invalid initiation_date format. Use YYYY-MM-DD.")
        except Exception as e:
            logger.error(f"Error querying and updating historical tenders: {e}")
            raise e

    async def get_by_pinecone_id(
        self, 
        pinecone_id: str, 
        embedding_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return all data from Pinecone for a finished tender by its Pinecone id"""
        try:
            query_tool = QueryTool(config=QueryConfig(
                index_name="historical-tenders",
                embedding_model=embedding_model or "text-embedding-3-large"
            ))
            
            results = await query_tool.query_by_id(pinecone_id)
            if not results or not results.get("matches"):
                raise ValueError("Tender not found in Pinecone.")
            
            return results["matches"][0]
        except Exception as e:
            logger.error(f"Error fetching tender from Pinecone: {e}")
            raise e

    async def _update_finished_ids(self, matches: List[Dict], embedding_model: Optional[str] = None) -> Dict[str, Any]:
        """Update finished_id in MongoDB tender_analysis_results for matched historical tenders"""
        not_matched_primary: List[str] = []
        not_matched_fallback: List[Dict] = []
        updated_with_url: List[str] = []
        updated_without_url: List[Dict] = []
        updated_tender_analysis_ids: List[str] = []  # Track actual tender analysis result IDs

        # Source mapping for fallback search
        SOURCE_MAP = {
            "ezamowienia.gov.pl": "ezamowienia",
            "ted.europa.eu": "ted",
            "egospodarka.pl": "egospodarka",
            "eb2b.com.pl": "eb2b",
            "ezamawiajacy.pl": "ezamawiajacy",
            "logintrade.pl": "logintrade",
            "smartpzp.pl": "smartpzp",
            "epropublico.pl": "epropublico_main",
            "platformazakupowa.pl": "platformazakupowa",
            "bazakonkurencyjnosci.funduszeeuropejskie.gov.pl": "bazakonkurencyjnosci",
            "connect.orlen.pl": "orlenconnect",
            "pge.pl": "pge",
        }

        for hist in matches:
            hist_id = hist["id"]
            hist_meta = hist.get("metadata", {}) or {}
            url = hist_meta.get("original_tender_url")
            name = (hist_meta.get("name") or "").strip()
            organization = (hist_meta.get("organization") or "").strip()

            # Try primary URL match
            mongo_doc = None
            with_url = False
            if url:
                mongo_doc = await db.tender_analysis_results.find_one(
                    {"tender_url": url}
                )
                if mongo_doc:
                    with_url = True

            # Fallback: semantic search by name + org
            if not mongo_doc and (name or organization):
                query_text = f"{name} {organization}".strip()

                # Determine source_type from url if possible
                source_type = None
                if url:
                    for k, v in SOURCE_MAP.items():
                        if k in url:
                            source_type = v
                            break
                if source_type == "ezamowienia":
                    continue
                
                tenders_tool = QueryTool(QueryConfig(
                    index_name="tenders",
                    embedding_model=embedding_model or "text-embedding-3-large",
                ))
                filter_conditions = None
                if source_type:
                    filter_conditions = {"source_type": {"$eq": source_type}}

                cand_results = await tenders_tool.query_by_text(
                    query_text=query_text,
                    top_k=3,
                    score_threshold=0.45,
                    filter_conditions=filter_conditions,
                )

                for cand in cand_results["matches"]:
                    cand_meta = cand.get("metadata", {}) or {}
                    a = {
                        "id": cand_meta.get("details_url"),
                        "name": cand_meta.get("name"),
                        "organization": cand_meta.get("organization"),
                    }
                    b = {
                        "id": hist_meta.get("original_tender_url"),
                        "name": hist_meta.get("name"),
                        "organization": hist_meta.get("organization"),
                    }
                    if is_same_tender(a, b):
                        cand_url = (
                            cand_meta.get("details_url")
                            or cand_meta.get("original_tender_url")
                        )
                        if cand_url:
                            mongo_doc = await db.tender_analysis_results.find_one(
                                {"tender_url": cand_url}
                            )
                            if mongo_doc:
                                updated_without_url.append({"a": a, "b": b})
                                break

                # Record diagnostics when fallback couldn't find anything
                if not mongo_doc:
                    not_matched_fallback.append(
                        {"hist_id": hist_id, "query": query_text}
                    )

            # Persist when we finally have a Mongo document
            if mongo_doc:
                await db.tender_analysis_results.update_one(
                    {"_id": mongo_doc["_id"]},
                    {"$set": {"finished_id": hist_id}},
                )
                # Track the tender analysis result ID for notifications
                updated_tender_analysis_ids.append(str(mongo_doc["_id"]))
                
                if with_url:
                    updated_with_url.append(url)
            else:
                not_matched_primary.append(url or f"(no-url) {hist_id}")

        return {
            "updated_with_url": updated_with_url,
            "updated_without_url": updated_without_url,
            "not_matched_primary": not_matched_primary,
            "not_matched_fallback": not_matched_fallback,
            "updated_tender_analysis_ids": updated_tender_analysis_ids,  # Return the actual IDs for notifications
        }
    
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
            
            "main_cpv_code": tender.main_cpv_code,
            "additional_cpv_codes": tender.additional_cpv_codes,
            
            "original_tender_url": tender.original_tender_url,
            
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
        
        if tender.main_cpv_code:
            content_parts.append(f"Main CPV: {tender.main_cpv_code}")
        
        if tender.additional_cpv_codes:
            content_parts.append(f"Additional CPV: {', '.join(tender.additional_cpv_codes)}")
        
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
                index_name=self.config.pinecone_config.index_name,
                namespace=self.config.pinecone_config.namespace,
                embedding_model=self.config.pinecone_config.embedding_model,
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