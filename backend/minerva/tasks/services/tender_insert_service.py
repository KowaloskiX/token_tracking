import logging
from typing import Dict, List, Protocol, Any
from datetime import datetime
from elasticsearch import helpers
from minerva.core.models.request.tender_extract import ExtractionRequest, Tender
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, EmbeddingTool
from minerva.core.services.keyword_search.elasticsearch import es_client
from dataclasses import dataclass


@dataclass
class TenderInsertConfig:
    pinecone_config: EmbeddingConfig
    elasticsearch_index: str = "tenders"
    skip_elasticsearch: bool = False
    skip_pinecone: bool = False
    
    @classmethod
    def create_default(cls, 
                       pinecone_index: str = "tenders", 
                       pinecone_namespace: str = "", 
                       embedding_model: str = "text-embedding-3-large",
                       elasticsearch_index: str = "tenders"):
        pinecone_config = EmbeddingConfig(
            index_name=pinecone_index,
            namespace=pinecone_namespace,
            embedding_model=embedding_model
        )
    
        return cls(
            pinecone_config=pinecone_config,
            elasticsearch_index=elasticsearch_index
        )

class TenderSource(Protocol):
    async def execute(self, inputs: Dict) -> Dict:
        pass


class TenderAdapter(Protocol):
    def prepare_embedding_item(self, tender: Tender) -> Dict:
        pass


class GenericTenderAdapter:
    def prepare_embedding_item(self, tender: Tender) -> Dict:
        # Use the 'details_url' as the unique ID for Pinecone
        item_id = tender.details_url
        
        input_text = f"{tender.name.strip()} {tender.organization.strip()}".strip()
        if not input_text:
            input_text = "Unnamed Tender"
        
        metadata = tender.dict()
        
        return {
            "input": input_text,
            "metadata": metadata,
            "id": item_id
        }


def ensure_elasticsearch_index(index_name: str):
    """Create or update Elasticsearch index with proper mappings for tender data"""
    if not es_client.indices.exists(index=index_name):
        # Create index with mappings
        mappings = {
            "mappings": {
                "properties": {
                    "text": {
                        "type": "text"
                    },
                    "title": {
                        "type": "text"
                    },
                    "organization": {
                        "type": "text"
                    },
                    "initiation_date": {
                        "type": "date",
                        "format": "yyyy-MM-dd"
                    },
                    "metadata": {
                        "type": "object",
                        "dynamic": True
                    }
                }
            }
        }
        es_client.indices.create(
            index=index_name,
            body=mappings
        )
        logging.info(f"Created Elasticsearch index: {index_name}")
    else:
        # Update existing index mapping if needed
        mappings = {
            "properties": {
                "text": {
                    "type": "text"
                },
                "title": {
                    "type": "text"
                },
                "organization": {
                    "type": "text"
                },
                "initiation_date": {
                    "type": "date",
                    "format": "yyyy-MM-dd"
                },
                "metadata": {
                    "type": "object",
                    "dynamic": True
                }
            }
        }
        es_client.indices.put_mapping(
            index=index_name,
            body=mappings
        )
        logging.info(f"Updated Elasticsearch index mappings: {index_name}")

################################
# Updated TenderInsertService with TenderInsertConfig
################################

