import asyncio
from asyncio.log import logger
from datetime import datetime, time
import json
import logging
import re
from typing import List
from xml.dom import ValidationErr

from minerva.core.helpers.deep_search import find_file_id_by_filename, make_citation_list_from_relevant_files, stream_deep_search_and_llm_response, stream_llm_lookup_response_with_animation, stream_llm_response_with_animation
from minerva.core.utils.conversation_title_generator import generate_and_update_conversation_title
import json_repair
from minerva.core.models.conversation import Citation, Message
from minerva.core.services.deep_search_service import deep_search, get_generate_full_response_request_data
from minerva.core.services.llm_logic import ask_llm_logic, llm_rag_search_logic, rag_search_logic
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
from minerva.core.helpers.file_upload import handle_file_upload
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.middleware.token_tracking import check_token_limit
from minerva.core.models.request.ai import AskAiRequest, CancelRun, LLMConfig, LLMRAGRequest, LLMSearchRequest, LLMSearchResponse, ListRuns, SearchResult, SubmitToolResponse
from minerva.core.models.user import User
from minerva.core.database.database import db
from minerva.core.services.llm_providers.anthropic import AnthropicLLM
from minerva.core.services.llm_providers.openai import OpenAILLM
from minerva.core.services.response_stream import StreamManager, event_stream
from minerva.core.models.file import File as FileModel
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from openai import OpenAI
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, HTTPException
from bson import ObjectId
from pydantic import BaseModel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

load_dotenv()

openai = OpenAI()
router = APIRouter()

@router.post("/ask-assistant")
async def ask_ai(
    background_tasks: BackgroundTasks,
    request: AskAiRequest = Depends(AskAiRequest.as_form),
    files: List[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    try:
        user, error_response = await check_token_limit(current_user)
        if error_response:
            return error_response
            
        current_user = user 
        
        assistant = await db['assistants'].find_one({"_id": ObjectId(request.assistant_id)})
        if not assistant:
            return JSONResponse(status_code=404, content={"detail": "Assistant not found"})

        conversation = await db['conversations'].find_one({"thread_id": request.thread_id})
        if not conversation:
            return JSONResponse(status_code=404, content={"detail": "Conversation not found"})

        if request.run_id:
            run = openai.beta.threads.runs.retrieve(
                thread_id=request.thread_id,
                run_id=request.run_id
            )
            if run.status in ['queued', 'in_progress', 'requires_action']:
                openai.beta.threads.runs.cancel(
                    thread_id=request.thread_id,
                    run_id=request.run_id,
                )

        attachments = []
        if files:
            for file in files:
                attachment = await handle_file_upload(
                    file=file,
                    owner_id=str(current_user.id),
                    db=db,
                    assistant_id=request.assistant_id
                )
                attachments.append(attachment)

        attachment_string = ""
        if (attachments):
         attachment_string = " 【Note: file is attached】"

        openai.beta.threads.messages.create(
            thread_id=request.thread_id,
            role="user",
            content=request.prompt + attachment_string,
            attachments=attachments if attachments else None
        )

        await db['conversations'].update_one(
            {"thread_id": request.thread_id},
            {
                "$set": {
                    "last_updated": datetime.utcnow()
                }
            }
        )

        messages = openai.beta.threads.messages.list(thread_id=request.thread_id)
        if len(messages.data) == 1:
            background_tasks.add_task(generate_and_update_title, request.thread_id, request.prompt)

        assistant_tools = [{"type": "file_search"}]

        if request.stream:
            stream_response = openai.beta.threads.runs.create(
                thread_id=request.thread_id,
                assistant_id=assistant.get('openai_assistant_id', ''),
                instructions=assistant.get('system_prompt', ''),
                temperature=0,
                stream=True,
                tools=assistant_tools,
                include=["step_details.tool_calls[*].file_search.results[*].content"]
            )
            stream_manager = StreamManager(background_tasks)
            return StreamingResponse(
                event_stream(stream_response, str(current_user.id), stream_manager), 
                media_type="text/event-stream"
            )
        else:
            run = openai.beta.threads.runs.create_and_poll(
                thread_id=request.thread_id,
                assistant_id=assistant.get('openai_assistant_id', ''),
                model=request.model,
                temperature=0,
                tools=assistant_tools
            )
            if run.status == 'completed':
                messages = openai.beta.threads.messages.list(
                    thread_id=request.thread_id
                )

                assistant_messages = [msg for msg in messages.data if msg.role == 'assistant']
                if assistant_messages:
                    response_text = assistant_messages[-1].content[0].text.value
                    regex_pattern = r"【.*?】"
                    cleaned_string = re.sub(regex_pattern, '', response_text)
                    return {"response": cleaned_string}
                else:
                    return JSONResponse(status_code=422, content={"detail": "No assistant response found"})
            else:
                return JSONResponse(status_code=422, content={"detail": "AI processing not completed", "status": run.status})

    except Exception as e:
        print(e)
        return JSONResponse(status_code=500, content={"detail": str(e)})
    


def generate_and_update_title(thread_id, prompt):
    completion = openai.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {"role": "system", "content": "You generate brief titles that are on point for the conversations."},
            {"role": "user", "content": "Conversation content: '" + prompt + "' \nRespond with the concise title for it:"}
        ]
    )
    
    title = completion.choices[0].message.content.strip().replace('"', '').replace("'", '')
    
    db['conversations'].update_one(
        {"thread_id": thread_id},
        {
            "$set": {
                "title": title
            }
        }
    )



