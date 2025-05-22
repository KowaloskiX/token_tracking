import asyncio
from asyncio.log import logger
import json
from typing import List
from minerva.core.models.request.ai import SearchResult
from minerva.core.services.llm_providers.openai import OpenAILLM
from minerva.core.services.deep_search_service import deep_search, get_generate_full_response_request_data
from minerva.core.database.database import db
from minerva.core.models.conversation import Citation, Message
import json_repair
from datetime import datetime, time
from bson import ObjectId

async def find_file_id_by_filename(filename):
    """Find a file ID by its filename."""
    try:
        file = await db["files"].find_one({"filename": filename})
        if file:
            return str(file["_id"])
        return None
    except Exception as e:
        logger.error(f"Error finding file ID for filename {filename}: {str(e)}")
        return None


def make_citation_list(relevant_files):
    """
    Create citation list from relevant files, now including file_id.
    """
    logger.info("Creating citation list from relevant files")
    citations_list = []
    try:
        # Store filename to file_id mappings to avoid repeated lookups
        filename_to_id_map = {}
        
        for file_item in relevant_files:
            if not isinstance(file_item, dict):
                logger.warning(f"Unexpected file item type: {type(file_item)}, value: {file_item}")
                continue
                
            file_citations = file_item.get("citations", [])
            filename = file_item.get("filename")
            if not filename:
                logger.warning(f"Missing filename in file item: {file_item}")
                continue
                
            # Try to get file_id directly from the item first – it is the only
            # reliable way to disambiguate files that share the same filename.
            file_id = file_item.get("file_id")

            # If we *still* do not have a file_id we skip this citation to avoid
            # accidentally linking to a file that belongs to a different assistant.
            if not file_id:
                logger.warning(
                    "Skipping citations for '%s' because file_id is missing (potential duplicate filename).",
                    filename
                )
                continue

            for cite in file_citations:
                citations_list.append(Citation(
                    content=cite, 
                    filename=filename,
                    file_id=file_id
                ))
                
        logger.info(f"Created {len(citations_list)} citations")
        return citations_list
    except Exception as e:
        logger.error(f"Error creating citation list: {str(e)}", exc_info=True)
        return []
    
def make_citation_list_sync(relevant_files):
    """
    Create citation list from relevant files, now including file_id.
    This is a synchronous version for non-async contexts.
    """
    logger.info("Creating citation list from relevant files (sync)")
    citations_list = []
    try:
        for file_item in relevant_files:
            if not isinstance(file_item, dict):
                logger.warning(f"Unexpected file item type: {type(file_item)}, value: {file_item}")
                continue
                
            file_citations = file_item.get("citations", [])
            filename = file_item.get("filename")
            file_id = file_item.get("file_id")  # Try to get the file_id directly
            
            if not filename:
                logger.warning(f"Missing filename in file item: {file_item}")
                continue
                
            # Skip when file_id is missing to avoid mismatching assistants
            if not file_id:
                logger.warning(
                    "Skipping citations for '%s' because file_id is missing (potential duplicate filename).",
                    filename
                )
                continue

            for cite in file_citations:
                citations_list.append(Citation(
                    content=cite, 
                    filename=filename,
                    file_id=file_id
                ))
                
        logger.info(f"Created {len(citations_list)} citations")
        return citations_list
    except Exception as e:
        logger.error(f"Error creating citation list: {str(e)}", exc_info=True)
        return []

