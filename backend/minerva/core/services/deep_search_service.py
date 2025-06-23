import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile
import aiofiles
import aiohttp
from fastapi import HTTPException
import httpx
import json_repair
from minerva.core.services.llm_providers.openai import OpenAILLM
import requests
import tiktoken
from minerva.api.routes.retrieval_routes import sanitize_id
from minerva.core.models.file import File
from minerva.core.models.request.ai import LLMSearchRequest
from minerva.core.services.llm_logic import ask_llm_logic
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
from typing import Callable, Awaitable, Optional

logger = logging.getLogger(__name__)

async def deep_search(
    user_query: str,
    files: list[File],
    messages_list: list[str] = None,
    is_streaming: bool = False,
    progress_callback: Optional[Callable[[dict], Awaitable[None]]] = None
):
    logger.info(f"Starting deep search for query: {user_query}")
    logger.info(f"Processing {len(files)} files")
    
    # continue with previous messages
    file_dict = {str(file_obj.id): file_obj for file_obj in files}
    logger.debug(f"Created file dictionary with {len(file_dict)} entries")

    try:
        logger.info("Getting relevant files for deep search...")
        matches = await get_relevant_files_for_deep_search(user_query, files)
        logger.info(f"Found {len(matches)} relevant files")
        
        matched_files = []
        for match in matches:
            file_obj = file_dict.get(match["id"])
            if file_obj:
                matched_files.append(file_obj)
                logger.debug(f"Matched file: {file_obj.filename}")
            else:
                logger.warning(f"Could not find file object for match ID: {match['id']}")

        # Provide early progress update – total files
        if progress_callback:
            try:
                await progress_callback({
                    "type": "status",
                    "message": f"Znalazłem {len(matches)} potencjalnie istotne pliki. Rozpoczynam ekstrakcję tekstu..."
                })
            except Exception:
                logger.exception("Failed to send progress callback for extraction start")

        logger.info("Extracting text from matched files...")
        files_with_text_content = await extract_text_from_files(matched_files)
        logger.info(f"Successfully extracted text from {len(files_with_text_content)} files")

        # Filter out any exceptions from text extraction before proceeding
        valid_files_with_text = []
        for item in files_with_text_content:
            if isinstance(item, Exception):
                logger.error(f"Skipping file with text extraction error: {str(item)}")
                continue
            valid_files_with_text.append(item)
        
        if not valid_files_with_text:
            logger.warning("No valid files with text content available after filtering exceptions")
            return [] if is_streaming else {"response": "No valid content could be extracted from the files.", "relevant_files": []}
        
        logger.info(f"Proceeding with {len(valid_files_with_text)} valid files after filtering exceptions")

        # Inform about the number of files that will be deeply searched
        total_valid_files = len(valid_files_with_text)
        if progress_callback:
            try:
                await progress_callback({
                    "type": "status",
                    "message": f"Dokładnie przejrzę {total_valid_files} plików..."
                })
            except Exception:
                logger.exception("Failed to send progress callback for deep search start")

        batch_size = 5
        semaphore = asyncio.Semaphore(batch_size)
        logger.debug(f"Using batch size of {batch_size} for processing")

        async def process_one_search(index: int, file_with_text_content):
            try:
                async with semaphore:
                    filename_local = file_with_text_content["filename"]

                    # Emit start status for this file
                    if progress_callback:
                        try:
                            await progress_callback({
                                "type": "status",
                                "message": f"[{index + 1}/{total_valid_files}] Analizuję plik: {filename_local}"
                            })
                        except Exception:
                            logger.exception("Failed to send progress callback for file start")

                    logger.debug(f"Processing deep search for file: {filename_local}")
                    result = await file_deep_search(
                        filename_local,
                        file_with_text_content["file_text"],
                        user_query,
                        progress_callback
                    )
                    logger.debug(f"Completed deep search for file: {filename_local}")
                    # Ensure we attach the file_id to every citation result so it can be used downstream
                    if isinstance(result, list):
                        for group in result:
                            if isinstance(group, dict):
                                group["file_id"] = file_with_text_content["file_id"]

                    # Emit completion status with citations found
                    if progress_callback:
                        try:
                            citations_found = 0
                            if isinstance(result, list):
                                for group in result:
                                    if isinstance(group, dict):
                                        citations_found += len(group.get("citations", []))

                            # Use correct grammatical form based on the number
                            if citations_found <= 4:
                                citation_text = f"{citations_found} relewantne informacje"
                            else:
                                citation_text = f"{citations_found} relewantnych informacji"

                            await progress_callback({
                                "type": "status",
                                "message": f"Zakończyłem analizę pliku: {filename_local}. Znalezłem {citation_text}."
                            })
                        except Exception:
                            logger.exception("Failed to send progress callback for file completion")

                    return result
            except Exception as e:
                logger.error(f"Error processing file {filename_local}: {str(e)}")
                # Ensure the exception includes filename for context if needed downstream
                e.filename = filename_local
                raise

        tasks = [process_one_search(idx, file_with_text_content) for idx, file_with_text_content in enumerate(valid_files_with_text)]
        logger.info(f"Created {len(tasks)} search tasks")

        logger.info("Starting parallel processing of search tasks...")
        files_citations_responses = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Completed all search tasks")

        # Check for any exceptions in the responses
        for i, response in enumerate(files_citations_responses):
            if isinstance(response, Exception):
                # Safely get the filename - it could be attached to the exception or we need to look it up
                # Only try to access files_with_text_content[i] if it's not an exception itself
                if hasattr(response, 'filename'):
                    filename = response.filename
                elif i < len(valid_files_with_text):
                    filename = valid_files_with_text[i].get("filename", "unknown")
                else:
                    filename = "unknown"
                logger.error(f"Task {i} (file: {filename}) failed with error: {str(response)}")
                # Keep the exception object for potential downstream handling, or replace with error dict
                # Convert exceptions to structured error objects for safer downstream handling
                files_citations_responses[i] = {"error": str(response), "filename": filename, "citations": []}

        logger.info("Preparing response based on streaming mode...")
        if is_streaming:
            logger.info("Streaming response requested, returning citation results")
            return files_citations_responses # Return the list of results/exceptions
        else:
            logger.info("Generating non-streaming response")
             # Filter out exceptions before passing to generate the final response prompt
            successful_responses = [r for r in files_citations_responses if not isinstance(r, Exception)]
            request_data = await get_generate_full_response_request_data(user_query, successful_responses)
            logger.info("Generated request data for full response")
            response = await ask_llm_logic(request_data)
            logger.info("Received response from LLM")
            # Handle potential errors during JSON repair
            try:
                parsed_output = json_repair.repair_json(response.llm_response, return_objects=True, ensure_ascii=False)
                logger.info("Successfully parsed LLM response")
                return parsed_output
            except Exception as json_e:
                logger.error(f"Failed to parse LLM response JSON: {json_e}")
                logger.error(f"Raw LLM response: {response.llm_response}")
                # Return an error structure or raise an exception
                raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {json_e}")

    except Exception as e:
        logger.error(f"Deep search failed with error: {str(e)}", exc_info=True)
        raise # Re-raise the exception after logging