@router.post("/submit-tool-response")
async def submit_tool_response(request: SubmitToolResponse):
    try:
        print(f"Received request: {request.dict()}")
        stream = openai.beta.threads.runs.submit_tool_outputs(
            thread_id=request.thread_id,
            run_id=request.run_id,
            tool_outputs=request.tool_outputs,
            stream=True
        )
        return StreamingResponse(event_stream(stream), media_type="text/event-stream")
    except ValidationErr as e:
        print(f"Validation error: {e.json()}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/runs")
async def get_runs(request: ListRuns):
    try:
        runs = openai.beta.threads.runs.list(
            request.thread_id
        )
        return runs
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.delete("/run")
async def cancel_run(request: CancelRun):
    try:
        run = openai.beta.threads.runs.cancel(
            thread_id=request.thread_id,
            run_id=request.run_id
        )
        return run
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.post("/llm-rag-example")
async def llm_rag_route(request: LLMRAGRequest):
    result = await llm_rag_search_logic(request)
    if isinstance(result, LLMSearchResponse):
        return result
    else:
        # If the result is a streaming generator, wrap it in a StreamingResponse
        return StreamingResponse(
            result,
            media_type="text/event-stream",
            headers={"Content-Type": "text/event-stream; charset=utf-8"}
        )


@router.post("/ask-llm")
async def ask_llm_route(request: LLMSearchRequest):
    result = await ask_llm_logic(request)
    if isinstance(result, LLMSearchResponse):
        return result
    else:
        return StreamingResponse(
            result,
            media_type="text/event-stream",
            headers={"Content-Type": "text/event-stream; charset=utf-8"}
        )

class ProcessFilesRequest(BaseModel):
    user_query: str
    files: List[FileModel]

# @router.post("/deep-search")
# async def deep_search_route(request: ProcessFilesRequest):
#     result = await deep_search(request.user_query, request.files)
#     return {"result": result}


class ConversationLLMRequest(BaseModel):
    conversation_id: str
    assistant_id: str
    query: str
    stream: bool = True
    