async def make_citation_list_from_relevant_files(relevant_files, files_citations_responses):
    logger.info("Creating citation list from relevant files and citations responses")
    citations_list = []
    try:
        # Extract valid filenames from the final LLM response's relevant_files list
        valid_filenames = []
        if isinstance(relevant_files, list):
            for item in relevant_files:
                if isinstance(item, dict):
                    filename = item.get('filename')
                    if filename:
                        valid_filenames.append(filename)
        logger.info(f"Found {len(valid_filenames)} valid filenames from final response: {valid_filenames}")
        
        # Process the citations data from the deep search results
        if not isinstance(files_citations_responses, list):
            logger.error(f"Expected files_citations_responses to be a list, but got {type(files_citations_responses)}")
            return []

        # Create a cache of filename to file_id mappings to avoid repeated DB lookups
        filename_to_id_map = {}

        for file_result_list in files_citations_responses: # Iterate outer list (results per file task)
            # Skip if the task resulted in an exception
            if isinstance(file_result_list, Exception):
                logger.warning(f"Skipping exception result: {file_result_list}")
                continue
            
            # Ensure the result for a file is a list (as returned by file_deep_search)
            if not isinstance(file_result_list, list):
                logger.warning(f"Unexpected file_result_list type: {type(file_result_list)}, value: {file_result_list}")
                continue
                
            # Iterate inner list (results per chunk within a file)
            for citation_group in file_result_list:
                if not isinstance(citation_group, dict):
                    logger.warning(f"Unexpected citation_group type: {type(citation_group)}, value: {citation_group}")
                    continue
                    
                filename = citation_group.get('filename')
                if not filename:
                    logger.warning(f"Missing filename in citation_group: {citation_group}")
                    continue
                    
                # Only include citations if the filename was deemed relevant by the final LLM
                # AND the deep search actually found citations for it.
                if filename in valid_filenames:
                    # Prefer file_id provided directly by deep_search task (it is the most reliable)
                    file_id = citation_group.get("file_id")

                    # If no file_id is present we skip to avoid mismatching files across assistants.
                    if not file_id:
                        logger.warning(
                            "Skipping citations for '%s' because file_id is missing (potential duplicate filename).",
                            filename
                        )
                        continue

                    citations = citation_group.get('citations', [])
                    if not isinstance(citations, list):
                        logger.warning(f"Unexpected citations type for file {filename}: {type(citations)}, value: {citations}")
                        continue
                        
                    for content in citations:
                        if not isinstance(content, str):
                            continue
                        if content.strip().lower() == "no information":
                            continue

                        logger.debug(
                            "Citation added – file: %s, first 120 chars: %s",
                            filename,
                            content.replace("\n", " ")[:120]
                        )
                        citations_list.append(
                            Citation(content=content, filename=filename, file_id=file_id)
                        )
        
        logger.info(f"Created {len(citations_list)} citations from relevant files")
        return citations_list
    except Exception as e:
        logger.error(f"Error creating citation list from relevant files: {str(e)}", exc_info=True)
        return []


