import asyncio
from typing import Any, Dict, List, Optional
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Body, Query
from minerva.core.models.assistant import Assistant
from minerva.core.services.vectorstore.pinecone.query import QueryConfig
from pydantic import BaseModel
from bson import ObjectId
from openai import OpenAI
from minerva.core.database.database import db
from datetime import datetime

openai = OpenAI()
router = APIRouter()

class Tool(BaseModel):
    type: str
    config: Optional[Dict] = None

class AssistantCreate(BaseModel):
    name: str
    model: str
    owner_id: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    icon: Optional[str] = ""
    shared_with: Optional[List[dict]] = []
    tools: Optional[List[Tool]] = []
    temperature: Optional[float] = 0.5
    openai_assistant_id: Optional[str] = None  # New field
    tender_pinecone_id: Optional[str] = None
    pinecone_config: Optional[QueryConfig] = None
    org_id: Optional[str] = None

@router.post("/", response_model=Assistant)
async def create_assistant(assistant_data: AssistantCreate):
    try:
        openai_assistant_id = None
        vector_store_id = None
        final_tools = []

        tender_pinecone_id = None
        uploaded_files_pinecone_id = None
        pinecone_config = None

        # OUR RAG CASE  
        if assistant_data.pinecone_config:
            tender_pinecone_id = assistant_data.tender_pinecone_id
            uploaded_files_pinecone_id = f"{assistant_data.name}_{uuid4()}"
            pinecone_config = QueryConfig(
                index_name="files-rag-23-04-2025",
                namespace="",
                embedding_model="text-embedding-3-large",
            )

        # If OpenAI assistant ID is provided, verify it exists
        elif assistant_data.openai_assistant_id:
            try:
                existing_assistant = openai.beta.assistants.retrieve(
                    assistant_data.openai_assistant_id
                )
                openai_assistant_id = existing_assistant.id
                # Note: We'll need to create a new vector store since we don't have access to the original
                vector_store = openai.vector_stores.create(
                    name=f"{assistant_data.name}'s Store"
                )
                vector_store_id = vector_store.id
            except Exception as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"OpenAI Assistant with ID {assistant_data.openai_assistant_id} not found"
                )
        else:
            # Creating the vector store
            vector_store = openai.vector_stores.create(
                name=f"{assistant_data.name}'s Store"
            )
            vector_store_id = vector_store.id

            # Building the tools array and tool resources with vector store IDs
            final_tools = []
            tool_resources = {}

            # Define the file_search tool configuration
            file_search_tool = {
                "type": "file_search"
            }

            has_file_search = False
            for tool in assistant_data.tools:
                if tool.type == "file_search":
                    final_tools.append(file_search_tool)
                    tool_resources["file_search"] = {
                        "vector_store_ids": [vector_store_id]
                    }
                    has_file_search = True
                else:
                    final_tools.append({"type": tool.type})
            
            if not has_file_search:
                final_tools.append(file_search_tool)
                tool_resources["file_search"] = {
                    "vector_store_ids": [vector_store_id]
                }

            # Creating the assistant with the correct tool structure and resources
            response = openai.beta.assistants.create(
                name=assistant_data.name,
                model=assistant_data.model,
                instructions=assistant_data.system_prompt,
                tools=final_tools,
                tool_resources=tool_resources,
                # temperature=assistant_data.temperature,
            )
            openai_assistant_id = response.id

        current_time = datetime.utcnow()

        # If we're using an existing assistant, we'll get its tools configuration
        if assistant_data.openai_assistant_id:
            existing_assistant = openai.beta.assistants.retrieve(openai_assistant_id)
            final_tools = existing_assistant.tools

        assistant = Assistant(
            name=assistant_data.name,
            description=assistant_data.description,
            system_prompt=assistant_data.system_prompt,
            icon=assistant_data.icon,
            owner_id=assistant_data.owner_id,
            org_id=assistant_data.org_id,         # <-- Pass org_id here
            shared_with=assistant_data.shared_with,
            tools=final_tools,
            openai_assistant_id=openai_assistant_id,
            openai_vectorstore_id=vector_store_id,
            tender_pinecone_id=tender_pinecone_id,
            uploaded_files_pinecone_id=uploaded_files_pinecone_id,
            pinecone_config=pinecone_config,
            created_at=current_time
        )

        result = await db["assistants"].insert_one(assistant.dict(by_alias=True, exclude_unset=True))
        assistant.id = str(result.inserted_id)
        
        return assistant

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/assistant/{assistant_id}", response_model=Assistant)
async def get_assistant(assistant_id: str):
    assistant = await db["assistants"].find_one({"_id": ObjectId(assistant_id)})
    if assistant is None:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return Assistant(**assistant)