class TenderInsertService:
    def __init__(
        self,
        config: TenderInsertConfig,
        tender_source: TenderSource,
        tender_adapter: TenderAdapter = None
    ):
        self.config = config
        self.embedding_tool = EmbeddingTool(config.pinecone_config) if not config.skip_pinecone else None
        self.es_index_name = config.elasticsearch_index
        self.tender_source = tender_source
        self.tender_adapter = tender_adapter or GenericTenderAdapter()
        
        # Ensure Elasticsearch index is ready if not skipped
        if not config.skip_elasticsearch:
            ensure_elasticsearch_index(self.es_index_name)

    async def process_tenders(self, extraction_request: ExtractionRequest) -> Dict:
        """Process tenders by extracting and inserting into both Pinecone and Elasticsearch"""
        logging.info("Starting tender extraction and insertion process...")
        extraction_result = await self.tender_source.execute(extraction_request.dict())

        all_tenders = extraction_result["tenders"]
        logging.info(f"Extracted {len(all_tenders)} tenders")

        if not all_tenders:
            logging.info("No tenders found, nothing to process.")
            return {
                "extraction_metadata": extraction_result["metadata"],
                "embedding_result": {
                    "processed_count": 0,
                    "total_items": 0,
                    "failed_items": []
                },
                "elasticsearch_result": {
                    "stored_count": 0,
                    "failed_count": 0
                }
            }
        
        # Process for Pinecone (vector search)
        pinecone_result = await self._process_for_pinecone(all_tenders) if not self.config.skip_pinecone else {
            "processed_count": 0,
            "total_items": 0,
            "failed_items": [],
            "skipped": True
        }
        
        # Process for Elasticsearch (lexical search)
        elasticsearch_result = await self._process_for_elasticsearch(all_tenders) if not self.config.skip_elasticsearch else {
            "stored_count": 0,
            "failed_count": 0,
            "skipped": True
        }
        
        return {
            "extraction_metadata": extraction_result["metadata"],
            "embedding_result": pinecone_result,
            "elasticsearch_result": elasticsearch_result
        }
    
    async def _process_for_pinecone(self, all_tenders: List[Tender]) -> Dict:
        """Process tenders for Pinecone vector embeddings"""
        logging.info("Preparing items for embedding...")
        embedding_items = []
        
        for tender in all_tenders:
            tender_id = tender.details_url
            if self.check_if_exists(tender_id):
                logging.info(f"Skipping tender with ID {tender_id} since it already exists in Pinecone.")
                continue

            item = self.tender_adapter.prepare_embedding_item(tender)
            
            # Validate input text
            if not isinstance(item["input"], str) or len(item["input"].strip()) == 0:
                logging.error(f"Invalid input text for tender {item['id']}, skipping.")
                continue

            embedding_items.append(item)

        if not embedding_items:
            logging.info("No new tenders to embed (all duplicates or invalid).")
            return {
                "processed_count": 0,
                "total_items": 0,
                "failed_items": []
            }

        total_items = len(embedding_items)
        logging.info(f"Starting embedding process for {total_items} new tenders...")

        # Log some quick stats
        unique_ids = len({item['id'] for item in embedding_items})
        avg_length = sum(len(item["input"]) for item in embedding_items) / total_items
        logging.info(f"Number of unique IDs: {unique_ids}")
        logging.info(f"Average input text length: {avg_length:.2f}")

        embedding_result = await self.embedding_tool.embed_and_store_batch(items=embedding_items)

        logging.info(
            f"Embedding completed. Processed "
            f"{embedding_result['processed_count']}/{total_items} items."
        )
        if embedding_result["failed_items"]:
            logging.warning(f"Failed to process {len(embedding_result['failed_items'])} items.")

        return embedding_result
        
    async def _process_for_elasticsearch(self, all_tenders: List[Tender]) -> Dict:
        """Process tenders for Elasticsearch lexical search"""
        try:
            # Prepare documents for bulk ingestion
            actions = []
            for tender in all_tenders:
                # Skip existing tenders - use the same check as in Pinecone
                tender_id = tender.details_url
                if self.check_if_elasticsearch_exists(tender_id):
                    logging.info(f"Skipping tender with ID {tender_id} since it already exists in Elasticsearch.")
                    continue
                
                # Safely get name and organization with defaults
                name = getattr(tender, 'name', '') or ''
                organization = getattr(tender, 'organization', '') or ''
                
                # Create the same combined text that's used for Pinecone
                combined_text = f"{name.strip()} {organization.strip()}".strip()
                if not combined_text:
                    combined_text = "Unnamed Tender"
                
                # Get ALL metadata fields directly - exactly like we do in Pinecone
                tender_dict = tender.dict() if hasattr(tender, 'dict') else {}
                
                # Make sure we have the initiation_date
                initiation_date = tender_dict.get('initiation_date', '')
                
                # Create document for Elasticsearch - MATCH the Pinecone structure
                doc = {
                    "text": combined_text,  # Use the same combined text as Pinecone
                    "title": name,
                    "organization": organization,
                    "initiation_date": initiation_date,
                    "metadata": tender_dict  # Use the EXACT SAME metadata structure as Pinecone
                }
                
                # Log the document to help with debugging
                logging.debug(f"Preparing ES document for tender {tender_id}: {doc}")
                
                actions.append({
                    "_index": self.es_index_name,
                    "_id": tender_id,  # Use same ID as in Pinecone for consistency
                    "_source": doc
                })
                
            if not actions:
                logging.info("No new tenders to store in Elasticsearch (all duplicates or invalid).")
                return {"stored_count": 0, "failed_count": 0}
            
            # Perform bulk ingestion
            success, failed = helpers.bulk(es_client, actions, stats_only=True)
            logging.info(f"Elasticsearch ingestion: {success} succeeded, {failed} failed")
            return {"stored_count": success, "failed_count": failed}
                    
        except Exception as e:
            logging.error(f"Error storing in Elasticsearch: {str(e)}")
            logging.exception("Detailed exception")  # Add full traceback for better debugging
            return {"error": str(e), "stored_count": 0, "failed_count": 0}
    
    def check_if_exists(self, tender_id: str) -> bool:
        """Check if tender with given ID already exists in Pinecone"""
        if self.config.skip_pinecone:
            return False
            
        logging.info(f"Checking if tender with ID {tender_id} already exists in Pinecone...")

        # Use Pinecone's 'fetch' API to see if that ID is present
        fetch_result = self.embedding_tool.index.fetch(ids=[tender_id])
        exists = tender_id in fetch_result.vectors

        if exists:
            logging.info(f"Tender with ID {tender_id} already exists in Pinecone.")
        else:
            logging.info(f"Tender with ID {tender_id} does not exist in Pinecone.")

        return exists
    
    def check_if_elasticsearch_exists(self, tender_id: str) -> bool:
        """Check if tender with given ID already exists in Elasticsearch"""
        if self.config.skip_elasticsearch:
            return False
            
        logging.info(f"Checking if tender with ID {tender_id} already exists in Elasticsearch...")
        
        try:
            result = es_client.exists(index=self.es_index_name, id=tender_id)
            if result:
                logging.info(f"Tender with ID {tender_id} already exists in Elasticsearch.")
            else:
                logging.info(f"Tender with ID {tender_id} does not exist in Elasticsearch.")
            return result
        except Exception as e:
            logging.error(f"Error checking if tender exists in Elasticsearch: {str(e)}")
            return False
    
    async def scrape_tenders(self, extraction_request: ExtractionRequest) -> List[Dict]:
        """Get raw tender data without processing"""
        extraction_result = await self.tender_source.execute(extraction_request.dict())
        return extraction_result["tenders"]