async def extract_text_from_files(files: list[File]) -> list[dict[str, str]]:
    logger.info(f"Starting text extraction from {len(files)} files")
    
    # Create a temporary directory for downloads
    temp_dir = tempfile.mkdtemp()
    logger.debug(f"Created temporary directory: {temp_dir}")
    registry = ExtractorRegistry()

    files_with_text_content = []

    async def download_one_file(file: File):
        try:
            logger.debug(f"Processing file: {file.filename}")
            blob_url = file.blob_url
            if not blob_url:
                logger.error(f"No valid blob_url found in file object: {file.filename}")
                raise ValueError(f"No valid blob_url found in file object: {file.filename}")

            # Sanitize filename and define the temporary path
            sanitized_filename = sanitize_id(file.filename)
            temp_path = Path(temp_dir) / sanitized_filename
            logger.debug(f"Downloading file to: {temp_path}")

            # Asynchronously download the file using aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(blob_url) as response:
                    response.raise_for_status()
                    # Open the file asynchronously for writing
                    async with aiofiles.open(temp_path, mode="wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                await f.write(chunk)

            # Determine file extension and obtain the corresponding extractor
            extension = temp_path.suffix.lower() or '.doc'
            extractor = registry.get(extension)
            if not extractor:
                logger.error(f"No extractor registered for file type: {extension}")
                raise ValueError(f"No extractor registered for file type: {extension}")

            logger.debug(f"Extracting text from file: {file.filename}")
            # Run the synchronous text extraction in a thread to avoid blocking
            #
            if extension == ".docx":
                file_text = await asyncio.to_thread(extractor.extract_text_as_string, temp_path, True)
            else:
                file_text = await asyncio.to_thread(extractor.extract_text_as_string, temp_path)
            logger.debug(f"Successfully extracted text from: {file.filename}")

            return {
                "file_id": str(file.id),
                "filename": file.filename,
                "file_text": file_text
            }
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {str(e)}")
            raise

    batch_size = 5
    semaphore = asyncio.Semaphore(batch_size)

    async def process_one_file(file: File):
        try:
            async with semaphore:
                return await download_one_file(file)
        except Exception as e:
            logger.error(f"Error in process_one_file for {file.filename}: {str(e)}")
            raise
    
    tasks = [process_one_file(file) for file in files]
    logger.info(f"Created {len(tasks)} extraction tasks")

    try:
        files_with_text_content = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Completed text extraction for {len(files_with_text_content)} files")
    except Exception as e:
        logger.error(f"Error during text extraction: {str(e)}")
        raise

    # Clean up temporary directory
    if os.path.exists(temp_dir):
        try:
            for file in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except Exception as e:
                    logger.warning(f"Error removing temporary file {file}: {str(e)}")
            os.rmdir(temp_dir)
            logger.debug("Cleaned up temporary directory")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary directory: {str(e)}")

    return files_with_text_content

async def get_generate_full_response_request_data(user_query: str, citations_output: dict, stream = False):
    # Define a system message for the LLM.

    # Remove comments about citations as they are no longer requested here
    # along with the citations
    #     you used from each file. In response field do not include citations they should only be in citations list.
            #   "citations": [list of citations used]

    system_message = """
    You are a helpful assistant that provides a comprehensive answer to the user's query based on the provided citations.
    """
    
    # Build the prompt by including the user query and the full citations output.
    prompt = f"""
    The citations are given as a JSON object where each entry contains a list of citation strings and a filename.
    Please generate a full answer in user language if user prompt to the user_query.
    Based on the citations provided, identify which files contained information relevant to generating your answer and list ONLY their filenames and file_ids.
    Return your answer as a JSON object with the following structure:
    {{
      "response": "<full answer text>",
      "relevant_files": [
          {{
              "filename": "<filename_of_relevant_file>",
              "file_id": "<file_id_of_relevant_file>"
          }},
          ...
      ]
    }}
    Make sure that you always include both filename and file_id for each file in relevant_files.

    <USER_QUERY>{user_query}</USER_QUERY>

    <CITATIONS_OUTPUT>{json.dumps(citations_output, indent=2)}</CITATIONS_OUTPUT>
    """
    
    # Build the LLM request with the updated response format schema.
    request_data = LLMSearchRequest(
        query=prompt,
        llm={
            "provider": "openai",
            "model": "gpt-4.1",
            "temperature": 0.6,
            "max_tokens": 30000,
            "system_message": system_message,
            "stream": stream,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "full_answer_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "response": {"type": "string"},
                            "relevant_files": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "filename": {"type": "string"},
                                        "file_id": {"type": "string"}
                                    },
                                    "required": ["filename", "file_id"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["response", "relevant_files"],
                        "additionalProperties": False
                    }
                }
            }
        }
    )

    return request_data