@router.put("/{assistant_id}", response_model=Assistant)
async def update_assistant(assistant_id: str, assistant: Assistant):
    result = await db["assistants"].update_one({"_id": ObjectId(assistant_id)}, {"$set": assistant.dict(by_alias=True)})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return assistant


async def get_all_subfolder_ids(folder_id: str, folder_collection) -> List[str]:
    """Recursively get all subfolder IDs for a given folder"""
    folder = await folder_collection.find_one({"_id": ObjectId(folder_id)})
    if not folder:
        return []
    
    all_subfolder_ids = [str(folder["_id"])]
    for subfolder_id in folder.get("subfolders", []):
        all_subfolder_ids.extend(await get_all_subfolder_ids(subfolder_id, folder_collection))
    
    return all_subfolder_ids



async def delete_openai_threads(thread_ids: List[str]) -> List[str]:
    """Delete multiple OpenAI threads and return any failed thread_ids"""
    failed_threads = []
    for thread_id in thread_ids:
        try:
            if thread_id:
                await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: openai.beta.threads.delete(thread_id)
                )
        except Exception as e:
            print(f"Failed to delete OpenAI thread {thread_id}: {str(e)}")
            failed_threads.append(thread_id)
    return failed_threads

async def delete_openai_files(file_ids: List[str]) -> List[str]:
    """Delete multiple OpenAI files and return any failed file_ids"""
    failed_files = []
    for file_id in file_ids:
        try:
            if file_id:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: openai.files.delete(file_id)
                )
        except Exception as e:
            print(f"Failed to delete OpenAI file {file_id}: {str(e)}")
            failed_files.append(file_id)
    return failed_files



@router.delete("/{assistant_id}")
async def delete_assistant(assistant_id: str):
    """
    Delete an assistant and all related data:
    1. Get all related conversations and delete their threads
    2. Get all related folders and their subfolders
    3. Get all files in these folders and delete them from OpenAI
    4. Delete all files and folders from database
    5. Delete the conversations and assistant
    """
    try:
        assistant_obj_id = ObjectId(assistant_id)
        
        # First get the assistant to retrieve the OpenAI assistant ID
        assistant = await db["assistants"].find_one({"_id": assistant_obj_id})
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")
            
        openai_assistant_id = assistant["openai_assistant_id"]
        
        # Get all related conversations and delete threads
        conversations = await db["conversations"].find(
            {"assistant_id": assistant_id}
        ).to_list(None)
        thread_ids = [conv["thread_id"] for conv in conversations if "thread_id" in conv]
        failed_threads = await delete_openai_threads(thread_ids)
        
        # Get all root folders for this assistant
        root_folders = await db["folders"].find(
            {"assistant_id": assistant_id, "parent_folder_id": None}
        ).to_list(None)
        
        # Get all subfolder IDs recursively
        all_folder_ids = []
        for folder in root_folders:
            folder_ids = await get_all_subfolder_ids(str(folder["_id"]), db["folders"])
            all_folder_ids.extend(folder_ids)
        
        # Get all files in these folders
        files = await db["files"].find({
            "parent_folder_id": {"$in": all_folder_ids}
        }).to_list(None)
        
        # Delete OpenAI files
        openai_file_ids = [file["openai_file_id"] for file in files if "openai_file_id" in file]
        failed_files = await delete_openai_files(openai_file_ids)
        
        # Delete files from database
        delete_files_result = await db["files"].delete_many({
            "parent_folder_id": {"$in": all_folder_ids}
        })
        
        # Delete all folders
        delete_folders_result = await db["folders"].delete_many({
            "_id": {"$in": [ObjectId(id) for id in all_folder_ids]}
        })
        
        # Delete conversations
        delete_conversations_result = await db["conversations"].delete_many({
            "assistant_id": assistant_id
        })
        
        # Delete the assistant from OpenAI using the correct OpenAI assistant ID

        if openai_assistant_id:
            try:
                openai.beta.assistants.delete(openai_assistant_id)
            except Exception as e:
                print(f"Error deleting OpenAI assistant {openai_assistant_id}: {str(e)}")
                # Continue with deletion even if OpenAI deletion fails
        
        # Delete the assistant from MongoDB
        delete_assistant_result = await db["assistants"].delete_one({
            "_id": assistant_obj_id
        })
        
        response = {
            "message": "Assistant deleted successfully",
            "details": {
                "assistant_deleted": True,
                "conversations_deleted": delete_conversations_result.deleted_count,
                "threads_processed": len(thread_ids),
                "threads_failed": len(failed_threads),
                "folders_deleted": delete_folders_result.deleted_count,
                "files_deleted": delete_files_result.deleted_count,
                "openai_files_processed": len(openai_file_ids),
                "openai_files_failed": len(failed_files)
            }
        }
        
        # Include failed items in response if any
        if failed_threads:
            response["details"]["failed_thread_ids"] = failed_threads
        if failed_files:
            response["details"]["failed_file_ids"] = failed_files
        
        return response
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        error_message = str(e)
        if "Invalid ObjectId" in error_message:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid assistant ID format: {assistant_id}"
            )
        
        print(f"Error deleting assistant {assistant_id}: {error_message}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while deleting the assistant and related data"
        )
    
    
class AssistantUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    icon: Optional[str] = None
    shared_with: Optional[List[dict]] = None
    tools: Optional[List[object]] = None
    temperature: Optional[float] = None

@router.patch("/{assistant_id}", response_model=Assistant)
async def patch_assistant(
    assistant_id: str,
    update_data: Dict[str, Any] = Body(...)
):
    try:
        existing_assistant = await db["assistants"].find_one({"_id": ObjectId(assistant_id)})
        if not existing_assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        openai_assistant_id = existing_assistant["openai_assistant_id"]

        openai_update_data = {}
        if "name" in update_data:
            openai_update_data["name"] = update_data["name"]
        if "model" in update_data:
            openai_update_data["model"] = update_data["model"]
        if "system_prompt" in update_data:
            openai_update_data["instructions"] = update_data["system_prompt"]
        if "tools" in update_data:
            openai_update_data["tools"] = update_data["tools"]
        if "temperature" in update_data:
            openai_update_data["temperature"] = update_data["temperature"]

        if openai_update_data:
            openai.beta.assistants.update(
                assistant_id=openai_assistant_id,
                **openai_update_data
            )

        update_result = await db["assistants"].update_one(
            {"_id": ObjectId(assistant_id)},
            {"$set": update_data}
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Assistant not found or no changes made")

        updated_assistant = await db["assistants"].find_one({"_id": ObjectId(assistant_id)})
        return Assistant(**updated_assistant)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/owner/{owner_id}", response_model=List[Assistant])
async def get_assistants_by_owner(owner_id: str, org_id: Optional[str] = None):
    try:
        # Build the query to handle cases based on org_id
        if org_id and org_id.strip():  # If org_id is not empty or None
            query = {
                "$or": [
                    {"owner_id": owner_id, "org_id": org_id},  # Organization-owned assistants created by the user
                    {"org_id": org_id},  # Organization-owned assistants created by others
                    {"owner_id": owner_id, "org_id": None},  # Personal assistants (no org_id)
                    {"owner_id": owner_id, "org_id": ""}   # Personal assistants (empty org_id)
                ]
            }
        else:  # If org_id is empty or None
            query = {
                "$or": [
                    {"owner_id": owner_id, "org_id": None},  # Personal assistants (no org_id)
                    {"owner_id": owner_id, "org_id": ""}   # Personal assistants (empty org_id)
                ]
            }

        assistants = await db["assistants"].find(query).to_list(None)
        if not assistants:
            return []
        return [Assistant(**assistant) for assistant in assistants]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/all", response_model=List[Assistant])
async def get_all_assistants(
    skip: int = Query(default=0, ge=0, description="Number of assistants to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of assistants to return")
):
    try:
        assistants = await db["assistants"].find() \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(None)
            
        if not assistants:
            return []
            
        return [Assistant(**assistant) for assistant in assistants]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch assistants: {str(e)}"
        )