@router.post("/send-project-message")
async def send_project_message(
    background_tasks: BackgroundTasks,
    request: ConversationLLMRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        # Step 1: Fetch conversation and up to 6 latest messages
        conversation = await db['conversations'].find_one({"_id": ObjectId(request.conversation_id)})
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = sorted(
            [Message(**msg) for msg in conversation.get('messages', [])],
            key=lambda x: x.created_at
        )[-6:]
        
        # Step 2: Save the query as a message
        query_message = Message(
            id=ObjectId(),
            role="user",
            content=request.query,
            created_at=datetime.utcnow()
        )
        await db['conversations'].update_one(
            {"_id": ObjectId(request.conversation_id)},
            {"$push": {"messages": query_message.model_dump()}}
        )

        if not conversation.get('messages', []):
            background_tasks.add_task(
                generate_and_update_conversation_title, 
                request.conversation_id, 
                request.query
        )

        assistant = await db['assistants'].find_one({"_id": ObjectId(request.assistant_id)})
        if not assistant:
            return JSONResponse(status_code=404, content={"detail": "Assistant not found"})
        
        tender_pinecone_id = assistant.get('tender_pinecone_id', None)
        uploaded_files_pinecone_id = assistant.get('uploaded_files_pinecone_id', None)
        pinecone_config_dict = assistant.get('pinecone_config', None)
        pinecone_config = QueryConfig(
            index_name=pinecone_config_dict['index_name'],
            namespace=pinecone_config_dict['namespace'],
            embedding_model=pinecone_config_dict['embedding_model']
        )

        llm_config = LLMConfig(
               provider= "openai",
               model= "gpt-4.1",
               temperature= 0,
               max_tokens= 30000,
               system_message= """
               You are an expert in analyzing user's questions and a chatbot in tenders analysis app.
               In this app there are files related to some public tender.
               Decide which function to call to best answer to user question. 
               You don't have direct access to files, you must decide only by analysing user's question. 
               You can call some of these two functions that will search files for best answer to question
               or you can just respond if user question doesn't require files searching.
               Analyse functions desciptions.
               Call deepsearch only if user query sounds like it could be answer fully using intensive files search.
               You should respond in structure format way like this:
               {
                    "name": "..." (function name: none/lookup/deepsearch)
                    "response: "..." (your response if no function call or "" if function call)
               }
               
               """,
               stream=request.stream
        )



        # Step 3: Prepare messages list for first LLM call with search tool
        message_list = [{"role": msg.role, "content": msg.content} for msg in messages] + [
            {"role": "user", "content": request.query}
        ]
        
        # Step 4: First LLM call with search tool

        OPENAI_TOOLS = [{
            "type": "function",
            "function": {
                "name": "lookup",
                "description": "Search files using normal vector search. Fast and good only for responding to needle in a haystack type of questions. Do not use it if question refers to something like enumeration or some info that could not be easliy and correcly identified by vector search",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "required": [],
                    "additionalProperties": False
                },
                "strict": True
            }
        },
        {
            "type": "function",
            "function": {
                "name": "deepsearch",
                "description": "Search files using advanced files search. Slow and good for responding to advanced questions that may need broader context",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "required": [],
                    "additionalProperties": False
                },
                "strict": True
            }
        }]

        ANTHROPIC_TOOLS = [
            {
                "name": "lookup",
                "description": "Search files using normal vector search. Fast and good for responding to needle in a haystack type of questions",
                "input_schema": {
                    "type": "object",
                    "properties": {
                    },
                    "required": [],
                }
            },
            {
                "name": "deepsearch",
                "description": "Search files using advanced files search. Slow and good for responding to advanced questions that may need broader context",
                "input_schema": {
                    "type": "object",
                    "properties": {
                    },
                    "required": []
                }
            }]

        tools = OPENAI_TOOLS if llm_config.provider == "openai" else ANTHROPIC_TOOLS
        llm = (OpenAILLM if llm_config.provider == "openai" else AnthropicLLM)(
            model=llm_config.model,
            stream=False,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            tools=tools,
            instructions=llm_config.system_message,
            response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "function_call_response",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "response": {"type": "string"},
                                },
                                "required": ["name", "response"],
                                "additionalProperties": False
                            }
                        }
                    }
        )

        initial_response = await llm.generate_response([{"role": "user", "content": request.query}])
        initial_response = initial_response.content

        retry_with_deepsearch = False

        if not isinstance(initial_response, dict):
            initial_response = json_repair.repair_json(str(initial_response), return_objects=True, ensure_ascii=False)


        if initial_response['name'] == "none" or str(initial_response).find("none") != -1:
            return StreamingResponse(
                        stream_llm_response_with_animation(initial_response, request.conversation_id),
                        media_type="text/event-stream",
                        headers={"Content-Type": "text/event-stream; charset=utf-8"}
                    )

        if initial_response['name'] == "lookup" or str(initial_response).find("lookup") != -1:

            messages1, vector_search_res1 = await rag_search_logic(request.query, pinecone_config, tender_pinecone_id)

            messages2, vector_search_res2 = await rag_search_logic(request.query, pinecone_config, uploaded_files_pinecone_id)

            messages = messages1 + messages2
            vector_search_res = vector_search_res1 + vector_search_res2

            llm_cls = OpenAILLM if llm_config.provider == "openai" else AnthropicLLM
            llm = llm_cls(
                model=llm_config.model,
                stream=False,
                temperature=llm_config.temperature,
                max_tokens=16000,
                instructions="""Answer to this question based on provided context.
                    If there is no info in provided context say that in your response, answer based on you knowledge only if user ask
                    Based on the context provided, identify which files contained information relevant to generating your answer and list ONLY their filenames.
                    Return your answer as a JSON object with the following structure:
                    {
                    "response": "<full answer text>",
                    "relevant_files": [
                        {
                            "filename": "<filename_of_relevant_file>"
                        },
                        ...
                    ]
                    }
                """,
                response_format= {
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
                                            "filename": {"type": "string"}
                                            # Citations removed
                                        },
                                        "required": ["filename"], # Only filename required
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["response", "relevant_files"],
                            "additionalProperties": False
                        }
                    }
                }
            )

            message_list.extend(messages)

            response = await llm.generate_response(message_list)
            response = response.content

            if not llm_config.stream:
                # Non-streaming response: return a complete response object
                llm_response = response if isinstance(response, str) else ""

                dict_response =  json_repair.repair_json(llm_response, return_objects=True, ensure_ascii=False)

                # --- Build citations list using vector_search_res and LLM filenames ---
                llm_filenames = {
                    item.get("filename") for item in dict_response.get("relevant_files", [])
                    if isinstance(item, dict) and item.get("filename")
                }

                filename_to_id_map: dict[str, str | None] = {}
                citations_list: list[Citation] = []

                for search_res in vector_search_res:
                    filename = search_res.source
                    if not filename or filename not in llm_filenames:
                        continue  # Skip if filename not relevant per LLM

                    # Cache file_id lookups
                    if filename not in filename_to_id_map:
                        file_id = await find_file_id_by_filename(filename)
                        filename_to_id_map[filename] = file_id
                    else:
                        file_id = filename_to_id_map[filename]

                    citations_list.append(
                        Citation(
                            content=search_res.text,
                            filename=filename,
                            file_id=file_id
                        )
                    )

                assistant_message = Message(
                    id=ObjectId(),
                    role="assistant",
                    content=dict_response['response'],
                    created_at=datetime.utcnow(),
                    citations=citations_list
                )
                await db['conversations'].update_one(
                    {"_id": ObjectId(request.conversation_id)},
                    {"$push": {"messages": assistant_message.model_dump()}}
                )
                await db['conversations'].update_one(
                    {"_id": ObjectId(request.conversation_id)},
                    {"$set": {"last_updated": datetime.utcnow()}}
                )
                # --- End of new citation logic --- 

                return LLMSearchResponse(
                        llm_response=llm_response,
                        vector_search_results=vector_search_res,
                        llm_provider=llm_config.provider,
                        llm_model=llm_config.model
                    )
            else:
                llm_analyze_response_config = LLMConfig(
                    provider= "openai",
                    model= "gpt-4.1",
                    temperature= 0.6,
                    max_tokens= 30000,
                    system_message= """
                    You should analyze prompt.
                    If you detect that in prompt there is info about no information found in files or 
                    other signs that this prompt could be not useful as a response to user return deepsearch.
                    If you think that prompt is good and it is ready to send to user return user
                    You should respond in structure format way like this:
                    {
                            "name": "..." (user/deepsearch)
                    }
                    
                    """,
                    stream=False
                )

                llm = OpenAILLM(
                    model=llm_analyze_response_config.model,
                    stream=False,
                    temperature=llm_analyze_response_config.temperature,
                    max_tokens=llm_analyze_response_config.max_tokens,
                    tools=[],
                    instructions=llm_analyze_response_config.system_message,
                    response_format={
                                "type": "json_schema",
                                "json_schema": {
                                    "name": "function_call_response",
                                    "strict": True,
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                        },
                                        "required": ["name"],
                                        "additionalProperties": False
                                    }
                                }
                            }
                )

                initial_response = await llm.generate_response([{"role": "user", "content": response}])
                initial_response = initial_response.content

                if not isinstance(initial_response, dict):
                    initial_response = json_repair.repair_json(str(initial_response), return_objects=True, ensure_ascii=False)

                if initial_response['name'] == "deepsearch" or str(initial_response).find("deepsearch") != -1:
                    retry_with_deepsearch = True
                else:
                    return StreamingResponse(
                        # Pass vector_search_res to the streaming function
                        stream_llm_lookup_response_with_animation(response, request.conversation_id, vector_search_res),
                        media_type="text/event-stream",
                        headers={"Content-Type": "text/event-stream; charset=utf-8"}
                    )

        if initial_response['name'] == "deepsearch" or str(initial_response).find("deepsearch") != -1 or retry_with_deepsearch:

            conversation = await db['conversations'].find_one({"_id": ObjectId(request.conversation_id)})
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            assistant_id = conversation.get("assistant_id")

            folder = await db["folders"].find_one({
                "owner_id": str(current_user.id),
                "assistant_id": assistant_id,
                "name": "Home",
                "parent_folder_id": None
            })

            files = await db["files"].find({"parent_folder_id": str(folder.get("_id"))}).to_list(length=None)
            print(files)
            model_files = [FileModel(**file) for file in files]

            if not llm_config.stream:
                files_citations_responses = await deep_search(request.query, model_files, llm_config.stream)
                print(f'files citations: {files_citations_responses}')
                request_data = await get_generate_full_response_request_data(request.query, files_citations_responses)

                llm = OpenAILLM(
                        model=request_data.llm.model,
                        stream=request_data.llm.stream,
                        temperature=request_data.llm.temperature,
                        max_tokens=request_data.llm.max_tokens,
                        tools=request_data.llm.tools, 
                        instructions=request_data.llm.system_message,
                        response_format=request_data.llm.response_format
                )

                message = [{"role": "user", "content": request_data.query}]

                message_list.extend(message)

                response = await llm.generate_response(message_list)
                response = response.content
                print(response)
                dict_response = json_repair.repair_json(response, return_objects=True, ensure_ascii=False)

                # --- Add missing message saving logic --- 
                assistant_message = Message(
                    id=ObjectId(),
                    role="assistant",
                    content=dict_response["response"],
                    created_at=datetime.utcnow(),
                    citations=await make_citation_list_from_relevant_files(
                        dict_response["relevant_files"],
                        files_citations_responses
                    )
                )
                await db['conversations'].update_one(
                    {"_id": ObjectId(request.conversation_id)},
                    {"$push": {"messages": assistant_message.model_dump()}}
                )
                await db["conversations"].update_one(
                    {"_id": ObjectId(request.conversation_id)},
                    {"$set": {"last_updated": datetime.utcnow()}}
                )
                # --- End of missing logic --- 

                return LLMSearchResponse(
                        llm_response=response,
                        vector_search_results=[],
                        llm_provider=llm_config.provider,
                        llm_model=llm_config.model
                    )
            
            else:
                print(request, message_list)
                return StreamingResponse(
                    stream_deep_search_and_llm_response(request, model_files, llm_config, message_list),
                    media_type="text/event-stream",
                    headers={"Content-Type": "text/event-stream; charset=utf-8"}
                )
        else:
            raise HTTPException(status_code=500, detail=f"LLM didn't called any function! {initial_response}")
        

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/admin/migrate-messages-add-id")
async def migrate_add_id_to_embedded_messages():
    """
    Migration endpoint to ensure every message in every conversation has an 'id' field (ObjectId),
    and removes any legacy '_id' fields from messages.
    """
    updated_conversations = 0
    updated_messages = 0

    async for convo in db["conversations"].find({}):
        messages = convo.get("messages", [])
        changed = False

        for msg in messages:
            # If legacy '_id' exists but no 'id', migrate it
            if 'id' not in msg:
                if '_id' in msg:
                    msg['id'] = msg['_id']
                    del msg['_id']
                    changed = True
                    updated_messages += 1
                else:
                    # No id at all, assign a new one
                    msg['id'] = ObjectId()
                    changed = True
                    updated_messages += 1
            else:
                # Remove any straggler '_id' fields
                if '_id' in msg:
                    del msg['_id']
                    changed = True

        if changed:
            await db["conversations"].update_one(
                {"_id": convo["_id"]},
                {"$set": {"messages": messages}}
            )
            updated_conversations += 1

    return {
        "status": "success",
        "updated_conversations": updated_conversations,
        "updated_messages": updated_messages
    }