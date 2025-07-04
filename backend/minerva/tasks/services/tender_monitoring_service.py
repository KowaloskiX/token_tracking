from asyncio import Protocol
import asyncio
from datetime import datetime
import logging
import os
from typing import Dict, List, Optional, Tuple

from bson import ObjectId
import json_repair
from minerva.core.helpers.s3_upload import upload_file_to_s3
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from minerva.core.database.database import db
from minerva.core.models.file import File
from minerva.core.models.request.ai import LLMSearchRequest
from minerva.core.services.deep_search_service import extract_text_from_files
from minerva.core.services.llm_logic import ask_llm_logic
from minerva.core.services.tender_notification_service import notify_tender_updates
from minerva.tasks.services.analyze_tender_files import RAGManager
from minerva.tasks.sources.source_types import TenderSourceType
import tiktoken


class TenderSource(Protocol):
    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult],
        date_str: Optional[str]
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        pass

class TenderMonitoringService:
    
    def __init__(self, tender_source: TenderSource, tender_source_type: TenderSourceType, is_date_str: bool = False):
        self.tender_source = tender_source
        self.tender_source_type = tender_source_type
        self.is_date_str = is_date_str

    async def process_tenders_monitoring(self, date_str: str) -> list[Dict]:

        cursor = db["tender_analysis_results"].find({"source": self.tender_source_type.value, "status": "active" })
        raw_tenders = await cursor.to_list(length=None)
        if not raw_tenders:
            logging.info(f"No {self.tender_source_type} TenderAnalysisResults found.")
            # return {"status": "no_tenders", "updates": []}
            return []
        
        tenders_to_monitor = [TenderAnalysisResult.parse_obj(doc) for doc in raw_tenders]
        logging.info(f"Loaded {len(tenders_to_monitor)} Tenders to monitor for {self.tender_source_type}.")

        try:
            if self.is_date_str:
                updates_dict = await self.tender_source.find_updates(tenders_to_monitor, date_str=date_str)
            else:
                updates_dict = await self.tender_source.find_updates(tenders_to_monitor)
        except Exception as e:
            logging.error(f"Error calling find_updates: {e}")
            # return {"status": "error", "error": str(e)}
            return []


        updates_summary = []
        now_utc = datetime.utcnow()

        if not updates_dict or len(updates_dict) == 0:
            return []

        try:
            for tender_id_str, new_files in updates_dict.items():
                if not new_files:
                    continue

                tender_obj = await db["tender_analysis_results"].find_one({"_id": ObjectId(tender_id_str)})
                if not tender_obj:
                    logging.warning(f"TenderAnalysisResult {tender_id_str} not found in DB. Skipping.")
                    continue

                tar = TenderAnalysisResult.parse_obj(tender_obj)
                logging.info(f"Processing {len(new_files)} new files for T.A.Result {tender_id_str}")


                rag_manager = RAGManager(tar.pinecone_config.index_name, tar.pinecone_config.namespace, tar.pinecone_config.embedding_model, tar.tender_pinecone_id)

                # We'll keep track of the new file references to push into DB
                new_tender_files = []

                for (file_content, filename, url, preview_chars, original_bytes) in new_files:
                    try:
                        file_pinecone_config = await rag_manager.upload_file_content(file_content, filename)


                        bytes_to_upload: bytes | bytearray = original_bytes if isinstance(original_bytes, (bytes, bytearray)) and original_bytes is not None else file_content
                        blob_url = upload_file_to_s3(filename, bytes_to_upload)
                        _, file_extension = os.path.splitext(filename)
                        new_tender_files.append(
                            File(filename=filename, 
                                 url=url, 
                                 blob_url=blob_url, 
                                 preview_chars=preview_chars, 
                                 type=file_extension, 
                                 bytes=len(file_content) if file_content else None, 
                                 file_pinecone_config=file_pinecone_config,
                                 created_at=datetime.utcnow(),
                                 owner_id=str(tar.user_id))
                        )

                        logging.info(f"Uploaded new file {filename} to OpenAI for tender {tender_id_str}.")
                    except Exception as e:
                        logging.error(f"Failed uploading file {filename} to OpenAI: {str(e)}")
                        continue

                if not new_tender_files:
                    logging.info(f"No successfully uploaded files for {tender_id_str}, skipping DB update.")
                    continue

                try:
                    files_with_text_content = await extract_text_from_files(new_tender_files)
                    logging.info(f"Extracted text from {len(files_with_text_content)} files for tender {tender_id_str}.")
                except Exception as e:
                    logging.error(f"Failed to extract text from files for tender {tender_id_str}: {str(e)}")
                    files_with_text_content = []

                file_summaries = []
                if files_with_text_content:
                    batch_size = 5
                    semaphore = asyncio.Semaphore(batch_size)
                    
                    async def process_one_file_summary(file_with_text):
                        async with semaphore:
                            return await self.summarize_tender_changes(
                                file_with_text["filename"], 
                                file_with_text["file_text"]
                            )
                    
                    tasks = [process_one_file_summary(file_with_text) for file_with_text in files_with_text_content]
                    
                    try:
                        file_summaries = await asyncio.gather(*tasks)
                        logging.info(f"Generated summaries for {len(file_summaries)} files for tender {tender_id_str}.")
                    except Exception as e:
                        logging.error(f"Failed to generate summaries for tender {tender_id_str}: {str(e)}")
                        file_summaries = []
                
                overall_summary = ""
                if file_summaries:
                    try:
                        overall_summary = await self.generate_overall_summary(file_summaries, tender_id_str)
                        logging.info(f"Generated overall summary for tender {tender_id_str}.")
                    except Exception as e:
                        logging.error(f"Failed to generate overall summary for tender {tender_id_str}: {str(e)}")

                # (B) Create a new doc in `tender_analysis_updates`
                update_doc = {
                    "tender_analysis_result_id": tar.id,
                    "updated_files": [file.dict() for file in new_tender_files],  # storing just the names
                    "update_date": now_utc,
                    "update_link": tar.tender_url,
                    "file_summaries": file_summaries if file_summaries else [],
                    "overall_summary": overall_summary
                }
                
                insert_result = await db["tender_analysis_updates"].insert_one(update_doc)

                new_update_id = insert_result.inserted_id

                db["tender_analysis_results"].update_one(
                {"_id": ObjectId(tender_id_str)},
                {
                    "$push": {"updates": new_update_id},
                    "$set": {
                    "updated_at": now_utc
                    }
                }
                )

                logging.info(f"DB updated for tender {tender_id_str}. Created update doc {new_update_id}.")

                # Record summary
                updates_summary.append({
                    "tender_id": tender_id_str,
                    "update_id": str(new_update_id),
                    "files_uploaded": [f.filename for f in new_tender_files],
                    "file_summaries": file_summaries if file_summaries else [],
                    "overall_summary": overall_summary
                })
        finally:
            print("")
        
        # Send notifications to users for the updates
        try:
            if updates_summary:
                notification_results = await notify_tender_updates(updates_summary)
                logger.info(f"Notification results: {notification_results}")
        except Exception as e:
            logger.error(f"Failed to send notifications for tender updates: {str(e)}")
        
        return updates_summary
    
    @staticmethod
    async def summarize_tender_changes(filename: str, file_text: str) -> Dict:
        """
        Summarize changes in a tender document using LLM.
        Handles large files by chunking them if needed.
        """
        system_message = """
        You will get a tender document with its name (in polish language).
        Closely analyze this document and summarize the changes or updates it contains.
        Focus on any new requirements, deadlines, specifications, or other important changes.
        If the document doesn't contain any clear changes, summarize its main points.
        Provide a concise summary.
        Answer in polish language.
        """
        
        TOTAL_CONTEXT_TOKENS = 20_000
        RESERVED_TOKENS = 500  # Reserve tokens for system message and other text
        max_tokens_for_text = TOTAL_CONTEXT_TOKENS - RESERVED_TOKENS
        
        # Set overlap for better context continuity between chunks
        OVERLAP_TOKENS = 100
        
        # Initialize tokenizer
        encoding = tiktoken.encoding_for_model("gpt-4")
        
        # Tokenize the file content
        tokens = encoding.encode(file_text)
        total_tokens = len(tokens)
        
        # Function to split text based on tokens with overlap
        def split_text_by_tokens(text, max_tokens, encoding, overlap=50):
            tokens = encoding.encode(text)
            chunks = []
            start = 0
            while start < len(tokens):
                end = start + max_tokens
                chunk_tokens = tokens[start:end]
                chunk_text = encoding.decode(chunk_tokens)
                chunks.append(chunk_text)
                start += max_tokens - overlap
            return chunks
        
        # Check if splitting is needed
        if total_tokens <= max_tokens_for_text:
            chunks = [file_text]
        else:
            chunks = split_text_by_tokens(file_text, max_tokens_for_text, encoding, overlap=OVERLAP_TOKENS)
        
        summaries = []
        # Process each chunk separately
        for i, chunk in enumerate(chunks):
            prompt = f"""
            document_name: {filename}
            text_document: {chunk}
            """
            request_data = LLMSearchRequest(
                query=prompt,
                llm={
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "temperature": 0.6,
                    "max_tokens": 30000,
                    "system_message": system_message,
                    "stream": False,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "tender_changes_summary",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"}
                                },
                                "required": ["summary"],
                                "additionalProperties": False
                            }
                        }
                    }
                }
            )
            
            response = await ask_llm_logic(request_data)
            parsed_output = json_repair.repair_json(response.llm_response, return_objects=True, ensure_ascii=False)
            
            summaries.append(parsed_output["summary"])
        
        # Combine summaries from all chunks
        combined_summary = " ".join(summaries)
        
        # If we have multiple chunks, use LLM again to consolidate them
        if len(summaries) > 1:
            consolidation_prompt = f"""
            document_name: {filename}
            partial_summaries: {combined_summary}
            """
            consolidation_request_data = LLMSearchRequest(
                query=consolidation_prompt,
                llm={
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "temperature": 0.6,
                    "max_tokens": 30000,
                    "system_message": """
                    You will get a document name and a set of partial summaries.
                    These partial summaries are from different parts of the same document.
                    Please consolidate these summaries into a single coherent summary.
                    Focus on changes or updates in the tender document.
                    Answer in polish language.
                    """,
                    "stream": False,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "consolidated_summary",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"}
                                },
                                "required": ["summary"],
                                "additionalProperties": False
                            }
                        }
                    }
                }
            )
            consolidation_response = await ask_llm_logic(consolidation_request_data)
            consolidated_summary = json_repair.repair_json(consolidation_response.llm_response, return_objects=True, ensure_ascii=False)
            return {
                "filename": filename,
                "summary": consolidated_summary["summary"]
            }
        
        return {
            "filename": filename,
            "summary": combined_summary
        }

    @staticmethod
    async def generate_overall_summary(file_summaries: List[Dict], tender_id: str) -> str:
        """
        Generate an overall summary of changes in a tender based on individual file summaries.
        """
        system_message = """
        You will get a list of summaries from different files related to a tender.
        Please generate an overall summary of the changes or updates in the tender based on these file summaries.
        Focus on key changes, new requirements, deadlines, specifications, or other important updates.
        Provide a concise summary that captures the most important changes.
        Answer in polish language.
        """
        
        # Format file summaries for the prompt
        formatted_summaries = []
        for summary in file_summaries:
            formatted_summaries.append(f"Filename: {summary['filename']}\nSummary: {summary['summary']}")
        
        summaries_text = "\n\n".join(formatted_summaries)
        
        prompt = f"""
        tender_id: {tender_id}
        file_summaries:
        {summaries_text}
        """
        
        request_data = LLMSearchRequest(
            query=prompt,
            llm={
                "provider": "openai",
                "model": "gpt-4.1",
                "temperature": 0.6,
                "max_tokens": 30000,
                "system_message": system_message,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "overall_tender_summary",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "summary": {"type": "string"}
                            },
                            "required": ["summary"],
                            "additionalProperties": False
                        }
                    }
                }
            }
        )
        
        response = await ask_llm_logic(request_data)
        parsed_output = json_repair.repair_json(response.llm_response, return_objects=True, ensure_ascii=False)
        
        return parsed_output["summary"]