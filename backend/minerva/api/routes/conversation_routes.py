from dataclasses import Field
from datetime import datetime
import re
from typing import Dict, Optional, List
import uuid
from fastapi import APIRouter, HTTPException, Depends
from minerva.core.database.database import db
from bson import ObjectId
from minerva.core.models.conversation import Citation, Conversation, Message
from pydantic import BaseModel
from openai import OpenAI
from pymongo import DESCENDING

router = APIRouter()
openai = OpenAI()

# Constants
PAGE_SIZE = 20

# Request and Response Models
class CreateConversationRequest(BaseModel):
    user_id: str
    assistant_id: str
    initial_message: Optional[str] = None
    our_rag: Optional[bool] = None
    org_id: Optional[str] = None  # New field for shared assistants

class PaginatedResponse(BaseModel):
    data: List[Conversation]
    page: int
    total_pages: int
    total_items: int
    has_next: bool
    has_previous: bool

# Helper function to convert ObjectIds to strings recursively
def convert_objectids(obj):
    if isinstance(obj, list):
        return [convert_objectids(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_objectids(v) for k, v in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj

@router.post("/new", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    try:
        thread_id = ""
        messages = []

        if not request.our_rag:
            thread = openai.beta.threads.create()
            
            if request.initial_message:
                openai.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=request.initial_message
                )
            thread_id = thread.id
        
        conversation = Conversation(
            assistant_id=request.assistant_id,
            user_id=request.user_id,
            messages=messages,
            thread_id=thread_id,
            title=request.initial_message[:40] + "..." if request.initial_message else "Chat"
        )
        
        await db["conversations"].insert_one(conversation.dict(by_alias=True))
        return conversation
        
    except Exception as e:
        print(f"Error creating conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create conversation: {str(e)}"
        )

@router.get("/assistant/{assistant_id}", response_model=PaginatedResponse)
async def get_conversations_by_assistant(
    assistant_id: str,
    page: int = 1
):
    try:
        if page < 1:
            page = 1
            
        skip = (page - 1) * PAGE_SIZE
        
        total_items = await db["conversations"].count_documents({"assistant_id": assistant_id})
        total_pages = (total_items + PAGE_SIZE - 1) // PAGE_SIZE 

        cursor = db["conversations"].find({"assistant_id": assistant_id})
        cursor = cursor.sort("last_updated", -1)
        cursor = cursor.skip(skip).limit(PAGE_SIZE)
        
        conversations = [Conversation(**conv) for conv in await cursor.to_list(length=PAGE_SIZE)]
        
        return PaginatedResponse(
            data=conversations,
            page=page,
            total_pages=total_pages,
            total_items=total_items,
            has_next=page < total_pages,
            has_previous=page > 1
        )
        
    except Exception as e:
        print(f"Error fetching conversations for assistant {assistant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch conversations: {str(e)}"
        )


def clean_message_content(content: str) -> str:
    """Remove text patterns matching 【.*?】 from the message content."""
    if not content:
        return content
    regex_pattern = r"【.*?】"
    return re.sub(regex_pattern, '', content)

@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    try:
        # Fetch conversation from the database
        conversation = await db['conversations'].find_one({"_id": ObjectId(conversation_id)})
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Fetch messages from OpenAI for the given thread_id
        thread_id = conversation.get("thread_id")
        if not thread_id:
            
            # handle messages from db, not from openai
            conversation_from_db = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
            conversation_from_db["messages"] = list(reversed(conversation_from_db["messages"]))
            if conversation_from_db:
                # Convert ObjectIds to strings before returning
                conversation_from_db = convert_objectids(conversation_from_db)
                return conversation_from_db

            raise HTTPException(status_code=400, detail="No thread_id or db record associated with this conversation")

        # Get messages for the specified thread
        thread_messages = openai.beta.threads.messages.list(thread_id=thread_id)
        
        # Format messages to include in the response
        messages = []
        for msg in thread_messages.data:
            message_content = ""
            attachments = []

            # Handle file attachments from user uploads
            if msg.attachments:
                for attachment in msg.attachments:
                    file = openai.files.retrieve(attachment.file_id)
                    attachments.append({
                        "file_id": attachment.file_id,
                        "name": file.filename
                    })

            # Process message content and annotations
            if msg.content and isinstance(msg.content, list) and len(msg.content) > 0:
                content_block = msg.content[0]
                if content_block.type == "text":
                    message_content = content_block.text.value
                    
                    # Handle file citations in the text
                    if hasattr(content_block.text, 'annotations'):
                        cited_files = set()  # Use set to avoid duplicates
                        for annotation in content_block.text.annotations:
                            if (hasattr(annotation, 'type') and 
                                annotation.type == 'file_citation' and 
                                annotation.file_citation.file_id not in cited_files):
                                
                                file = openai.files.retrieve(annotation.file_citation.file_id)
                                attachments.append({
                                    "file_id": annotation.file_citation.file_id,
                                    "name": file.filename
                                })
                                cited_files.add(annotation.file_citation.file_id)
                                
                                # Clean up citation markers from the text
                                message_content = message_content.replace(annotation.text, '')
                    
                    # Clean message content using regex pattern
                    message_content = clean_message_content(message_content)

            messages.append({
                "id": msg.id,
                "role": msg.role,
                "content": message_content,
                "created_at": msg.created_at,
                "attachments": attachments if attachments else None
            })

        # Build the conversation response
        conversation_response = {
            "_id": str(conversation["_id"]),
            "assistant_id": str(conversation["assistant_id"]) if "assistant_id" in conversation else None,
            "user_id": str(conversation["user_id"]) if "user_id" in conversation else None,
            "messages": messages,
            "thread_id": conversation.get("thread_id"),
            "title": conversation.get("title"),
            "last_updated": conversation.get("last_updated")
        }

        return conversation_response

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


class UpdateConversation(BaseModel):
    assistant_id: Optional[str] = None
    user_id: Optional[str] = None
    messages: Optional[List[Message]] = None
    thread_id: Optional[str] = None
    title: Optional[str ] = None
    
@router.put("/{conversation_id}", response_model=Conversation)
async def update_conversation(conversation_id: str, conversation: UpdateConversation):
    update_dict = {
            k: v for k, v in conversation.dict().items() 
            if v is not None
        }
    update_dict["last_updated"] = datetime.utcnow()
    result = await db["conversations"].update_one({"_id": ObjectId(conversation_id)}, 
                                                  {"$set": update_dict})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    updated_conversation = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    if updated_conversation:
        # Convert ObjectIds to strings before returning
        updated_conversation = convert_objectids(updated_conversation)
        return updated_conversation

@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    result = await db["conversations"].delete_one({"_id": ObjectId(conversation_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}



@router.post("/create-if-needed", response_model=Conversation)
async def check_or_create_conversation(request: CreateConversationRequest):
    """
    Check if the latest conversation for the given assistant (and org if provided)
    has messages. If not, return the existing empty conversation. Otherwise, create a new one.
    """
    try:
        # Build the query based on whether org_id is provided
        query = {"assistant_id": request.assistant_id}
        if request.org_id:
            query["org_id"] = request.org_id
        else:
            query["user_id"] = request.user_id

        latest_conversation = await db["conversations"].find_one(
            query,
            sort=[("last_updated", DESCENDING)]
        )

        if latest_conversation and not latest_conversation.get("messages"):
            return Conversation(
                _id=str(latest_conversation["_id"]),
                assistant_id=latest_conversation["assistant_id"],
                user_id=latest_conversation.get("user_id"),
                messages=latest_conversation["messages"],
                thread_id=latest_conversation["thread_id"],
                last_updated=latest_conversation["last_updated"].isoformat(),
                title=latest_conversation["title"],
                # Include org_id if exists
                org_id=latest_conversation.get("org_id")
            )

        # If no appropriate conversation exists, create one
        thread_id = ""
        if not request.our_rag:
            thread = openai.beta.threads.create()
            thread_id = thread.id
            
        conversation = Conversation(
            assistant_id=request.assistant_id,
            user_id=request.user_id,
            # Set org_id if this is a shared assistant
            org_id=request.org_id,
            messages=[],
            thread_id=thread_id,
            title="Chat"
        )
        
        await db["conversations"].insert_one(conversation.dict(by_alias=True))
        return conversation

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing conversation request: {str(e)}"
        )
    

class UpdateConversationTitleRequest(BaseModel):
    title: str

@router.patch("/{conversation_id}/update-title", response_model=Conversation)
async def update_conversation_title(conversation_id: str, request: UpdateConversationTitleRequest):
    """
    Update the title of a specific conversation.
    """
    try:
        # Update the conversation title in the database
        result = await db["conversations"].update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$set": {
                    "title": request.title,
                    "last_updated": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Fetch and return the updated conversation
        updated_conversation = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
        if updated_conversation:
            # Convert ObjectIds to strings before returning
            updated_conversation = convert_objectids(updated_conversation)
            return updated_conversation

    except Exception as e:
        print(f"Error updating conversation title: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update conversation title: {str(e)}"
        )

@router.get(
    "/{conv_id}/messages/{msg_id}/citations",
    response_model=list[Citation]
)
async def fetch_citations_for_message(conv_id: str, msg_id: str, file_id: str):
    convo = await db["conversations"].find_one({"_id": ObjectId(conv_id)})
    if not convo:
        raise HTTPException(404, "Conversation not found")

    # Find the message with the given msg_id
    msg = next((m for m in convo.get("messages", []) if str(m.get("id")) == msg_id), None)
    if not msg:
        raise HTTPException(404, "Message not found")

    citations = []
    for c in (msg.get("citations") or []):
        if c.get("file_id") == file_id:
            if isinstance(c, dict):
                citations.append(Citation(**c))
            else:
                print(f"Skipping non-dict citation item: {c}")
    return citations