async def file_deep_search(filename: str, file_text_content: str, user_query: str, progress_callback: Optional[Callable[[dict], Awaitable[None]]] = None):
    logger.info(f"Starting deep search for file: {filename}")
    system_message = """
        You will get USER_QUERY, DOCUMENT_TEXT containing the content of the document and DOCUMENT_NAME.
        Closely analyze this document content and check if there are any relevant mentions 
        that explicitly mention something related to user query. 
        Return EXACT quotes from the document.

        Important: If the document doesn't contain any information related to the question simply return "No information"
        Make sure that you respond in correct structure output format 
    """

    TOTAL_CONTEXT_TOKENS = 20_000
    RESERVED_TOKENS = 500  # Reserve tokens for system message and user query.
    max_tokens_for_text = TOTAL_CONTEXT_TOKENS - RESERVED_TOKENS
    OVERLAP_TOKENS = 100

    encoding = tiktoken.encoding_for_model("gpt-4")
    tokens = encoding.encode(file_text_content)
    total_tokens = len(tokens)

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

    if total_tokens <= max_tokens_for_text:
        chunks = [file_text_content]
    else:
        chunks = split_text_by_tokens(file_text_content, max_tokens_for_text, encoding, overlap=OVERLAP_TOKENS)

    results = []
    for i, chunk in enumerate(chunks):
        logger.debug(f"Processing chunk {i+1}/{len(chunks)} of file {filename}")
        
        # Send status update before starting the OpenAI call
        if progress_callback:
            await progress_callback({
                "type": "status",
                "message": f"Przetwarzam część {i+1}/{len(chunks)} pliku {filename} (może to potrwać chwilę)..."
            })
            
        prompt = f"""
        <USER_QUERY>{user_query}</USER_QUERY>
        <DOCUMENT_NAME>{filename}</DOCUMENT_NAME>
        <DOCUMENT_TEXT> 
            {chunk}
        </DOCUMENT_TEXT>
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
                        "name": "tender_matches_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "citations": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["citations"],
                            "additionalProperties": False
                        }
                    }
                }
            }
        )

        # Create a background task to send periodic updates during the long OpenAI call
        keep_alive_task = None
        
        async def send_keep_alive_updates():
            await asyncio.sleep(15)  # First update after 15 seconds
            iteration = 0
            while True:
                if progress_callback:
                    iteration += 1
                    # Alternate between different messages to show activity
                    if iteration % 3 == 0:
                        message = f"Nadal analizuję część {i+1}/{len(chunks)} pliku {filename}..."
                    elif iteration % 3 == 1:
                        message = f"Wciąż pracuję nad częścią {i+1}/{len(chunks)} pliku {filename}..."
                    else:
                        message = f"Kontynuuję analizę części {i+1}/{len(chunks)} pliku {filename}..."
                        
                    await progress_callback({
                        "type": "status",
                        "message": message
                    })
                await asyncio.sleep(10)  # Send update every 10 seconds
                
        try:
            # Start the keep-alive task before making the OpenAI call
            if progress_callback:
                keep_alive_task = asyncio.create_task(send_keep_alive_updates())
                
            # Make the potentially slow OpenAI call
            response = await ask_llm_logic(request_data)
            parsed_output = json_repair.repair_json(response.llm_response, return_objects=True, ensure_ascii=False)
            
            if not isinstance(parsed_output, dict):
                logger.warning(f"Unexpected response type for chunk {i+1}: {type(parsed_output)}")
                continue
                
            citations = parsed_output.get("citations", [])
            if not isinstance(citations, list):
                logger.warning(f"Unexpected citations type for chunk {i+1}: {type(citations)}")
                continue
                
            if citations:
                results.append({
                    "filename": filename,
                    "citations": citations
                })
                logger.debug(f"Found {len(citations)} citations in chunk {i+1}")
                
                # Send an update about found citations
                if progress_callback:
                    count_text = f"{len(citations)} cytatów" if len(citations) != 1 else "1 cytat"
                    await progress_callback({
                        "type": "status",
                        "message": f"Znalazłem {count_text} w części {i+1}/{len(chunks)} pliku {filename}"
                    })
        except Exception as e:
            logger.error(f"Error processing chunk {i+1}: {str(e)}")
            continue
        finally:
            # Always cancel the keep-alive task if it exists
            if keep_alive_task and not keep_alive_task.done():
                keep_alive_task.cancel()
                try:
                    await keep_alive_task
                except asyncio.CancelledError:
                    pass

    if not results:
        logger.info(f"No citations found in file: {filename}")
        return [{
            "filename": filename,
            "citations": []
        }]
        
    logger.info(f"Found total {sum(len(r['citations']) for r in results)} citations in file: {filename}")
    return results


async def get_relevant_files_for_deep_search(user_query: str, files: list[File]) -> list[dict[str, str]]:
    """
        returns:
        [
            {
                "id": "...",
                "filename": "..."
            },
            {
                "id": "...",
                "filename": "..."
            },
            ...
        ]

    """

    list_of_prev_chars = [
        {
            "id": str(file.id) if file.id else None,
            "filename": file.filename,
            "preview_chars": file.preview_chars
        }
        for file in files
    ]

    system_message = """
    You are a helpful assistant that gives advice on which files to search to get some info.
    You will be given a user_query and list containing files id, filenames and preview_chars from each file.
    Based on preview_chars decide which files are could be worthy to consider to search deeply.
    Return those files id and filenames as a structured output
    """

    prompt = f"""
    user_query: {user_query}

    list of files (id, preview_chars): 
    {list_of_prev_chars}

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
                        "name": "tender_matches_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "matches": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "filename": {"type": "string"}
                                        },
                                        "required": ["id", "filename"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["matches"],
                            "additionalProperties": False
                        }
                    }
                }
        }
    )

    response = await ask_llm_logic(request_data)

    parsed_output = json_repair.repair_json(response.llm_response, return_objects=True, ensure_ascii=False)

    return parsed_output['matches']
