import logging
import pprint
from typing import Dict, List, Protocol, Any
from datetime import datetime
from elasticsearch import helpers
from minerva.core.models.request.tender_extract import ExtractionRequest, Tender
from minerva.core.services.vectorstore.helpers import safe_chunk_text
from minerva.core.services.vectorstore.text_chunks import ChunkingConfig, TextChunker
from minerva.core.services.vectorstore.pinecone.upsert import EmbeddingConfig, EmbeddingTool
from minerva.core.services.keyword_search.elasticsearch import es_client
from dataclasses import dataclass


@dataclass
class TenderInsertConfig:
    pinecone_config: EmbeddingConfig
    subject_pinecone_config: EmbeddingConfig = None
    elasticsearch_index: str = "tenders"
    skip_elasticsearch: bool = False
    skip_pinecone: bool = False
    
    @classmethod
    def create_default(cls, 
                       pinecone_index: str = "tenders", 
                       pinecone_namespace: str = "", 
                       subject_pinecone_index: str = "tender-subjects",
                       subject_pinecone_namespace: str = "",
                       embedding_model: str = "text-embedding-3-large",
                       elasticsearch_index: str = "tenders"):
        pinecone_config = EmbeddingConfig(
            index_name=pinecone_index,
            namespace=pinecone_namespace,
            embedding_model=embedding_model
        )
        
        subject_pinecone_config = EmbeddingConfig(
            index_name=subject_pinecone_index,
            namespace=subject_pinecone_namespace,
            embedding_model=embedding_model
        )
    
        return cls(
            pinecone_config=pinecone_config,
            subject_pinecone_config=subject_pinecone_config,
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
        
        # Get tender metadata but exclude tender_subject
        metadata = tender.dict()
        if 'tender_subject' in metadata:
            logging.info(f"Removing tender_subject from metadata for tender {item_id}")
            del metadata['tender_subject']
        
        return {
            "input": input_text,
            "metadata": metadata,
            "id": item_id
        }


async def ensure_elasticsearch_index(index_name: str):
    """Create or update Elasticsearch index with proper mappings for tender data"""
    if not await es_client.indices.exists(index=index_name):
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
        await es_client.indices.create(
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
        await es_client.indices.put_mapping(
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
        self.subject_embedding_tool = EmbeddingTool(config.subject_pinecone_config) if not config.skip_pinecone and config.subject_pinecone_config else None
        self.es_index_name = config.elasticsearch_index
        self.tender_source = tender_source
        self.tender_adapter = tender_adapter or GenericTenderAdapter()
        self.chunker = TextChunker(ChunkingConfig(chunk_size=400, chunk_overlap=100))
        # Ensure Elasticsearch index is ready if not skipped
        # if not config.skip_elasticsearch:
        #     ensure_elasticsearch_index(self.es_index_name)

    async def process_tenders(self, extraction_request: ExtractionRequest) -> Dict:
        """Process tenders by extracting and inserting into both Pinecone and Elasticsearch"""
        logging.info("Starting tender extraction and insertion process...")
        extraction_result = await self.tender_source.execute(extraction_request.dict())

        all_tenders = extraction_result["tenders"]
        logging.info(f"Extracted {len(all_tenders)} tenders")

        # Track tenders with empty and non-empty tender_subject
        tenders_with_empty_subject = []
        tenders_with_subject = []
        
        for tender in all_tenders:
            if not hasattr(tender, 'tender_subject') or not tender.tender_subject:
                tenders_with_empty_subject.append(tender.details_url)
            else:
                tenders_with_subject.append(tender.details_url)

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
                },
                "tender_subject_stats": {
                    "total_tenders": 0,
                    "tenders_with_subject": 0,
                    "tenders_without_subject": 0,
                    "tenders_with_empty_subject": []
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
            "elasticsearch_result": elasticsearch_result,
            "tender_subject_stats": {
                "total_tenders": len(all_tenders),
                "tenders_with_subject": len(tenders_with_subject),
                "tenders_without_subject": len(tenders_with_empty_subject),
                "tenders_with_empty_subject": tenders_with_empty_subject
            }
        }
    
    async def _process_for_pinecone(self, all_tenders: List[Tender]) -> Dict:
        """Process tenders for Pinecone vector embeddings"""
        logging.info("Preparing items for embedding...")
        embedding_items = []
        subject_embedding_items = []
        
        for tender in all_tenders:
            tender_id = tender.details_url
            if self.check_if_exists(tender_id):
                logging.info(f"Skipping tender with ID {tender_id} since it already exists in Pinecone.")
                continue

            # Process main tender data
            item = self.tender_adapter.prepare_embedding_item(tender)
            
            # Validate input text
            if not isinstance(item["input"], str) or len(item["input"].strip()) == 0:
                logging.error(f"Invalid input text for tender {item['id']}, skipping.")
                continue

            embedding_items.append(item)

            # Process tender subject if available and subject embedding is configured
            pprint.pprint(tender)
            if hasattr(tender, 'tender_subject') and tender.tender_subject and self.subject_embedding_tool:
                logging.info(f"Processing tender subject for tender {tender_id}")
                # Split subject text into chunks (similar to upload_file_content)
                
                for i, chunk in enumerate(safe_chunk_text(tender.tender_subject, self.chunker, self.subject_embedding_tool.config.embedding_model)):
                    subject_item = {
                        "input": chunk,
                        "metadata": {
                            "tender_id": tender_id,
                            "chunk_index": i,
                            "source": "tender_subject",
                            "source_type": tender.source_type,
                            "initiation_date": tender.initiation_date,
                            "text": chunk
                        },
                        "id": f"{tender_id}_subject_{i}"
                    }
                    subject_embedding_items.append(subject_item)
                    logging.debug(f"Created subject chunk {i+1} for tender {tender_id}")
            else:
                if not hasattr(tender, 'tender_subject'):
                    logging.debug(f"No tender_subject field found for tender {tender_id}")
                elif not tender.tender_subject:
                    logging.debug(f"Empty tender_subject for tender {tender_id}")
                elif not self.subject_embedding_tool:
                    logging.debug(f"Subject embedding tool not configured for tender {tender_id}")

        results = {
            "main": {
                "processed_count": 0,
                "total_items": 0,
                "failed_items": []
            },
            "subjects": {
                "processed_count": 0,
                "total_items": 0,
                "failed_items": []
            }
        }

        # Process main tender data
        if embedding_items:
            total_items = len(embedding_items)
            logging.info(f"Starting embedding process for {total_items} new tenders...")

            # Log some quick stats
            unique_ids = len({item['id'] for item in embedding_items})
            avg_length = sum(len(item["input"]) for item in embedding_items) / total_items
            logging.info(f"Number of unique IDs: {unique_ids}")
            logging.info(f"Average input text length: {avg_length:.2f}")

            results["main"] = await self.embedding_tool.embed_and_store_batch(items=embedding_items)
            logging.info(f"Main tender embedding completed: {results['main']['processed_count']}/{total_items} items processed")

        # Process subject data
        if subject_embedding_items and self.subject_embedding_tool:
            total_subject_items = len(subject_embedding_items)
            logging.info(f"Starting embedding process for {total_subject_items} subject chunks...")
            
            results["subjects"] = await self.subject_embedding_tool.embed_and_store_batch(items=subject_embedding_items)
            logging.info(f"Subject embedding completed: {results['subjects']['processed_count']}/{total_subject_items} chunks processed")
            
            if results["subjects"]["failed_items"]:
                logging.warning(f"Failed to process {len(results['subjects']['failed_items'])} subject chunks")

        return results
    
        
    async def _process_for_elasticsearch(self, all_tenders: List[Tender]) -> Dict:
        """Process tenders for Elasticsearch lexical search"""
        try:
            # Prepare documents for bulk ingestion
            actions = []
            for tender in all_tenders:
                # Skip existing tenders - use the same check as in Pinecone
                tender_id = tender.details_url
                if await self.check_if_elasticsearch_exists(tender_id):
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
                
                # Remove tender_subject from metadata
                if 'tender_subject' in tender_dict:
                    logging.info(f"Removing tender_subject from Elasticsearch metadata for tender {tender_id}")
                    del tender_dict['tender_subject']
                
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
                logging.info(f"Preparing ES document for tender {tender_id}: {doc}")
                
                actions.append({
                    "_index": self.es_index_name,
                    "_id": tender_id,  # Use same ID as in Pinecone for consistency
                    "_source": doc
                })
                
            if not actions:
                logging.info("No new tenders to store in Elasticsearch (all duplicates or invalid).")
                return {"stored_count": 0, "failed_count": 0}
            
            # Perform bulk ingestion
            success, failed = await helpers.async_bulk(es_client, actions, stats_only=True)
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
    
    async def check_if_elasticsearch_exists(self, tender_id: str) -> bool:
        """Check if tender with given ID already exists in Elasticsearch"""
        if self.config.skip_elasticsearch:
            return False
            
        logging.info(f"Checking if tender with ID {tender_id} already exists in Elasticsearch...")
        
        try:
            result = await es_client.exists(index=self.es_index_name, id=tender_id)
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