async def stream_llm_response_with_structured_output_and_save_to_db(response, conversation_id, files_citations_responses):
    logger.info(f"[{conversation_id}] Starting to stream LLM response with structured output")
    full_content = ""
    phase = "start"
    response_escape = False
    response_buffer = []

    try:
        # Send initial status to frontend that we're generating the response
        yield f"data: {json.dumps({'type': 'status', 'message': 'Opracowuję znalezione informacje i formułuję odpowiedź...'})}\n\n"
        
        # --- Stream the main text response (Existing logic) ---
        async for chunk in response:
            if chunk["type"] == "text":
                full_content += chunk["content"]
                # --- Logic to parse and yield text chunks (Existing) ---
                if phase == "start":
                    if full_content.startswith('{"response":"'):
                        phase = "streaming_content"
                        remaining = full_content[len('{"response":"'):]
                        response_escape = False
                        response_buffer = []
                        for char in remaining:
                            if response_escape:
                                # Handle escape sequences
                                if char == '"': response_buffer.append('"')
                                elif char == '\\': response_buffer.append('\\')
                                elif char == '/': response_buffer.append('/')
                                elif char == 'b': response_buffer.append('\b')
                                elif char == 'f': response_buffer.append('\f')
                                elif char == 'n': response_buffer.append('\n')
                                elif char == 'r': response_buffer.append('\r')
                                elif char == 't': response_buffer.append('\t')
                                else: response_buffer.append(char)
                                response_escape = False
                            elif char == '\\':
                                response_escape = True
                            elif char == '"':
                                if response_buffer:
                                    content = ''.join(response_buffer)
                                    yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                                    response_buffer = []
                                phase = "post_response"
                                break
                            else:
                                response_buffer.append(char)
                        if phase == "streaming_content" and response_buffer:
                            content = ''.join(response_buffer)
                            yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                            response_buffer = []
                elif phase == "streaming_content":
                    for char in chunk["content"]:
                        if response_escape:
                           # Handle escape sequences (same as above)
                            if char == '"': response_buffer.append('"')
                            elif char == '\\': response_buffer.append('\\')
                            elif char == '/': response_buffer.append('/')
                            elif char == 'b': response_buffer.append('\b')
                            elif char == 'f': response_buffer.append('\f')
                            elif char == 'n': response_buffer.append('\n')
                            elif char == 'r': response_buffer.append('\r')
                            elif char == 't': response_buffer.append('\t')
                            else: response_buffer.append(char)
                            response_escape = False
                        elif char == '\\':
                            response_escape = True
                        elif char == '"':
                            if response_buffer:
                                content = ''.join(response_buffer)
                                yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                                response_buffer = []
                            phase = "post_response"
                            break
                        else:
                            response_buffer.append(char)
                    if phase == "streaming_content" and response_buffer:
                        content = ''.join(response_buffer)
                        yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                        response_buffer = []
                elif phase == "post_response":
                    pass # Just accumulate rest of the content
            # --- End of Text Streaming Logic ---
            elif chunk["type"] == "function_call":
                # Handle function calls if necessary (existing logic)
                yield f"data: {json.dumps({'type': 'function_call', 'name': chunk['name'], 'arguments': chunk['arguments']})}\n\n"

        logger.info(f"[{conversation_id}] Text stream finished. Processing full content.")
        dict_response = {}
        try:
            dict_response = json_repair.repair_json(full_content, return_objects=True, ensure_ascii=False)
            logger.info(f"[{conversation_id}] Successfully parsed full LLM response content.")
        except Exception as parse_err:
            logger.error(f"[{conversation_id}] Failed to parse full LLM response content: {parse_err}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to parse final LLM response structure: {parse_err}'})}\n\n"
            raise

        # Prepare the final citation list (used for DB save later)
        # Ensure the asynchronous citation list builder is awaited
        citations_list = await make_citation_list_from_relevant_files(
            dict_response.get("relevant_files", []),
            files_citations_responses
        )
        logger.info(f"[{conversation_id}] Prepared {len(citations_list)} total citations for DB.")

        # --- NEW: Extract Unique Files (filename + file_id) for Frontend ---
        unique_files = []
        seen_file_ids = set()
        for c in citations_list:
            if c.file_id and c.file_id not in seen_file_ids:
                unique_files.append({"filename": c.filename, "file_id": c.file_id})
                seen_file_ids.add(c.file_id)
        total_files = len(unique_files)
        logger.info(f"[{conversation_id}] Extracted {total_files} unique files to send to frontend.")
        # --- End NEW ---

        # --- NEW: Stream citations with full contents ---
        if citations_list:
            try:
                citations_json = json.dumps({'type': 'file_citation', 'citations': [c.model_dump() for c in citations_list]})
                yield f"data: {citations_json}\n\n"
                logger.info(f"[{conversation_id}] Sent 'file_citation' event with {len(citations_list)} citations.")
            except Exception as e:
                logger.error(f"[{conversation_id}] Error sending 'file_citation' event: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to stream citations: {e}'})}\n\n"
        # --- MODIFIED: Send unique files individually ---
        if total_files > 0:
            # 1. Send Start Event (using files count)
            start_event = {'type': 'final_filenames_start', 'total_filenames': total_files}
            try:
                start_json = json.dumps(start_event)
                yield f"data: {start_json}\n\n"
                logger.info(f"[{conversation_id}] Sent 'final_filenames_start' event (Total: {total_files}).")
            except Exception as e:
                logger.error(f"[{conversation_id}] Error sending 'final_filenames_start': {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to start filename stream: {e}'})}\n\n"

            # 2. Send Each Unique File Item
            for i, file in enumerate(unique_files):
                filename_item_event = {
                    'type': 'filename_item',
                    'filename': file['filename'],
                    'file_id': file['file_id']
                }
                try:
                    item_json = json.dumps(filename_item_event)
                    yield f"data: {item_json}\n\n"
                    if i == 0 or (i + 1) % 10 == 0 or i + 1 == total_files:
                         logger.debug(f"[{conversation_id}] Sent filename_item {i+1}/{total_files}: {file}")
                except Exception as e:
                    logger.error(f"[{conversation_id}] Error sending filename_item {i+1}/{total_files} ('{file['filename']}'): {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'filename_item_error', 'index': i, 'filename': file['filename'], 'file_id': file['file_id'], 'error': str(e)})}\n\n"

            # 3. Send End Event
            end_event = {'type': 'final_filenames_end'}
            try:
                end_json = json.dumps(end_event)
                yield f"data: {end_json}\n\n"
                logger.info(f"[{conversation_id}] Sent 'final_filenames_end' event.")
            except Exception as e:
                 logger.error(f"[{conversation_id}] Error sending 'final_filenames_end': {e}", exc_info=True)
                 yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to end filename stream: {e}'})}\n\n"

        else:
             logger.info(f"[{conversation_id}] No unique filenames to send.")
        # --- End of sending unique filenames ---

        # --- Save the assistant message to DB (Uses original citations_list) ---
        logger.info(f"[{conversation_id}] Creating and saving assistant message to DB (using full citations list).")
        assistant_message = Message(
            id=ObjectId(),
            role="assistant",
            content=dict_response.get("response", ""),
            created_at=datetime.utcnow(),
            citations=citations_list
        )
        await db['conversations'].update_one(
            {"_id": ObjectId(conversation_id)},
            {"$push": {"messages": assistant_message.model_dump()}}
        )
        await db['conversations'].update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {"last_updated": datetime.utcnow()}}
        )
        logger.info(f"[{conversation_id}] Successfully saved assistant message.")

        # Yield the message ID after saving
        yield f"data: {json.dumps({'type': 'message_id', 'id': str(assistant_message.id)})}\n\n"
        logger.info(f"[{conversation_id}] Sent 'message_id' event: {str(assistant_message.id)}")

    except Exception as e:
        logger.error(f"[{conversation_id}] Error in stream_llm_response_with_structured_output_and_save_to_db: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': f'Stream processing error: {str(e)}'})}\\n\\n"

async def stream_deep_search_and_llm_response(request, model_files, llm_config, message_list):
    logger.info("Starting stream_deep_search_and_llm_response")
    try:
        # Inform the frontend that deep search is starting
        logger.info("Sending initial status message")
        yield f"data: {json.dumps({'type': 'status', 'message': 'Rozpoczynam wyszukiwanie w plikach...'})}\n\n"

        # Create a queue to receive progress events from deep_search
        progress_queue: asyncio.Queue[dict] = asyncio.Queue()

        async def progress_callback(event: dict):
            """Callback passed to deep_search to emit progress events via the queue."""
            try:
                await progress_queue.put(event)
            except Exception:
                logger.exception("Failed to enqueue progress event from deep_search")

        logger.info("Starting deep search")

        # Kick-off deep_search as background task so we can forward progress events concurrently
        deep_search_task = asyncio.create_task(
            deep_search(
                request.query,
                model_files,
                is_streaming=llm_config.stream,
                progress_callback=progress_callback
            )
        )

        # Continuously stream progress events while deep_search runs
        import time
        heartbeat_count = 0
        last_heartbeat = time.monotonic()
        last_status = time.monotonic()
        waiting_time = 0
        status_messages = [
            "Analizuję dokumenty. Proszę o cierpliwość...",
            "Przeszukuję dokumenty. To może chwilę potrwać...",
            "Trwa przeszukiwanie plików. Ta operacja może potrwać kilkadziesiąt sekund...",
            "Nadal pracuję nad analizą dokumentów...",
            "Wyszukiwanie w toku. Zbliżam się do końca analizy..."
        ]
        
        while not deep_search_task.done():
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=2.0)
                if event:
                    yield f"data: {json.dumps(event)}\n\n"
                    # Reset waiting time when we get a real event
                    waiting_time = 0
                    last_status = time.monotonic()
            except asyncio.TimeoutError:
                now = time.monotonic()
                # Send a heartbeat every 10 seconds without an event
                if now - last_heartbeat > 10:
                    heartbeat_count += 1
                    yield f"data: {json.dumps({'type': 'heartbeat', 'count': heartbeat_count})}\n\n"
                    last_heartbeat = now
                    
                    # If we haven't had a status update in 20 seconds, send a "still working" message
                    waiting_time = now - last_status
                    if waiting_time > 20:
                        # Select a message based on how long we've been waiting
                        message_index = min(int(waiting_time / 20) - 1, len(status_messages) - 1)
                        status_message = status_messages[message_index]
                        
                        yield f"data: {json.dumps({'type': 'status', 'message': status_message})}\n\n"
                        last_status = now

        # Flush any remaining events in the queue after task completion
        while not progress_queue.empty():
            event = await progress_queue.get()
            yield f"data: {json.dumps(event)}\n\n"

        # Await the result (propagate errors if any)
        files_citations_responses = await deep_search_task

        logger.debug(f"Deep search returned citations structure: {type(files_citations_responses)}, length: {len(files_citations_responses) if isinstance(files_citations_responses, list) else 'N/A'}")
        if isinstance(files_citations_responses, list) and len(files_citations_responses) > 0:
             logger.debug(f"First item type: {type(files_citations_responses[0])}")
        
        logger.info(f"Deep search completed, preparing final response prompt.")
        
         # Filter out exceptions before generating the request data for the final response
        successful_responses = [r for r in files_citations_responses if not isinstance(r, Exception)]
        if not successful_responses:
             logger.warning("Deep search did not yield any successful citation results.")
             # Decide how to proceed: maybe yield an error or a message indicating no results?
             yield f"data: {json.dumps({'type': 'error', 'message': 'Deep search failed to find relevant information.'})}\n\n"
             return # Stop processing

        # Send a status update that we're generating the final response
        yield f"data: {json.dumps({'type': 'status', 'message': 'Analiza dokumentów zakończona. Generuję odpowiedź...'})}\n\n"

        logger.info("Generating full response request data")
        request_data = await get_generate_full_response_request_data(request.query, successful_responses, stream=True)
        logger.info("Request data generated")
        
        llm = OpenAILLM(
            model=request_data.llm.model,
            stream=request_data.llm.stream,
            temperature=request_data.llm.temperature,
            max_tokens=request_data.llm.max_tokens,
            tools=request_data.llm.tools, 
            instructions=request_data.llm.system_message,
            response_format=request_data.llm.response_format
        )
        logger.info("LLM initialized")

        message = [{"role": "user", "content": request_data.query}]
        # Avoid extending message_list if it's not needed or passed correctly
        # message_list.extend(message)
        logger.info("Messages prepared for final LLM call")

        logger.info("Starting final LLM response generation")
        # Use the prepared message list for the final call
        response = await llm.generate_response(message) 
        logger.info("Final LLM response stream received")

        logger.info("Starting to stream response with structured output")
        # Pass the original, potentially mixed list (results + exceptions) for full context if needed downstream
        async for chunk in stream_llm_response_with_structured_output_and_save_to_db(response, request.conversation_id, files_citations_responses):
            logger.debug(f"Yielding chunk: {chunk[:100]}...")  # Log first 100 chars of chunk
            yield chunk
        logger.info("Finished streaming response")
    except Exception as e:
        logger.error(f"Error in stream_deep_search_and_llm_response: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        raise



    
async def stream_llm_lookup_response_with_animation(full_content, conversation_id = None, vector_search_res: List[SearchResult] = []):
    # First, accumulate the full generated response
    dict_response = json_repair.repair_json(full_content, return_objects=True, ensure_ascii=False)
    
    # --- New logic to build citations list from vector search results --- 
    logger.info(f"[{conversation_id}] Building citations from lookup results.")
    citations_list = []
    relevant_files_from_llm = dict_response.get("relevant_files", [])
    llm_filenames = {item['filename'] for item in relevant_files_from_llm if isinstance(item, dict) and 'filename' in item}
    logger.info(f"[{conversation_id}] LLM identified relevant filenames: {llm_filenames}")
    
    filename_to_id_map = {}
    # Pre-populate filename_to_id map from vector results to potentially reduce DB calls
    all_filenames_in_results = {res.source for res in vector_search_res if res.source}
    for filename in all_filenames_in_results:
        # Look up file ID only if needed (not already found for this filename)
        if filename not in filename_to_id_map:
            file_id = await find_file_id_by_filename(filename)
            if file_id:
                 filename_to_id_map[filename] = file_id
            else:
                 logger.warning(f"[{conversation_id}] Could not find file_id for filename: {filename}")

    for search_result in vector_search_res:
        filename = search_result.source
        # Only include citations from files the LLM deemed relevant
        if filename and filename in llm_filenames:
            file_id = filename_to_id_map.get(filename)
            citations_list.append(Citation(
                content=search_result.text, 
                filename=filename,
                file_id=file_id # May be None if lookup failed
            ))
            
    logger.info(f"[{conversation_id}] Built {len(citations_list)} citations from lookup results.")
    # --- End of new citation logic --- 

    response_text = dict_response["response"]

    # Set parameters for the animation
    chunk_size = 20  # Number of characters to send per chunk
    delay = 0.05      # Delay (in seconds) between chunks

    # Stream the response text in chunks with a delay for a typing animation
    for i in range(0, len(response_text), chunk_size):
        part = response_text[i:i+chunk_size]
        yield f"data: {json.dumps({'type': 'text', 'content': part})}\n\n"
        await asyncio.sleep(delay)

    # Finally, send the file citations as a separate event
    yield f"data: {json.dumps({'type': 'file_citation', 'citations': [x.model_dump() for x in citations_list]})}\n\n"

    assistant_message = Message(
        id=ObjectId(),
        role="assistant",
        content=dict_response["response"],
        created_at=datetime.utcnow(),
        citations=citations_list,
    )

    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$push": {"messages": assistant_message.model_dump()}},
    )
    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"last_updated": datetime.utcnow()}},
    )

    # Yield the message ID after saving
    yield f"data: {json.dumps({'type': 'message_id', 'id': str(assistant_message.id)})}\n\n"
    logger.info(f"[{conversation_id}] Sent 'message_id' event for lookup: {str(assistant_message.id)}")



async def stream_llm_response_with_animation(dict_response, conversation_id):
    # First, accumulate the full generated response
    response_text = dict_response["response"]

    # Set parameters for the animation
    chunk_size = 20  # Number of characters to send per chunk
    delay = 0.05      # Delay (in seconds) between chunks

    # Stream the response text in chunks with a delay for a typing animation
    for i in range(0, len(response_text), chunk_size):
        part = response_text[i:i+chunk_size]
        yield f"data: {json.dumps({'type': 'text', 'content': part})}\n\n"
        await asyncio.sleep(delay)

    assistant_message = Message(
        id=ObjectId(),
        role="assistant",
        content=dict_response["response"],
        created_at=datetime.utcnow(),
        citations=[],
    )

    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$push": {"messages": assistant_message.model_dump()}},
    )
    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"last_updated": datetime.utcnow()}},
    )

    # Yield the message ID after saving
    yield f"data: {json.dumps({'type': 'message_id', 'id': str(assistant_message.id)})}\n\n"
    logger.info(f"[{conversation_id}] Sent 'message_id' event for simple response: {str(assistant_message.id)}")